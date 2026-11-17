"""Step-by-step decomposition of the final four-sleeve strategy (final-daily-submission branch).

Reuses run_final_strategy's construction exactly; only the target/execution step changes:
  1. trend sleeve only, risk-normalized to 10%, no limits, full rebalance
  2. 30/20/20/30 blend, risk-normalized to 10%, no limits, full rebalance
  3. blend + four limits (blended_target), full rebalance
  4. blend + limits + gamma=5 cost-aware execution (= final)
Every step is marked daily with mark_daily (same costs) and measured on 21-business-day
period endpoints like compare_baseline.py (annual mean x12, vol x sqrt(12)).
Step 2b (blend without re-normalizing to 10%) separates the re-scaling in step 2 from the limits in step 3.

    python decompose_steps.py      # writes outputs/decomposition/decompose_steps.csv
"""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd

import run_final_strategy as rf
from costs_and_execution import execute, mark_daily
from data_utils import ROOT, daily_returns, monthly_returns, period_returns, rebalance_dates
from macro_trend import RATE_FUTURES_IN_FX
from portfolio_engine import blended_target, risk_normalize
from price_trend import daily_signal_and_vol
from risk_model import LIMITS, daily_covariance_cube

OUT = ROOT / "outputs" / "decomposition"
PERIODS = {"IS": ("1976-01-01", "2014-12-31"), "OOS": ("2015-01-01", "2025-05-31")}


def measures(r):
    vol = r.std() * np.sqrt(12)
    wealth = (1 + r).cumprod()
    return dict(ret=r.mean() * 12, vol=vol, sharpe=r.mean() * 12 / vol,
                maxdd=(wealth / wealth.cummax().clip(lower=1) - 1).min())


def main():
    monthly = monthly_returns()
    daily = daily_returns(list(monthly.columns))
    dates = rebalance_dates(daily.index)
    dates = dates[(dates >= pd.Timestamp("1975-01-01")) & (dates <= monthly.index.max())]
    slow, vol = daily_signal_and_vol(daily, dates)
    eligible_frame = slow.notna() & vol.notna() & slow.ne(0)
    eligible = eligible_frame.to_numpy()
    cov = daily_covariance_cube(daily, dates, eligible_frame)
    daily_core = risk_normalize(rf.inverse_vol_weight(slow, vol).to_numpy() * eligible, cov)
    monthly_basis, classes, _ = rf.build_monthly_sleeves(monthly)
    basis = rf.dated_sleeves(monthly, monthly_basis, dates, daily_core, cov, eligible)
    mapped = classes.copy()
    mapped.loc[mapped.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    groups = [mapped.eq(c).to_numpy() for c in sorted(mapped.unique())]
    forward = period_returns(daily, dates).reindex(columns=monthly.columns).reindex(dates).fillna(0).to_numpy()

    blend = np.einsum("tki,k->ti", basis, rf.BUDGETS)
    limited = blended_target(basis, rf.BUDGETS, cov, groups, LIMITS)
    final, _ = execute(limited, cov, forward, groups, eligible, LIMITS)
    steps = {"1 trend only, no limits, full rebalance": daily_core,
             "2 four-sleeve blend, no limits, full rebalance": risk_normalize(blend, cov),
             "2b four-sleeve blend, not re-normalized": blend,
             "3 blend + four limits, full rebalance": limited,
             "4 blend + limits + gamma=5 (= final)": final}
    rows = []
    for name, w in steps.items():
        marked = mark_daily(daily, pd.DataFrame(w, index=dates, columns=monthly.columns))
        wealth = (1 + marked.net_return).cumprod().reindex(dates)
        per = (wealth / wealth.shift(1) - 1).dropna()
        row = {"step": name}
        for p, (a, b) in PERIODS.items():
            m = measures(per.loc[a:b])
            row.update({f"{p} {k}": v for k, v in m.items()})
            sample = marked.loc[a:b]
            row[f"{p} turnover"] = sample.turnover.sum() / (len(per.loc[a:b]) / 12)
            row[f"{p} gross lev"] = sample.gross_exposure.mean()
        rows.append(row)
        print(name, {k: round(v, 3) for k, v in row.items() if k != "step"}, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "decompose_steps.csv", index=False)


if __name__ == "__main__":
    main()
