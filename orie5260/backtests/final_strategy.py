"""Run the selected daily-signal four-sleeve futures portfolio.

Four fixed signal budgets: 30% price trend, 20% macro, 20% negative skew,
30% frozen Extra Trees. The blended book is scaled to 10% ex-ante volatility
(252-day daily covariance) with no exposure caps, and fully rebalanced every
21 business days; NAV is marked daily. The capped and cost-aware variants are
appendix diagnostics (decompose_steps.py, exposure_sensitivity.py).
"""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from orie5260.execution.costs_and_execution import mark_daily
from orie5260.common.data import ROOT, asset_map, daily_returns, monthly_returns, period_returns, rebalance_dates
from orie5260.models.extra_trees import extra_trees_sleeve
from orie5260.signals.macro_trend import macro_sleeve, RATE_FUTURES_IN_FX
from orie5260.signals.negative_skew import skew_sleeve
from orie5260.portfolio.engine import risk_normalize
from orie5260.signals.price_trend import daily_signal_and_vol
from orie5260.portfolio.risk_model import LIMITS, monthly_ewma_vol, monthly_covariance_cube, daily_covariance_cube

OUT = ROOT / "outputs" / "final_strategy"
BUDGETS = np.array([.3, .2, .2, .3])
TARGET_VOLATILITY = LIMITS.volatility  # 10% ex-ante; used as a scaling target, not a ceiling
EVALUATION = {"IS_1976_2014": ("1976-01-01", "2014-12-31"),
              "development_2005_2009": ("2005-01-01", "2009-12-31"),
              "validation_2010_2014": ("2010-01-01", "2014-12-31"),
              "OOS_2015_2025": ("2015-01-01", "2025-05-31")}


def inverse_vol_weight(direction, vol):
    raw = direction / vol
    valid = raw.notna() & direction.ne(0)
    return raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)


def build_monthly_sleeves(monthly):
    amap = asset_map()
    classes = amap.set_index("ID")["AssetClass"].reindex(monthly.columns)
    vol = monthly_ewma_vol(monthly)
    live = monthly.notna().rolling(12, min_periods=12).sum().eq(12)
    sleeve_vol = vol.where(live)
    eligible = sleeve_vol.notna().to_numpy()
    covariance = monthly_covariance_cube(monthly)
    continuous = (monthly.rolling(12, min_periods=12).sum() / vol).clip(-1, 1)
    original_core = risk_normalize(inverse_vol_weight(continuous, sleeve_vol).to_numpy() * eligible, covariance)
    macro = macro_sleeve(monthly, classes, sleeve_vol, covariance, eligible)
    factor = skew_sleeve(monthly, classes, sleeve_vol, covariance, eligible)
    ml, audit = extra_trees_sleeve(monthly, classes, sleeve_vol, covariance, eligible)
    # Return an unavailable sleeve's budget to the original trend core.
    pieces = [original_core]
    for sleeve in (macro, factor, ml):
        pieces.append(np.where((np.abs(sleeve).sum(axis=1) > 0)[:, None], sleeve, original_core))
    return np.stack(pieces, axis=1), classes, audit


def dated_sleeves(monthly, monthly_basis, dates, daily_core, covariance, eligible):
    aligned = []
    for s in range(4):
        frame = pd.DataFrame(monthly_basis[:, s], index=monthly.index, columns=monthly.columns)
        aligned.append(frame.reindex(dates, method="ffill").fillna(0).to_numpy())
    old_core = aligned[0]
    pieces = [daily_core]
    for sleeve in aligned[1:]:
        active = np.abs(sleeve - old_core).sum(axis=1) > 1e-12
        scaled = risk_normalize(sleeve * eligible, covariance)
        pieces.append(np.where(active[:, None], scaled, daily_core))
    return np.stack(pieces, axis=1)


