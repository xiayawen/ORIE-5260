"""Performance, attribution, and statistical evaluation for Method 1."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS = {
    "training_1976_1997": ("1976-01-01", "1997-12-31"),
    "validation_1998_2014": ("1998-01-01", "2014-12-31"),
    "development_1976_2014": ("1976-01-01", "2014-12-31"),
    "later_2015_2025": ("2015-01-01", None),
    "full_1976_2025": ("1976-01-01", None),
}


def hac_mean_statistics(values: pd.Series, lags: int = 3) -> dict[str, float]:
    """Mean and Newey-West uncertainty without importing broader reports."""
    clean = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(clean)
    if n == 0:
        return {
            "mean": np.nan,
            "hac_se": np.nan,
            "t_stat": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
        }
    mean = clean.mean()
    demeaned = clean.to_numpy() - mean
    long_run_variance = float(demeaned @ demeaned / n)
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1.0 - lag / (lags + 1.0)
        autocovariance = float(demeaned[lag:] @ demeaned[:-lag] / n)
        long_run_variance += 2.0 * weight * autocovariance
    se = np.sqrt(max(long_run_variance, 0.0) / n)
    return {
        "mean": mean,
        "hac_se": se,
        "t_stat": mean / se if se > 0 else np.nan,
        "ci_low": mean - 1.96 * se,
        "ci_high": mean + 1.96 * se,
    }


def slice_period(series: pd.Series | pd.DataFrame, start: str, end: str | None):
    return series.loc[start:end] if end else series.loc[start:]


def performance_metrics(
    returns: pd.Series,
    turnover: pd.Series,
    exposures: pd.DataFrame,
    cost_drag: pd.Series | None = None,
) -> dict[str, float | int | str]:
    r = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        return {"months": 0}
    turnover = turnover.reindex(r.index).fillna(0.0)
    exposures = exposures.reindex(r.index)
    wealth = (1.0 + r).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1.0) - 1.0
    years = len(r) / 12.0
    annual_vol = r.std() * np.sqrt(12.0)
    downside = np.sqrt((r.clip(upper=0) ** 2).mean()) * np.sqrt(12.0)
    cagr = wealth.iloc[-1] ** (1.0 / years) - 1.0 if wealth.iloc[-1] > 0 else np.nan
    return {
        "start": r.index.min().date(),
        "end": r.index.max().date(),
        "months": len(r),
        "cumulative_return": wealth.iloc[-1] - 1.0,
        "cagr": cagr,
        "annual_mean": r.mean() * 12.0,
        "annual_volatility": annual_vol,
        "sharpe_0rf": r.mean() * 12.0 / annual_vol if annual_vol > 0 else np.nan,
        "sortino_0rf": r.mean() * 12.0 / downside if downside > 0 else np.nan,
        "max_drawdown": drawdown.min(),
        "calmar": cagr / abs(drawdown.min()) if drawdown.min() < 0 and np.isfinite(cagr) else np.nan,
        "hit_rate": (r > 0).mean(),
        "annual_turnover": turnover.mean() * 12.0,
        "annual_cost_drag": cost_drag.reindex(r.index).mean() * 12.0 if cost_drag is not None else 0.0,
        "average_gross_exposure": exposures["gross_exposure"].mean(),
        "average_net_exposure": exposures["net_exposure"].mean(),
        "average_long_exposure": exposures["long_exposure"].mean(),
        "average_short_exposure": exposures["short_exposure"].mean(),
        "average_active_instruments": exposures["active_instruments"].mean(),
    }


def exposure_frame(simulation: dict) -> pd.DataFrame:
    return pd.DataFrame({
        "gross_exposure": simulation["gross_exposure"],
        "net_exposure": simulation["net_exposure"],
        "long_exposure": simulation["long_exposure"],
        "short_exposure": simulation["short_exposure"],
        "active_instruments": simulation["active_instruments"],
    })


def evaluate_cases(
    strategy: str,
    setting: str,
    simulation: dict,
    cases: dict[str, pd.Series],
    cost_drags: dict[str, pd.Series],
) -> pd.DataFrame:
    rows = []
    exposures = exposure_frame(simulation)
    for period, (start, end) in PERIODS.items():
        for cost_case, series in cases.items():
            subset = slice_period(series, start, end)
            if subset.empty:
                continue
            rows.append({
                "strategy": strategy,
                "setting": setting,
                "period": period,
                "cost_case": cost_case,
                **performance_metrics(
                    subset,
                    simulation["turnover"],
                    exposures,
                    cost_drags.get(cost_case),
                ),
            })
    return pd.DataFrame(rows)


def hac_incremental_tests(
    monthly_returns: pd.DataFrame,
    comparisons: list[tuple[str, str, str]],
) -> pd.DataFrame:
    """comparisons contain (label, candidate column, baseline column)."""
    rows = []
    for period, (start, end) in PERIODS.items():
        if period == "full_1976_2025":
            continue
        for label, candidate, baseline in comparisons:
            paired = slice_period(monthly_returns[[candidate, baseline]], start, end).dropna()
            if paired.empty:
                continue
            difference = paired[candidate] - paired[baseline]
            stats = hac_mean_statistics(difference)
            rows.append({
                "comparison": label,
                "candidate": candidate,
                "baseline": baseline,
                "period": period,
                "months": len(difference),
                "annualized_incremental_return": stats["mean"] * 12,
                "annualized_hac_se": stats["hac_se"] * 12,
                "annualized_ci_low": stats["ci_low"] * 12,
                "annualized_ci_high": stats["ci_high"] * 12,
                "hac_t_stat": stats["t_stat"],
            })
    return pd.DataFrame(rows)


def regime_attribution(
    panel: pd.DataFrame,
    formed_weights: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    keys = pd.MultiIndex.from_frame(panel[["formation_date", "instrument"]])
    base = panel[["formation_date", "realized_date", "period", "instrument", "asset_class", "regime", "agreement", "next_return"]].copy()
    rows = []
    for strategy, weights in formed_weights.items():
        stacked = weights.stack(dropna=False)
        stacked.index.names = ["formation_date", "instrument"]
        local = base.copy()
        local["weight"] = stacked.reindex(keys).fillna(0.0).to_numpy()
        local["contribution"] = local["weight"] * local["next_return"]
        local["gross"] = local["weight"].abs()
        grouped = local.groupby(["period", "asset_class", "regime"], observed=True).agg(
            total_contribution=("contribution", "sum"),
            average_monthly_contribution=("contribution", "mean"),
            average_gross_weight=("gross", "mean"),
            instrument_months=("instrument", "size"),
        ).reset_index()
        grouped.insert(0, "strategy", strategy)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True)
