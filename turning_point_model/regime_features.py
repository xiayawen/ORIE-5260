"""Regime features and Method 1 diagnostics built from the shared audit panel."""

from __future__ import annotations

import numpy as np
import pandas as pd

from turning_point_model.evaluation import hac_mean_statistics


REGIMES = ("Bull", "Correction", "Bear", "Rebound")


def turning_point_regimes(
    returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Classify 2-month versus 12-month momentum states."""
    slow = np.sign(returns.rolling(12, min_periods=12).sum())
    fast = np.sign(returns.rolling(2, min_periods=2).sum())
    regimes = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=object)
    regimes = regimes.mask(slow.gt(0) & fast.ge(0), "Bull")
    regimes = regimes.mask(slow.gt(0) & fast.lt(0), "Correction")
    regimes = regimes.mask(slow.lt(0) & fast.le(0), "Bear")
    regimes = regimes.mask(slow.lt(0) & fast.gt(0), "Rebound")
    return regimes, slow, fast


def disagreement_from_signals(slow: pd.DataFrame, fast: pd.DataFrame) -> pd.DataFrame:
    """True only when the non-zero fast and slow signals have opposite signs."""
    return slow.mul(fast).lt(0)


def enrich_panel(
    panel: pd.DataFrame,
    returns: pd.DataFrame,
    baseline: dict,
) -> pd.DataFrame:
    """Add the auditable fields required by the turning-point specification."""
    regimes, slow, fast = turning_point_regimes(returns)
    momentum_12m = returns.rolling(12, min_periods=12).sum()
    momentum_2m = returns.rolling(2, min_periods=2).sum()
    disagreement = disagreement_from_signals(slow, fast)

    out = panel.copy()
    keys = pd.MultiIndex.from_frame(out[["formation_date", "instrument"]])

    def values(frame: pd.DataFrame) -> np.ndarray:
        stacked = frame.stack(dropna=False)
        stacked.index.names = ["formation_date", "instrument"]
        return stacked.reindex(keys).to_numpy()

    out["monthly_return"] = out["current_return"]
    out["momentum_12m"] = values(momentum_12m)
    out["momentum_2m"] = values(momentum_2m)
    out["slow_signal"] = values(slow)
    out["fast_signal"] = values(fast)
    out["disagreement_flag"] = values(disagreement).astype(bool)
    out["baseline_weight"] = out["formation_weight"]
    out["instrument_volatility"] = values(baseline["vol"])
    out["position_direction"] = np.where(out["slow_signal"] > 0, "Long", "Short")
    # Verify the imported panel and independently derived features agree.
    if not (out["regime"].to_numpy() == values(regimes)).all():
        raise AssertionError("Imported four-state panel does not match regenerated regimes")
    if not np.allclose(out["signal_12m"], out["slow_signal"], equal_nan=True):
        raise AssertionError("Slow signal mismatch in turning-point panel")
    if not np.allclose(out["signal_2m"], out["fast_signal"], equal_nan=True):
        raise AssertionError("Fast signal mismatch in turning-point panel")
    return out


def add_disagreement_duration(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["instrument", "formation_date"]).copy()
    durations = pd.Series(0, index=out.index, dtype=int)
    for _, group in out.groupby("instrument", sort=False):
        run = 0
        for idx, flag in zip(group.index, group["disagreement_flag"]):
            run = run + 1 if bool(flag) else 0
            durations.at[idx] = run
    out["disagreement_duration_months"] = durations
    return out.sort_values(["formation_date", "instrument"]).reset_index(drop=True)


def regime_counts(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby(["period", "regime"], observed=True).agg(
        instrument_months=("instrument", "size"),
        observed_next_returns=("next_return_observed", "sum"),
        average_gross_weight=("formation_gross_weight", "mean"),
    ).reset_index()
    total = grouped.groupby("period")["instrument_months"].transform("sum")
    grouped["instrument_month_share"] = grouped["instrument_months"] / total
    return grouped


def transition_frequencies(panel: pd.DataFrame) -> pd.DataFrame:
    ordered = panel.sort_values(["instrument", "formation_date"]).copy()
    ordered["previous_regime"] = ordered.groupby("instrument")["regime"].shift(1)
    ordered["previous_date"] = ordered.groupby("instrument")["formation_date"].shift(1)
    consecutive = (
        ordered["formation_date"].dt.to_period("M")
        - ordered["previous_date"].dt.to_period("M")
    ).apply(lambda x: x.n if pd.notna(x) else np.nan)
    valid = ordered.loc[consecutive.eq(1) & ordered["previous_regime"].notna()].copy()
    result = valid.groupby(["period", "previous_regime", "regime"], observed=True).size().rename("transitions").reset_index()
    result["probability_from_previous_regime"] = result["transitions"] / result.groupby(
        ["period", "previous_regime"]
    )["transitions"].transform("sum")
    return result


def duration_diagnostics(panel: pd.DataFrame) -> pd.DataFrame:
    subset = panel.loc[panel["disagreement_flag"]].copy()
    rows = []
    for keys, group in subset.groupby(["period", "disagreement_duration_months"], observed=True):
        period, duration = keys
        monthly = group.groupby("realized_date").agg(
            contribution=("subsequent_baseline_contribution", "sum"),
            gross=("formation_gross_weight", "sum"),
            instruments=("instrument", "size"),
        )
        outcome = monthly["contribution"] / monthly["gross"].replace(0, np.nan)
        stats = hac_mean_statistics(outcome)
        rows.append({
            "period": period,
            "disagreement_duration_months": int(duration),
            "instrument_months": len(group),
            "months": len(monthly),
            "average_instruments": monthly["instruments"].mean(),
            "annualized_return_per_gross": stats["mean"] * 12,
            "annualized_hac_se": stats["hac_se"] * 12,
            "hac_t_stat": stats["t_stat"],
        })
    return pd.DataFrame(rows)


def direction_diagnostics(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in panel.groupby(["period", "position_direction", "agreement"], observed=True):
        period, direction, agreement = keys
        monthly = group.groupby("realized_date").agg(
            contribution=("subsequent_baseline_contribution", "sum"),
            gross=("formation_gross_weight", "sum"),
        )
        outcome = monthly["contribution"] / monthly["gross"].replace(0, np.nan)
        stats = hac_mean_statistics(outcome)
        rows.append({
            "period": period,
            "position_direction": direction,
            "agreement": agreement,
            "instrument_months": len(group),
            "annualized_return_per_gross": stats["mean"] * 12,
            "annualized_hac_se": stats["hac_se"] * 12,
            "hac_t_stat": stats["t_stat"],
            "directional_hit_rate": (group["subsequent_unit_tsmom_payoff"] > 0).mean(),
        })
    return pd.DataFrame(rows)


def correction_rebound_gate(panel: pd.DataFrame) -> pd.DataFrame:
    """Require a significant and sign-stable training difference for M1-C."""
    train = panel.loc[
        panel["realized_date"].between("1976-01-01", "1997-12-31")
        & panel["regime"].isin(["Correction", "Rebound"])
    ].copy()

    def paired_difference(frame: pd.DataFrame) -> tuple[pd.Series, dict]:
        monthly = frame.groupby(["realized_date", "regime"]).agg(
            contribution=("subsequent_baseline_contribution", "sum"),
            gross=("formation_gross_weight", "sum"),
        )
        monthly["return_per_gross"] = monthly["contribution"] / monthly["gross"].replace(0, np.nan)
        pivot = monthly["return_per_gross"].unstack("regime")
        paired = pivot[["Correction", "Rebound"]].dropna()
        difference = paired["Rebound"] - paired["Correction"]
        return difference, hac_mean_statistics(difference)

    full_diff, stats = paired_difference(train)
    first_diff, _ = paired_difference(train.loc[train["realized_date"] <= "1986-12-31"])
    second_diff, _ = paired_difference(train.loc[train["realized_date"] >= "1987-01-01"])
    first = first_diff.mean() * 12
    second = second_diff.mean() * 12
    stable = np.isfinite(first) and np.isfinite(second) and np.sign(first) == np.sign(second)
    passes = bool(np.isfinite(stats["t_stat"]) and abs(stats["t_stat"]) >= 1.96 and stable)
    return pd.DataFrame([{
        "training_start": "1976-01-01",
        "training_end": "1997-12-31",
        "paired_months": len(full_diff),
        "rebound_minus_correction_annualized": stats["mean"] * 12,
        "annualized_hac_se": stats["hac_se"] * 12,
        "hac_t_stat": stats["t_stat"],
        "ci_low": stats["ci_low"] * 12,
        "ci_high": stats["ci_high"] * 12,
        "first_half_difference": first,
        "second_half_difference": second,
        "same_sign_across_halves": stable,
        "gate_threshold": "abs(HAC t) >= 1.96 and same sign in 1976-1986 and 1987-1997",
        "passes_gate": passes,
    }])
