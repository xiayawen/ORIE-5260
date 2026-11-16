"""Causal macro features and confirmation gates used by the final model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from economic_trend import (
    FX_HOME_FLIP,
    RATE_FUTURES_IN_FX,
    SIGNS,
    SMOOTH_MONTHS,
    macro_signals,
    macro_universe,
)


REQUIRED_MACRO_FILES = ("INDPRO.csv", "CPIAUCSL.csv", "GS2.csv")


def validate_macro_directory(macro_dir: str | Path) -> Path:
    path = Path(macro_dir).expanduser().resolve()
    missing = [name for name in REQUIRED_MACRO_FILES if not (path / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Macro confirmation requires {missing} in {path}. "
            "Use --macro-dir to provide the FRED-style CSV directory."
        )
    return path


def equal_weight_opposition_vote(
    theme_directions: dict[str, pd.DataFrame],
    baseline_signal: pd.DataFrame,
    eligible_instruments: pd.Index | list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Calculate a strict-majority opposition vote across available themes."""
    slow = baseline_signal.copy()
    opposition_count = pd.DataFrame(0, index=slow.index, columns=slow.columns, dtype=int)
    available_count = pd.DataFrame(0, index=slow.index, columns=slow.columns, dtype=int)
    active_direction = slow.notna() & slow.ne(0.0)

    for frame in theme_directions.values():
        mapped = frame.reindex_like(slow)
        available = mapped.notna() & active_direction
        opposition = mapped.mul(slow).lt(0.0) & available
        available_count = available_count.add(available.astype(int), fill_value=0).astype(int)
        opposition_count = opposition_count.add(opposition.astype(int), fill_value=0).astype(int)

    eligible = available_count.gt(0)
    if eligible_instruments is not None:
        universe = pd.Index(eligible_instruments)
        eligible.loc[:, ~eligible.columns.isin(universe)] = False

    opposition_share = opposition_count.div(available_count.where(available_count.gt(0)))
    opposition_share = opposition_share.where(eligible)
    opposition_flag = opposition_share.gt(0.5) & eligible
    return {
        "opposition_vote_count": opposition_count.where(eligible),
        "available_theme_count": available_count.where(eligible),
        "opposition_vote_share": opposition_share,
        "macro_vote_eligible": eligible,
        "macro_vote_opposes_baseline": opposition_flag,
    }


def four_of_five_opposition(features: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Confirm only when at least four available themes oppose the baseline."""
    opposition = features["opposition_vote_count"]
    available = features["available_theme_count"]
    eligible = features["macro_vote_eligible"].reindex_like(opposition).fillna(False)
    return opposition.ge(4) & available.ge(4) & eligible


def economic_confirmation_features(
    returns: pd.DataFrame,
    asset_map: pd.DataFrame,
    baseline_signal: pd.DataFrame,
    macro_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    """Build causal mapped macro directions and opposition flags."""
    path = validate_macro_directory(macro_dir)
    themes = macro_signals(returns, path).rolling(SMOOTH_MONTHS, min_periods=1).mean()

    classes = asset_map.set_index("ID")["AssetClass"].reindex(returns.columns).copy()
    classes.loc[classes.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    if classes.isna().any():
        raise ValueError(f"Missing asset classes for {classes[classes.isna()].index.tolist()}")

    directional = {}
    for theme in SIGNS.index:
        signs = pd.Series(
            {
                instrument: SIGNS.loc[theme, classes[instrument]]
                * (FX_HOME_FLIP if classes[instrument] == "FX" else 1)
                for instrument in returns.columns
            }
        )
        directional[theme] = pd.DataFrame(
            np.outer(themes[theme].to_numpy(), signs.reindex(returns.columns).to_numpy()),
            index=returns.index,
            columns=returns.columns,
        )

    stacked = pd.concat(directional, axis=1)
    economic_score = pd.concat(
        {theme: frame.stack(dropna=False) for theme, frame in directional.items()},
        axis=1,
    ).mean(axis=1, skipna=True).unstack()
    economic_score = economic_score.reindex(index=returns.index, columns=returns.columns)
    eligible = economic_score.notna()
    universe = macro_universe(returns.columns)
    eligible.loc[:, ~eligible.columns.isin(universe)] = False
    economic_score = economic_score.where(eligible)

    slow = baseline_signal.reindex_like(returns)
    opposition = economic_score.mul(slow).lt(0.0) & slow.ne(0.0) & eligible
    support = economic_score.mul(slow).gt(0.0) & slow.ne(0.0) & eligible
    vote = equal_weight_opposition_vote(directional, slow, universe)
    return {
        "theme_signals": themes,
        "theme_directions": stacked,
        "economic_score": economic_score,
        "macro_eligible": eligible,
        "macro_opposes_baseline": opposition,
        "macro_supports_baseline": support,
        **vote,
    }


def macro_confirmed_binary_weights(
    baseline_weights: pd.DataFrame,
    turning_flag: pd.DataFrame,
    macro_opposition: pd.DataFrame,
    alpha: float,
) -> pd.DataFrame:
    """Reduce positions only where turning-point and macro flags both hold."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must lie in [0, 1]")
    confirmed = turning_flag.reindex_like(baseline_weights).fillna(False) & macro_opposition.reindex_like(
        baseline_weights
    ).fillna(False)
    return baseline_weights.fillna(0.0) * (1.0 - alpha * confirmed.astype(float))
