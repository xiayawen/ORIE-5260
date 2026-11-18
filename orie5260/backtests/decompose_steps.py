"""Step-by-step decomposition of the four-sleeve strategy (report appendix).

Reuses run_final_strategy's construction; only the target / execution step changes:
  1. trend sleeve only, scaled to 10% ex-ante vol, no limits, full rebalance
  2. 30/20/20/30 blend, scaled to 10% ex-ante vol, no limits, full rebalance  (= selected final)
  2b. the same blend without re-scaling to 10% (separates the scaling in 2 from the limits in 3)
  3. blend + four limits (10% vol ceiling, 4x gross, 1x net, 5% per class), full rebalance
  4. blend + four limits + gamma=5 cost-aware execution
Every step is marked daily with mark_daily (same costs) and measured on 21-business-day
period endpoints like compare_baseline.py (annual mean x12, vol x sqrt(12)).

    python decompose_steps.py      # writes outputs/decomposition/decompose_steps.{csv,md}
"""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd

from orie5260.execution.costs_and_execution import execute, mark_daily
from orie5260.common.data import ROOT
from orie5260.portfolio.engine import blended_target, risk_normalize
from orie5260.portfolio.risk_model import LIMITS
from orie5260.backtests.final_strategy import BUDGETS, build_portfolio_inputs, final_target

OUT = ROOT / "outputs" / "decomposition"
PERIODS = {"IS": ("1976-01-01", "2014-12-31"), "OOS": ("2015-01-01", "2025-05-31")}
STEPS = {"1": "Trend sleeve only, 10% scaling, no limits, full rebalance",
         "2": "Four-sleeve blend, 10% scaling, no limits, full rebalance (selected final)",
         "2b": "Four-sleeve blend, not re-scaled, no limits, full rebalance",
         "3": "Blend + four limits, full rebalance",
         "4": "Blend + four limits + gamma=5 cost-aware execution"}


def measures(r):
    vol = r.std() * np.sqrt(12)
    wealth = (1 + r).cumprod()
    return dict(ret=r.mean() * 12, vol=vol, sharpe=r.mean() * 12 / vol,
                maxdd=(wealth / wealth.cummax().clip(lower=1) - 1).min())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    x = build_portfolio_inputs()
    dates, cov = x["dates"], x["covariance"]
    blend = np.einsum("tki,k->ti", x["basis"], BUDGETS)
    limited = blended_target(x["basis"], BUDGETS, cov, x["groups"], LIMITS)
    capped_gamma5, _ = execute(limited, cov, x["forward"], x["groups"], x["eligible"], LIMITS)
    targets = {"1": x["daily_core"], "2": final_target(x), "2b": blend, "3": limited, "4": capped_gamma5}
    assert np.allclose(targets["2"], risk_normalize(blend, cov))
    rows = []
    for step, w in targets.items():
        marked = mark_daily(x["daily"], pd.DataFrame(w, index=dates, columns=x["monthly"].columns))
        wealth = (1 + marked.net_return).cumprod().reindex(dates)
        per = (wealth / wealth.shift(1) - 1).dropna()
        row = {"step": step, "description": STEPS[step]}
        for p, (a, b) in PERIODS.items():
            row.update({f"{p}_{k}": v for k, v in measures(per.loc[a:b]).items()})
            sample, years = marked.loc[a:b], len(per.loc[a:b]) / 12
            row[f"{p}_turnover"] = sample.turnover.sum() / years
            row[f"{p}_cost"] = (sample.trade_cost + sample.roll_cost).sum() / years
            row[f"{p}_gross"] = sample.gross_exposure.mean()
            row[f"{p}_abs_net"] = sample.net_exposure.abs().mean()
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "decompose_steps.csv", index=False)
    cols = [("ret", "Net ret", "{:.1%}"), ("vol", "Vol", "{:.1%}"), ("sharpe", "Sharpe", "{:.3f}"),
            ("maxdd", "Max DD", "{:.1%}"), ("turnover", "Turnover", "{:.1f}"), ("cost", "Cost", "{:.2%}"),
            ("gross", "Gross", "{:.2f}x"), ("abs_net", "|Net|", "{:.2f}x")]
    lines = ["| Step | Construction | " + " | ".join(f"{p} {lab}" for p in PERIODS for _, lab, _ in cols) + " |",
             "|---|---|" + "---:|" * (2 * len(cols))]
    for r in table.itertuples(index=False):
        r = r._asdict()
        lines.append(f"| {r['step']} | {r['description']} | "
                     + " | ".join(f.format(r[f'{p}_{k}']) for p in PERIODS for k, _, f in cols) + " |")
    (OUT / "decompose_steps.md").write_text(
        "# Step-by-step decomposition\n\n21-business-day period endpoints; IS = 1976-2014, OOS = 2015-May 2025. "
        "Net of 2 bps per unit traded + 4 rolls a year at 2 bps.\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
