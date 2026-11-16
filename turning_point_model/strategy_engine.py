"""Portfolio construction and execution helpers for turning-point Method 1."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cost_aware_rebalance import rebalance_path
from covariance_risk_validation import predict
from portfolio_volatility_targeting import GROSS_CAP, target_weights
from strategy_backtest_adj import expanding_volatility
from transaction_cost_model import (
    DAILY_DIR,
    DEFAULT_PARAMETERS,
    TRADING_DAYS,
    cost_breakdown,
    instrument_adv_usd,
    trade_weights,
)


TARGET_VOLATILITY = 0.10
SCALE_CAP = 2.0
FLAT_COST_BPS = (0, 2, 10)


def binary_reduction_weights(
    baseline_weights: pd.DataFrame,
    disagreement: pd.DataFrame,
    alpha: float,
) -> pd.DataFrame:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must lie in [0, 1]")
    flag = disagreement.reindex_like(baseline_weights).fillna(False).astype(float)
    return baseline_weights.fillna(0.0) * (1.0 - alpha * flag)


def fast_reversal_weights(
    baseline_weights: pd.DataFrame,
    disagreement: pd.DataFrame,
    beta: float,
) -> pd.DataFrame:
    if not 0.5 < beta <= 1.0:
        raise ValueError("reversal beta must lie in (0.5, 1]")
    flag = disagreement.reindex_like(baseline_weights).fillna(False).astype(float)
    return baseline_weights.fillna(0.0) * (1.0 - 2.0 * beta * flag)


def simulate(
    returns: pd.DataFrame,
    formed: pd.DataFrame,
    executed: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame | pd.Series]:
    formed = formed.reindex(index=returns.index, columns=returns.columns).fillna(0.0)
    executed = (
        formed.shift(1).fillna(0.0)
        if executed is None
        else executed.reindex(index=returns.index, columns=returns.columns).fillna(0.0)
    )
    instrument_returns = executed * returns.fillna(0.0)
    gross = instrument_returns.sum(axis=1)
    trades = trade_weights(executed, returns, "drift")
    return {
        "formed": formed,
        "executed": executed,
        "instrument_returns": instrument_returns,
        "gross": gross,
        "trades": trades,
        "turnover": trades.sum(axis=1),
        "gross_exposure": executed.abs().sum(axis=1),
        "net_exposure": executed.sum(axis=1),
        "long_exposure": executed.clip(lower=0).sum(axis=1),
        "short_exposure": -executed.clip(upper=0).sum(axis=1),
        "active_instruments": executed.ne(0).sum(axis=1),
    }


def flat_cost_returns(simulation: dict, bps: int) -> pd.Series:
    return simulation["gross"] - simulation["turnover"] * bps / 10_000.0


def detailed_cost_context(
    returns: pd.DataFrame,
    asset_map: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    classes = asset_map.set_index("ID")["AssetClass"].reindex(returns.columns)
    # transaction_cost_model uses the newer pandas alias "ME". The project
    # environment uses the equivalent legacy alias "M", so keep this small
    # input adapter local while reusing the existing ADV and cost formulas.
    volume_data = {}
    for instrument in returns.columns:
        path = DAILY_DIR / f"{instrument}.csv"
        if not path.exists():
            continue
        daily = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        contract_volume = pd.to_numeric(daily["Volume"], errors="coerce").where(lambda x: x > 0)
        trailing = contract_volume.rolling(TRADING_DAYS, min_periods=TRADING_DAYS // 2).median()
        volume_data[instrument] = trailing.resample("M").last().reindex(
            returns.index, method="ffill", limit=1
        )
    volume = pd.DataFrame(volume_data, index=returns.index).reindex(columns=returns.columns)
    adv, _ = instrument_adv_usd(volume, classes, DEFAULT_PARAMETERS)
    return adv, classes


def detailed_cost_returns(
    simulation: dict,
    returns: pd.DataFrame,
    formation_volatility: pd.DataFrame,
    adv: pd.DataFrame,
    asset_class: pd.Series,
) -> tuple[pd.Series, pd.DataFrame]:
    costs, _ = cost_breakdown(
        simulation["executed"],
        formation_volatility,
        adv,
        asset_class,
        DEFAULT_PARAMETERS,
        returns,
    )
    return simulation["gross"] - costs["total"], costs


def ewma_covariance_target(
    returns: pd.DataFrame,
    formed: pd.DataFrame,
    baseline_volatility: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply the repository's 10% EWMA-covariance target and 4x/2x caps."""
    volatility = baseline_volatility if baseline_volatility is not None else expanding_volatility(returns)
    forecasts, diagnostics = predict(returns, formed, volatility)
    forecast = forecasts["ewma_covariance"].reindex(formed.index)
    targeted, scaling = target_weights(formed, forecast)
    if targeted.abs().sum(axis=1).max() > GROSS_CAP + 1e-9:
        raise AssertionError("Matched-risk weights violate the 4x gross cap")
    return targeted, scaling, diagnostics


def apply_band_25(
    formed: pd.DataFrame,
    returns: pd.DataFrame,
    gross_cap: float | None = None,
) -> pd.DataFrame:
    """Use the existing path-dependent ±25% no-trade band symmetrically."""
    return rebalance_path(formed, returns, ("band", 0.25), gross_cap)
