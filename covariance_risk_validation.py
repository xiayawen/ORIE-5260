"""Compare causal covariance forecasts at unchanged adjusted-baseline weights.

Run baseline_performance_analysis.py first. No strategy or leverage is changed.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from baseline_output_loader import load_baseline_outputs, formation_date_risk_inputs
from strategy_backtest_adj import read_returns
from validate_diagonal_risk_model import forward_fixed_weight_volatility

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "covariance_risk_validation_output"
MIN_OVERLAP = 36
HALFLIFE = 6
SHRINKAGE = 0.5
MODELS = ("diagonal", "expanding_covariance", "ewma_covariance", "shrunk_covariance")


def covariance(history, halflife=None):
    """Pairwise weighted covariance, then PSD correlation repair.

    Unknown correlations (<36 overlapping months) fall back to zero. Marginal
    variances use each instrument's available history; missing returns are never
    treated as zero observations. EWMA decay uses calendar-month row distance.
    """
    x = history.to_numpy(dtype=float)
    valid = np.isfinite(x).astype(float)
    x = np.nan_to_num(x, nan=0.0)
    decay = np.ones(len(x)) if halflife is None else 2.0 ** (-np.arange(len(x)-1, -1, -1) / halflife)
    mass = valid.T @ (valid * decay[:, None])
    squared_mass = valid.T @ (valid * decay[:, None] ** 2)
    totals = x.T @ (valid * decay[:, None])
    cross = x.T @ (x * decay[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = (cross - totals * totals.T / mass) / (mass - squared_mass / mass)
    variance = np.diag(raw).copy()
    if not np.all(np.isfinite(variance) & (variance > 0)):
        raise ValueError("Active instruments require finite, positive variance")
    scale = np.sqrt(variance)
    corr = raw / np.outer(scale, scale)
    overlap = valid.T @ valid
    corr[(overlap < MIN_OVERLAP) | ~np.isfinite(corr)] = 0.0
    np.fill_diagonal(corr, 1.0)
    corr = (corr + corr.T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    repaired = (eigenvectors * np.maximum(eigenvalues, 0)) @ eigenvectors.T
    norm = np.sqrt(np.diag(repaired))
    repaired /= np.outer(norm, norm)
    upper = np.triu_indices(len(scale), 1)
    diagnostics = {
        "minimum_raw_correlation_eigenvalue": eigenvalues.min(),
        "psd_repair_frobenius": np.linalg.norm(repaired - corr),
        "low_overlap_pairs": int((overlap[upper] < MIN_OVERLAP).sum()),
        "pairs": len(upper[0]),
    }
    return repaired * np.outer(scale, scale) * 12, diagnostics


def predict(returns, weights, volatility):
    predictions, diagnostics = [], []
    for date, row in weights.iterrows():
        active = row.index[row.fillna(0).ne(0)]
        if not len(active):
            continue
        w = row[active].to_numpy()
        history = returns.loc[:date, active]
        historical, diag = covariance(history)
        ewma, ewma_diag = covariance(history, HALFLIFE)
        sigma = volatility.loc[date, active].to_numpy()
        if not np.all(np.isfinite(sigma) & (sigma > 0)):
            raise ValueError(f"Invalid baseline volatility at {date}")
        matrices = (
            np.diag(sigma ** 2), historical, ewma,
            (1-SHRINKAGE) * historical + SHRINKAGE * np.diag(np.diag(historical)),
        )
        predictions.append({"Date": date, **{
            name: np.sqrt(max(float(w @ matrix @ w), 0))
            for name, matrix in zip(MODELS, matrices)
        }})
        for name, details in (("expanding_covariance", diag), ("ewma_covariance", ewma_diag)):
            diagnostics.append({"Date": date, "model": name, "active_instruments": len(active), **details})
    return pd.DataFrame(predictions).set_index("Date"), pd.DataFrame(diagnostics)


def summarize(group):
    predicted, realized = group.predicted, group.realized
    error = realized - predicted
    return pd.Series({
        "months": len(group), "start": group.Date.min(), "end": group.Date.max(),
        "average_predicted_volatility": predicted.mean(),
        "average_realized_volatility": realized.mean(),
        "mean_forecast_error": error.mean(), "mean_absolute_error": error.abs().mean(),
        "root_mean_squared_error": np.sqrt((error ** 2).mean()),
        "forecast_realized_correlation": predicted.corr(realized),
        "realized_exceedance_frequency": (realized > predicted).mean(),
        "realized_25pct_exceedance_frequency": (realized > 1.25 * predicted).mean(),
    })


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    baseline = load_baseline_outputs()
    weights, volatility = formation_date_risk_inputs(baseline)
    weights = weights.reindex(index=returns.index, columns=returns.columns).fillna(0)
    volatility = volatility.reindex(index=returns.index, columns=returns.columns)
    start = baseline["monthly_returns"].index.min()
    predictions, diagnostics = predict(returns, weights.loc[start:], volatility)
    tables = []
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    for horizon, ax in zip((12, 3), axes):
        realized = forward_fixed_weight_volatility(returns, weights, horizon)
        common = predictions.join(realized.rename("realized")).dropna()
        for model in MODELS:
            table = common[[model, "realized"]].rename(columns={model: "predicted"}).reset_index()
            table["model"], table["horizon_months"] = model, horizon
            tables.append(table)
        common.plot(ax=ax, linewidth=1, alpha=0.8)
        ax.set_title(f"Fixed baseline weights: {horizon}-month forward risk")
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylabel("Annualized volatility")
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "forecast_comparison.png", dpi=160)
    plt.close(fig)
    forecasts = pd.concat(tables, ignore_index=True)
    keys = ["horizon_months", "model"]
    summary = forecasts.groupby(keys)[["Date", "predicted", "realized"]].apply(summarize).reset_index()
    forecasts["decade"] = forecasts.Date.dt.year // 10 * 10
    periods = forecasts.groupby(keys + ["decade"])[["Date", "predicted", "realized"]].apply(summarize).reset_index()
    forecasts.to_csv(OUT / "monthly_risk_forecasts.csv", index=False)
    summary.to_csv(OUT / "forecast_accuracy_summary.csv", index=False)
    periods.to_csv(OUT / "forecast_accuracy_by_period.csv", index=False)
    diagnostics.to_csv(OUT / "covariance_diagnostics.csv", index=False)
    lines = ["# Covariance risk validation", "", "Unchanged adjusted-baseline weights; formation-month information only.",
             "", "All models use identical evaluation dates within each horizon. Historical estimates are expanding; EWMA has a fixed six-month half-life. Shrinkage is fixed at 50% toward the historical diagonal, not fitted to these results.",
             "", "Pairwise estimates use available observations, require 36 overlapping months for correlations, and assume zero correlation otherwise. Correlation matrices are projected to PSD and renormalized to preserve marginal variances. Repair diagnostics are exported. EWMA changes both variances and correlations, so its comparison does not isolate correlation alone.",
             "", "Future fixed-weight realized returns fill missing observations with zero, matching existing validation. Forecast windows overlap; statistics are descriptive, not independent observations or an out-of-sample model-selection exercise. Last formation dates without a complete future horizon are excluded. No portfolio targeting or leverage changes are introduced.",
             "", "| Horizon | Model | Predicted vol | Realized vol | MAE | RMSE | Exceedance |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in summary.itertuples():
        lines.append(f"| {row.horizon_months} | {row.model} | {row.average_predicted_volatility:.2%} | {row.average_realized_volatility:.2%} | {row.mean_absolute_error:.2%} | {row.root_mean_squared_error:.2%} | {row.realized_exceedance_frequency:.1%} |")
    (OUT / "methodology_and_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
