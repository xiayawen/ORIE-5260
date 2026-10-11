"""Validate the adjusted baseline's existing diagonal volatility forecast.

This is item 6 of the baseline-analysis plan. It compares ex-ante diagonal
portfolio volatility with fixed-weight realized volatility over the next 12 months,
plus a 3-month robustness check. It does not estimate or test covariance models.
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
HORIZONS = (12, 3)
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "risk_model_validation_output"


def forward_fixed_weight_volatility(
    returns: pd.DataFrame, formation_weights: pd.DataFrame, horizon: int
) -> pd.Series:
    """Realized annualized vol of weights held fixed over the following horizon."""
    future_returns = []
    for step in range(1, horizon + 1):
        future_returns.append(
            (formation_weights * returns.shift(-step).fillna(0.0)).sum(axis=1)
        )
    matrix = pd.concat(future_returns, axis=1)
    matrix.columns = [f"month_{step}" for step in range(1, horizon + 1)]
    realized = matrix.std(axis=1, ddof=1) * np.sqrt(TRADING_MONTHS)
    valid_end = len(returns) - horizon
    realized.iloc[valid_end:] = np.nan
    return realized


def validation_table(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    volatility: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    predicted = np.sqrt((weights.pow(2) * volatility.pow(2)).sum(axis=1))
    predicted = predicted.where(volatility.notna().any(axis=1) & weights.ne(0).any(axis=1))
    realized = forward_fixed_weight_volatility(returns, weights, horizon)
    table = pd.DataFrame(
        {
            "predicted_diagonal_volatility": predicted,
            "realized_forward_volatility": realized,
        }
    ).dropna()
    table["forecast_error"] = (
        table["realized_forward_volatility"]
        - table["predicted_diagonal_volatility"]
    )
    table["absolute_error"] = table["forecast_error"].abs()
    table["squared_error"] = table["forecast_error"].pow(2)
    table["realized_to_predicted_ratio"] = (
        table["realized_forward_volatility"]
        / table["predicted_diagonal_volatility"]
    )
    table["realized_exceeds_prediction"] = (
        table["realized_forward_volatility"]
        > table["predicted_diagonal_volatility"]
    )
    table["realized_exceeds_prediction_by_25pct"] = (
        table["realized_forward_volatility"]
        > 1.25 * table["predicted_diagonal_volatility"]
    )
    high_threshold = table["realized_forward_volatility"].quantile(0.80)
    table["high_realized_volatility_period"] = (
        table["realized_forward_volatility"] >= high_threshold
    )
    table["horizon_months"] = horizon
    return table


def summarize_validation(table: pd.DataFrame, label: str) -> dict[str, float | str]:
    return {
        "sample": label,
        "horizon_months": int(table["horizon_months"].iloc[0]),
        "start": str(table.index.min().date()),
        "end": str(table.index.max().date()),
        "months": len(table),
        "average_predicted_volatility": table["predicted_diagonal_volatility"].mean(),
        "average_realized_volatility": table["realized_forward_volatility"].mean(),
        "mean_forecast_error": table["forecast_error"].mean(),
        "mean_absolute_error": table["absolute_error"].mean(),
        "root_mean_squared_error": np.sqrt(table["squared_error"].mean()),
        "forecast_realized_correlation": table[
            "predicted_diagonal_volatility"
        ].corr(table["realized_forward_volatility"]),
        "realized_exceedance_frequency": table[
            "realized_exceeds_prediction"
        ].mean(),
        "realized_25pct_exceedance_frequency": table[
            "realized_exceeds_prediction_by_25pct"
        ].mean(),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    asset_map = read_asset_map()
    baseline, _ = build_baseline(returns, asset_map)
    weights = baseline["weights"].reindex(returns.index).fillna(0.0)
    volatility = baseline["vol"].reindex(returns.index)
    evaluation_start = baseline["returns"].index.min()
    class_lookup = asset_map.set_index("ID")["AssetClass"].to_dict()

    tables = {
        horizon: validation_table(returns, weights, volatility, horizon).loc[
            evaluation_start:
        ]
        for horizon in HORIZONS
    }
    combined = pd.concat(tables.values()).sort_index()
    summaries = [summarize_validation(tables[h], "whole_portfolio") for h in HORIZONS]

    period_rows = []
    for horizon, table in tables.items():
        decades = table.index.year // 10 * 10
        for decade, subset in table.groupby(decades):
            row = summarize_validation(subset, f"{decade}s")
            period_rows.append(row)

    class_rows = []
    for asset_class in sorted(set(class_lookup.values())):
        columns = [column for column in returns if class_lookup.get(column) == asset_class]
        for horizon in HORIZONS:
            table = validation_table(
                returns[columns], weights[columns], volatility[columns], horizon
            ).loc[evaluation_start:]
            if not table.empty:
                class_rows.append(summarize_validation(table, asset_class))

    high_vol_rows = []
    for horizon, table in tables.items():
        for high_flag, subset in table.groupby("high_realized_volatility_period"):
            row = summarize_validation(
                subset, "high_volatility" if high_flag else "other_periods"
            )
            high_vol_rows.append(row)

    combined.to_csv(OUT_DIR / "monthly_risk_forecasts.csv")
    pd.DataFrame(summaries).to_csv(
        OUT_DIR / "forecast_accuracy_summary.csv", index=False
    )
    pd.DataFrame(period_rows).to_csv(
        OUT_DIR / "forecast_accuracy_by_period.csv", index=False
    )
    pd.DataFrame(class_rows).to_csv(
        OUT_DIR / "forecast_accuracy_by_asset_class.csv", index=False
    )
    pd.DataFrame(high_vol_rows).to_csv(
        OUT_DIR / "forecast_accuracy_high_volatility.csv", index=False
    )

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for ax, horizon in zip(axes, HORIZONS):
        table = tables[horizon]
        table[
            ["predicted_diagonal_volatility", "realized_forward_volatility"]
        ].plot(ax=ax)
        ax.set_title(f"Predicted versus realized volatility: {horizon}-month horizon")
        ax.set_ylabel("Annualized volatility")
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "predicted_vs_realized_volatility.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, horizon in zip(axes, HORIZONS):
        table = tables[horizon]
        ax.scatter(
            table["predicted_diagonal_volatility"],
            table["realized_forward_volatility"],
            alpha=0.45,
            s=18,
        )
        limit = max(
            table["predicted_diagonal_volatility"].max(),
            table["realized_forward_volatility"].max(),
        )
        ax.plot([0, limit], [0, limit], color="#c44e52", linewidth=1)
        ax.set_title(f"{horizon}-month forecast")
        ax.set_xlabel("Predicted diagonal volatility")
        ax.set_ylabel("Realized forward volatility")
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "forecast_scatter.png", dpi=180)
    plt.close(fig)

    print(f"Wrote diagonal-risk validation outputs to {OUT_DIR}")
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
