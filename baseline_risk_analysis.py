"""Describe the adjusted baseline under its existing diagonal risk model.

This is item 5 of the baseline-analysis plan. Item 3 owns exposure, rolling
volatility, and drawdown outputs. This script reuses its standardized weights and
volatility estimates to report diagonal variance contributions and concentration.
It does not estimate covariance matrices, target portfolio volatility, or modify
strategy weights.
"""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from baseline_output_loader import load_baseline_outputs
from strategy_backtest_adj import read_asset_map


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "baseline_risk_analysis_output"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    asset_map = read_asset_map()
    baseline = load_baseline_outputs()
    weights = baseline["executed_weights"].fillna(0.0)
    forecast_vol = baseline["volatility_estimates"].reindex(weights.index)
    class_lookup = asset_map.set_index("ID")["AssetClass"].to_dict()

    variance_contribution = weights.pow(2) * forecast_vol.pow(2)
    total_variance = variance_contribution.sum(axis=1)
    risk_share = variance_contribution.div(total_variance.replace(0, np.nan), axis=0)
    class_variance = variance_contribution.T.groupby(
        variance_contribution.columns.map(class_lookup)
    ).sum().T
    class_risk_share = class_variance.div(total_variance.replace(0, np.nan), axis=0)

    concentration = pd.DataFrame(index=weights.index)
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
