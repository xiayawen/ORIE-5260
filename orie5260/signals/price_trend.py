"""The course baseline's daily price trend, used as the 30% trend sleeve."""
import numpy as np
from orie5260.common.data import rebalance_dates
from orie5260.portfolio.risk_model import normalize_sleeve


def daily_signal_and_vol(daily, dates):
    log_return = np.log1p(daily)
    trail = log_return.rolling(252, min_periods=200).sum()
    vol = daily.rolling(252, min_periods=200).std() * np.sqrt(252)
    live = daily.notna().rolling(5, min_periods=1).sum().gt(0)
    return np.sign(trail).where(live).loc[dates], vol.where(live).loc[dates]


def trend_sleeve(daily, dates, covariance):
    signal, volatility = daily_signal_and_vol(daily, dates)
    eligible = signal.notna() & volatility.notna() & signal.ne(0)
    raw = signal / volatility
    raw = raw.where(eligible).div(eligible.sum(axis=1).replace(0, np.nan), axis=0)
    return normalize_sleeve(raw, eligible.to_numpy(), covariance), eligible