def build_portfolio_inputs():
    """Everything the final strategy and the appendix variants share, dated causally."""
    monthly = monthly_returns()
    daily = daily_returns(list(monthly.columns))
    dates = rebalance_dates(daily.index)
    dates = dates[(dates >= pd.Timestamp("1975-01-01")) & (dates <= monthly.index.max())]
    slow, vol = daily_signal_and_vol(daily, dates)
    eligible_frame = slow.notna() & vol.notna() & slow.ne(0)
    eligible = eligible_frame.to_numpy()
    covariance = daily_covariance_cube(daily, dates, eligible_frame)
    daily_core = risk_normalize(inverse_vol_weight(slow, vol).to_numpy() * eligible, covariance)
    monthly_basis, classes, audit = build_monthly_sleeves(monthly)
    basis = dated_sleeves(monthly, monthly_basis, dates, daily_core, covariance, eligible)
    mapped = classes.copy()
    mapped.loc[mapped.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    groups = [mapped.eq(c).to_numpy() for c in sorted(mapped.unique())]
    forward = period_returns(daily, dates).reindex(columns=monthly.columns).reindex(dates).fillna(0).to_numpy()
    return dict(monthly=monthly, daily=daily, dates=dates, covariance=covariance, eligible=eligible,
                daily_core=daily_core, basis=basis, groups=groups, forward=forward, audit=audit)


def final_target(inputs):
    """Selected portfolio: 30/20/20/30 blend scaled to 10% ex-ante volatility, no caps."""
    blend = np.einsum("tki,k->ti", inputs["basis"], BUDGETS)
    return risk_normalize(blend, inputs["covariance"], TARGET_VOLATILITY)


def summary(frame, start, end):
    sample = frame.loc[start:end]
    wealth = (1 + sample.net_return).cumprod()
    monthly = (1 + sample.net_return).resample("M").prod() - 1
    years = len(monthly) / 12
    return {"daily_observations": len(sample), "annual_mean": float(monthly.mean() * 12),
            "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
            "daily_annual_volatility": float(sample.net_return.std() * np.sqrt(252)),
            "daily_sharpe_zero_rf": float(sample.net_return.mean() / sample.net_return.std() * np.sqrt(252)),
            "max_daily_drawdown": float((wealth / wealth.cummax() - 1).min()),
            "annual_turnover": float(sample.turnover.sum() / years),
            "annual_cost": float((sample.trade_cost + sample.roll_cost).sum() / years),
            "average_gross_exposure": float(sample.gross_exposure.mean()),
            "average_absolute_net_exposure": float(sample.net_exposure.abs().mean())}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = build_portfolio_inputs()
    dates, monthly, covariance = inputs["dates"], inputs["monthly"], inputs["covariance"]
    target = final_target(inputs)
    predicted = np.sqrt(np.maximum(np.einsum("ti,tij,tj->t", target, covariance, target), 0))
    assert np.allclose(predicted[predicted > 0], TARGET_VOLATILITY), "Book not at the 10% ex-ante target"
    weights = pd.DataFrame(target, index=dates, columns=monthly.columns)  # full rebalance to target
    marked = mark_daily(inputs["daily"], weights)
    rows = [{"period": name, **summary(marked, start, end)}
            for name, (start, end) in EVALUATION.items()]
    pd.DataFrame(rows).to_csv(OUT / "performance.csv", index=False)
    marked.to_csv(OUT / "daily_returns_and_costs.csv", index_label="Date")
    weights.to_csv(OUT / "formation_weights.csv", index_label="Date")
    inputs["audit"].to_csv(OUT / "extra_trees_training_audit.csv", index=False)
    fig, ax = plt.subplots(figsize=(11, 5))
    for label, (start, end) in EVALUATION.items():
        if label in ("IS_1976_2014", "OOS_2015_2025"):
            series = marked.loc[start:end, "net_return"]
            ax.plot(series.index, (1 + series).cumprod(), label=label.replace("_", " "))
    ax.set(title="Selected daily four-sleeve portfolio", ylabel="Growth of $1")
    ax.grid(alpha=.2); ax.legend(); fig.tight_layout()
    fig.savefig(OUT / "wealth.png", dpi=160); plt.close(fig)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
