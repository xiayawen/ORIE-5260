"""Causally dated inputs for the selected 42-input, 11%-target portfolio."""
import numpy as np
import pandas as pd

from futures_portfolio.common.data import asset_map, daily_returns, monthly_returns, rebalance_dates
from futures_portfolio.portfolio.engine import risk_normalize
from futures_portfolio.portfolio.risk_model import monthly_ewma_vol, monthly_covariance_cube, daily_covariance_cube
from futures_portfolio.signals.price_trend import daily_signal_and_vol
from futures_portfolio.signals.macro_trend import macro_sleeve
from futures_portfolio.signals.negative_skew import skew_sleeve

BUDGETS = np.array([.30, .20, .20, .30])


def inverse_vol_weight(direction, vol):
    raw = direction / vol
    valid = raw.notna() & direction.ne(0)
    return raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)


def dated_sleeves(monthly, monthly_basis, dates, daily_core, covariance, eligible):
    """Bring monthly macro/skew signals to formation dates without future data."""
    aligned = []
    for sleeve in range(4):
        frame = pd.DataFrame(monthly_basis[:, sleeve], index=monthly.index, columns=monthly.columns)
        aligned.append(frame.reindex(dates, method="ffill").fillna(0).to_numpy())
    old_core = aligned[0]
    pieces = [daily_core]
    for sleeve in aligned[1:]:
        active = np.abs(sleeve - old_core).sum(axis=1) > 1e-12
        scaled = risk_normalize(sleeve * eligible, covariance)
        pieces.append(np.where(active[:, None], scaled, daily_core))
    return np.stack(pieces, axis=1)


def build_portfolio_inputs():
    monthly = monthly_returns()
    daily = daily_returns(list(monthly.columns))
    dates = rebalance_dates(daily.index)
    dates = dates[(dates >= pd.Timestamp("1975-01-01")) & (dates <= monthly.index.max())]
    slow, vol = daily_signal_and_vol(daily, dates)
    eligible = (slow.notna() & vol.notna() & slow.ne(0)).to_numpy()
    covariance = daily_covariance_cube(daily, dates, slow.notna() & vol.notna() & slow.ne(0))
    daily_core = risk_normalize(inverse_vol_weight(slow, vol).to_numpy() * eligible, covariance)

    classes = asset_map().set_index("ID")["AssetClass"].reindex(monthly.columns)
    monthly_vol = monthly_ewma_vol(monthly)
    live = monthly.notna().rolling(12, min_periods=12).sum().eq(12)
    sleeve_vol = monthly_vol.where(live)
    monthly_eligible = sleeve_vol.notna().to_numpy()
    monthly_covariance = monthly_covariance_cube(monthly)
    continuous = (monthly.rolling(12, min_periods=12).sum() / monthly_vol).clip(-1, 1)
    monthly_core = risk_normalize(
        inverse_vol_weight(continuous, sleeve_vol).to_numpy() * monthly_eligible,
        monthly_covariance,
    )
    macro = macro_sleeve(monthly, classes, sleeve_vol, monthly_covariance, monthly_eligible)
    skew = skew_sleeve(monthly, classes, sleeve_vol, monthly_covariance, monthly_eligible)
    pieces = [monthly_core]
    for sleeve in (macro, skew):
        pieces.append(np.where((np.abs(sleeve).sum(axis=1) > 0)[:, None], sleeve, monthly_core))
    # The fourth sleeve is replaced with the frozen selected-42 forecast by the runner.
    pieces.append(monthly_core)
    monthly_basis = np.stack(pieces, axis=1)
    basis = dated_sleeves(monthly, monthly_basis, dates, daily_core, covariance, eligible)
    return dict(monthly=monthly, daily=daily, dates=dates, covariance=covariance,
                eligible=eligible, daily_core=daily_core, basis=basis)
