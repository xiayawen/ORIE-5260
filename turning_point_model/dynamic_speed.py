"""State-dependent slow/fast trend blending without future information.

The implementation follows Appendix C of Goulding, Harvey and Mazzoleni
(2023), *Breaking Bad Trends*.  Parameters are estimated once from a supplied
training sample and can then be frozen for later portfolio evaluation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


STATES = ("Bull", "Correction", "Bear", "Rebound")


def momentum_states(
    returns: pd.DataFrame,
    slow_months: int = 12,
    fast_months: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return observable month-end state and binary slow/fast directions."""
    slow_value = returns.rolling(slow_months, min_periods=slow_months).sum()
    fast_value = returns.rolling(fast_months, min_periods=fast_months).sum()
    slow = slow_value.ge(0).astype(float).mul(2).sub(1).where(slow_value.notna())
    fast = fast_value.ge(0).astype(float).mul(2).sub(1).where(fast_value.notna())

    state = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=object)
    state = state.mask(slow.eq(1) & fast.eq(1), "Bull")
    state = state.mask(slow.eq(1) & fast.eq(-1), "Correction")
    state = state.mask(slow.eq(-1) & fast.eq(-1), "Bear")
    state = state.mask(slow.eq(-1) & fast.eq(1), "Rebound")
    return state, slow, fast


def _mixing_weight(
    conditional: pd.Series,
    normalizer: float,
    minimum_observations: int,
) -> tuple[float, bool]:
    x = conditional.dropna().astype(float)
    if len(x) < minimum_observations or not np.isfinite(normalizer) or abs(normalizer) < 1e-12:
        return 0.5, True
    second_moment = float(np.mean(np.square(x)))
    if not np.isfinite(second_moment) or second_moment <= 1e-16:
        return 0.5, True
    estimate = 0.5 * (1.0 - float(x.mean()) / (normalizer * second_moment))
    if not np.isfinite(estimate):
        return 0.5, True
    return float(np.clip(estimate, 0.0, 1.0)), False


def fit_frozen_mixing_parameters(
    returns: pd.DataFrame,
    training_end: str | pd.Timestamp = "2004-12-31",
    minimum_state_observations: int = 12,
    slow_months: int = 12,
    fast_months: int = 2,
) -> pd.DataFrame:
    """Estimate per-instrument Correction/Rebound fast-signal weights.

    Only outcomes fully contained in the sample ending at ``training_end`` are
    used.  A neutral 0.5 blend is used when the published moment estimator is
    not identified or a state has insufficient observations.
    """
    training = returns.loc[:pd.Timestamp(training_end)].copy()
    state, _, _ = momentum_states(training, slow_months, fast_months)
    next_return = training.shift(-1)
    rows: list[dict] = []

    for instrument in training.columns:
        s = state[instrument]
        y = next_return[instrument]
        samples = {name: y.where(s.eq(name)).dropna() for name in STATES}
        agreement = pd.concat([samples["Bull"], samples["Bear"]])
        agreement_second = float(np.mean(np.square(agreement))) if len(agreement) else np.nan
        agreement_count = len(samples["Bull"]) + len(samples["Bear"])
        if agreement_count and np.isfinite(agreement_second) and agreement_second > 1e-16:
            p_bull = len(samples["Bull"]) / agreement_count
            p_bear = len(samples["Bear"]) / agreement_count
            normalizer = (
                p_bull * float(samples["Bull"].mean())
                - p_bear * float(samples["Bear"].mean())
            ) / agreement_second
        else:
            normalizer = np.nan

        correction, correction_fallback = _mixing_weight(
            samples["Correction"], normalizer, minimum_state_observations
        )
        rebound, rebound_fallback = _mixing_weight(
            samples["Rebound"], normalizer, minimum_state_observations
        )
        rows.append(
            {
                "instrument": instrument,
                "correction_fast_weight": correction,
                "rebound_fast_weight": rebound,
                "normalizer_C": normalizer,
                "bull_observations": len(samples["Bull"]),
                "correction_observations": len(samples["Correction"]),
                "bear_observations": len(samples["Bear"]),
                "rebound_observations": len(samples["Rebound"]),
                "correction_fallback": correction_fallback,
                "rebound_fallback": rebound_fallback,
                "training_end": pd.Timestamp(training_end),
            }
        )
    return pd.DataFrame(rows).set_index("instrument")


def dynamic_speed_direction(
    returns: pd.DataFrame,
    parameters: pd.DataFrame,
    slow_months: int = 12,
    fast_months: int = 2,
) -> pd.DataFrame:
    """Construct the frozen state-dependent slow/fast direction in [-1, 1]."""
    state, slow, fast = momentum_states(returns, slow_months, fast_months)
    correction = parameters["correction_fast_weight"].reindex(returns.columns).fillna(0.5)
    rebound = parameters["rebound_fast_weight"].reindex(returns.columns).fillna(0.5)

    result = slow.copy()
    correction_mix = slow.mul(1.0 - correction, axis=1) + fast.mul(correction, axis=1)
    rebound_mix = slow.mul(1.0 - rebound, axis=1) + fast.mul(rebound, axis=1)
    result = result.mask(state.eq("Correction"), correction_mix)
    result = result.mask(state.eq("Rebound"), rebound_mix)
    return result.where(slow.notna() & fast.notna())
