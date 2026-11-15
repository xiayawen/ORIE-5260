"""Describe the adjusted baseline under its existing diagonal risk model.

This is item 5 of the baseline-analysis plan. Item 3 owns exposure, rolling
volatility, and drawdown outputs. This script reuses its standardized weights and
volatility estimates to report diagonal variance contributions and concentration.
It does not target portfolio volatility or modify strategy weights.

R1 extension: the same executed weights are also decomposed with full EWMA and
expanding covariance forecasts (Euler / Zivot risk budgeting: MCR = S w / sigma,
CR = w * MCR, PCR = CR / sigma, sum PCR = 1). Each execution-month forecast uses
returns through the formation month only. PCR can be negative for positions that
hedge the rest of the book. The diagonal outputs above are unchanged.
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
from strategy_backtest_adj import read_asset_map, read_returns
from risk_budgeting import covariance_matrix, euler_decomposition


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "baseline_risk_analysis_output"
COVARIANCE_MODELS = ("ewma", "expanding")


def covariance_risk_decomposition(weights, returns, class_lookup):
    """R1: covariance Euler decomposition of execution-month weights.

    The forecast for execution month t uses returns through the formation month
    (the previous row of the return index), the same date the weights were formed.
    """
    position = returns.index.get_indexer(weights.index)
    if (position < 1).any():
        raise ValueError("Every execution month needs a preceding formation month")
    formation_dates = returns.index[position - 1]
    instrument = {m: {} for m in COVARIANCE_MODELS}
    by_class = {m: {} for m in COVARIANCE_MODELS}
    concentration = []
    for execution_date, formation_date in zip(weights.index, formation_dates):
        row = weights.loc[execution_date]
        active = row.index[row.ne(0)]
        if not len(active):
            continue
        history = returns.loc[:formation_date, active]
        for model in COVARIANCE_MODELS:
            euler = euler_decomposition(row[active].to_numpy(), covariance_matrix(history, model))
            pcr = pd.Series(euler["pcr"], index=active)
            classes = pcr.groupby(active.map(class_lookup)).sum()
            instrument[model][execution_date] = pcr
            by_class[model][execution_date] = classes
            concentration.append({
                "Date": execution_date, "model": model,
                "predicted_volatility": euler["sigma"],
                "largest_instrument_pcr": pcr.max(),
                "effective_instrument_risk_positions": 1.0 / (pcr ** 2).sum(),
                "negative_pcr_share_of_positions": (pcr < 0).mean(),
                "largest_asset_class_pcr": classes.max(),
                "effective_asset_class_risk_positions": 1.0 / (classes ** 2).sum(),
                "pcr_sum_error": abs(pcr.sum() - 1.0),
            })
    instrument = {m: pd.DataFrame(v).T.reindex(columns=weights.columns) for m, v in instrument.items()}
    by_class = {m: pd.DataFrame(v).T.fillna(0.0) for m, v in by_class.items()}
    return instrument, by_class, pd.DataFrame(concentration)


def write_covariance_outputs(weights, class_risk_share, concentration_diagonal, class_lookup):
    returns = read_returns()
    instrument, by_class, concentration = covariance_risk_decomposition(weights, returns, class_lookup)
    error = concentration.pcr_sum_error.max()
    if error > 1e-8:
        raise AssertionError(f"Covariance PCRs do not sum to one: {error}")
    rows = []
    for model in COVARIANCE_MODELS:
        instrument[model].to_csv(OUT_DIR / f"covariance_instrument_pcr_{model}.csv", index_label="Date")
        by_class[model].to_csv(OUT_DIR / f"covariance_asset_class_pcr_{model}.csv", index_label="Date")
    for label, shares in (("diagonal", class_risk_share), *(("cov_" + m, by_class[m]) for m in COVARIANCE_MODELS)):
        shares = shares.loc[by_class["ewma"].index]
        for asset_class in shares.columns:
            rows.append({"model": label, "asset_class": asset_class,
                         "average_risk_share": shares[asset_class].mean(),
                         "maximum_risk_share": shares[asset_class].max(),
                         "average_1976_1994": shares.loc[:"1994", asset_class].mean(),
                         "average_1995_2014": shares.loc["1995":, asset_class].mean()})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_DIR / "diagonal_vs_covariance_class_risk.csv", index=False)
    concentration.to_csv(OUT_DIR / "covariance_risk_concentration.csv", index=False)
    stats = concentration.groupby("model")[["predicted_volatility", "largest_asset_class_pcr",
                                            "effective_asset_class_risk_positions",
                                            "effective_instrument_risk_positions",
                                            "negative_pcr_share_of_positions"]].mean()
    stats.loc["diagonal"] = [concentration_diagonal.predicted_diagonal_volatility.mean(),
                             concentration_diagonal.largest_asset_class_risk_share.mean(),
                             concentration_diagonal.effective_asset_class_risk_positions.mean(),
                             concentration_diagonal.effective_instrument_risk_positions.mean(), 0.0]
    stats.to_csv(OUT_DIR / "covariance_concentration_summary.csv")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    for ax, (title, shares) in zip(axes, (("Diagonal", class_risk_share), ("EWMA covariance (Euler PCR)", by_class["ewma"]))):
        shares.rolling(12, min_periods=1).mean().plot(ax=ax)
        ax.set_title(f"{title}: asset-class risk share (12m avg)")
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.axhline(0.25, color="black", ls=":", lw=1)
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "diagonal_vs_covariance_class_risk.png", dpi=180)
    plt.close(fig)
    print(stats.round(4).to_string())
    print(summary.pivot(index="asset_class", columns="model", values="average_risk_share").round(4).to_string())


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
    write_covariance_outputs(weights, class_risk_share, concentration, class_lookup)
    print(f"Wrote baseline-risk outputs to {OUT_DIR}")
    print(f"Maximum instrument risk-share reconciliation error: {error:.3g}")


if __name__ == "__main__":
    main()
