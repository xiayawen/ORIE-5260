"""Describe the adjusted baseline under its existing diagonal risk model.

This is item 5 of the baseline-analysis plan. It reports exposure, realized risk,
drawdowns, and diagonal variance contributions. It does not estimate covariance
matrices, target portfolio volatility, or modify strategy weights.
"""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strategy_backtest_adj import build_baseline, read_asset_map, read_returns


TRADING_MONTHS = 12
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "baseline_risk_analysis_output"


def drawdown_table(portfolio_returns: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    wealth = (1.0 + portfolio_returns.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    events = []
    peak_pos = 0
    pos = 1
    event_id = 0
    while pos < len(wealth):
        if wealth.iloc[pos] >= wealth.iloc[peak_pos]:
            peak_pos = pos
            pos += 1
            continue
        trough_pos = pos
        scan = pos + 1
        while scan < len(wealth) and wealth.iloc[scan] < wealth.iloc[peak_pos]:
            if wealth.iloc[scan] < wealth.iloc[trough_pos]:
                trough_pos = scan
            scan += 1
        recovery_pos = scan if scan < len(wealth) else None
        event_id += 1
        events.append(
            {
                "event_id": event_id,
                "peak_date": wealth.index[peak_pos],
                "trough_date": wealth.index[trough_pos],
                "recovery_date": wealth.index[recovery_pos]
                if recovery_pos is not None
                else pd.NaT,
                "maximum_drawdown": drawdown.iloc[trough_pos],
                "months_peak_to_trough": trough_pos - peak_pos,
                "months_peak_to_recovery": recovery_pos - peak_pos
                if recovery_pos is not None
                else np.nan,
            }
        )
        if recovery_pos is None:
            break
        peak_pos = recovery_pos
        pos = recovery_pos + 1
    return drawdown, pd.DataFrame(events)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    asset_map = read_asset_map()
    baseline, _ = build_baseline(returns, asset_map)
    portfolio = baseline["returns"]
    weights = baseline["execution_weights"].reindex(portfolio.index).fillna(0.0)
    forecast_vol = baseline["vol"].shift(1).reindex(portfolio.index)
    class_lookup = asset_map.set_index("ID")["AssetClass"].to_dict()

    exposures = pd.DataFrame(index=portfolio.index)
    exposures["gross_exposure"] = weights.abs().sum(axis=1)
    exposures["net_exposure"] = weights.sum(axis=1)
    exposures["long_exposure"] = weights.clip(lower=0).sum(axis=1)
    exposures["short_exposure"] = weights.clip(upper=0).sum(axis=1)
    exposures["active_positions"] = weights.ne(0).sum(axis=1)

    rolling_risk = pd.DataFrame(index=portfolio.index)
    for window in (12, 36, 60):
        rolling_risk[f"realized_volatility_{window}m"] = (
            portfolio.rolling(window).std() * np.sqrt(TRADING_MONTHS)
        )
    drawdown, drawdown_events = drawdown_table(portfolio)
    rolling_risk["drawdown"] = drawdown

    variance_contribution = weights.pow(2) * forecast_vol.pow(2)
    total_variance = variance_contribution.sum(axis=1)
    risk_share = variance_contribution.div(total_variance.replace(0, np.nan), axis=0)
    class_variance = variance_contribution.T.groupby(
        variance_contribution.columns.map(class_lookup)
    ).sum().T
    class_risk_share = class_variance.div(total_variance.replace(0, np.nan), axis=0)

    concentration = pd.DataFrame(index=portfolio.index)
    concentration["predicted_diagonal_volatility"] = np.sqrt(total_variance)
    concentration["largest_instrument_risk_share"] = risk_share.max(axis=1)
    concentration["instrument_risk_hhi"] = risk_share.pow(2).sum(axis=1)
    concentration["effective_instrument_risk_positions"] = 1.0 / concentration[
        "instrument_risk_hhi"
    ].replace(0, np.nan)
    concentration["largest_asset_class_risk_share"] = class_risk_share.max(axis=1)
    concentration["asset_class_risk_hhi"] = class_risk_share.pow(2).sum(axis=1)
    concentration["effective_asset_class_risk_positions"] = 1.0 / concentration[
        "asset_class_risk_hhi"
    ].replace(0, np.nan)

    instrument_average = pd.DataFrame(
        {
            "ID": risk_share.columns,
            "average_risk_share": risk_share.mean().values,
            "maximum_risk_share": risk_share.max().values,
        }
    )
    instrument_average["AssetClass"] = instrument_average["ID"].map(class_lookup)
    instrument_average = instrument_average.sort_values(
        "average_risk_share", ascending=False
    )
    class_average = pd.DataFrame(
        {
            "asset_class": class_risk_share.columns,
            "average_risk_share": class_risk_share.mean().values,
            "maximum_risk_share": class_risk_share.max().values,
        }
    ).sort_values("average_risk_share", ascending=False)

    exposures.to_csv(OUT_DIR / "monthly_exposure.csv")
    rolling_risk.to_csv(OUT_DIR / "rolling_realized_risk.csv")
    variance_contribution.to_csv(OUT_DIR / "instrument_variance_contribution.csv")
    risk_share.to_csv(OUT_DIR / "instrument_risk_share.csv")
    class_risk_share.to_csv(OUT_DIR / "asset_class_risk_share.csv")
    concentration.to_csv(OUT_DIR / "risk_concentration.csv")
    instrument_average.to_csv(
        OUT_DIR / "instrument_risk_contribution_summary.csv", index=False
    )
    class_average.to_csv(
        OUT_DIR / "asset_class_risk_contribution_summary.csv", index=False
    )
    drawdown_events.to_csv(OUT_DIR / "drawdown_analysis.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    exposures[["gross_exposure", "long_exposure", "short_exposure"]].plot(
        ax=axes[0]
    )
    exposures["net_exposure"].plot(ax=axes[1], color="#1f4e79")
    axes[0].set_title("Baseline gross, long, and short exposure")
    axes[1].set_title("Baseline net exposure")
    for ax in axes:
        ax.axhline(0, color="#666666", linewidth=0.8)
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "gross_net_exposure.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    rolling_risk[
        ["realized_volatility_12m", "realized_volatility_36m", "realized_volatility_60m"]
    ].plot(ax=ax)
    ax.set_title("Rolling realized volatility of the adjusted baseline")
    ax.set_ylabel("Annualized volatility")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rolling_volatility.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    class_risk_share.plot.area(ax=ax, stacked=True)
    ax.set_title("Diagonal risk share by asset class")
    ax.set_ylabel("Share of predicted diagonal variance")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "risk_contribution_by_asset_class.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    concentration[
        ["largest_instrument_risk_share", "largest_asset_class_risk_share"]
    ].plot(ax=ax)
    ax.set_title("Largest diagonal risk concentration through time")
    ax.set_ylabel("Largest risk share")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "risk_concentration.png", dpi=180)
    plt.close(fig)

    valid_share_sum = risk_share.sum(axis=1).loc[total_variance > 0]
    error = (valid_share_sum - 1.0).abs().max()
    if error > 1e-10:
        raise AssertionError(f"Instrument risk shares do not sum to one: {error}")
    print(f"Wrote baseline-risk outputs to {OUT_DIR}")
    print(f"Maximum instrument risk-share reconciliation error: {error:.3g}")


if __name__ == "__main__":
    main()
