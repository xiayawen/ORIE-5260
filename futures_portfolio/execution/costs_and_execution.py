"""Cost-aware 21-day execution and daily NAV marking for the final strategy."""
import numpy as np
import pandas as pd

TRADE_BPS = 2.0
ROLLS_PER_YEAR = 4.0
TRADING_DAYS_PER_YEAR = 252.0
TRACKING_AVERSION = 5.0


def mark_daily(daily, formed):
    """A formation-close trade first earns the following day's return."""
    calendar = daily.loc[formed.index.min():formed.index.max()].index
    returns = daily.reindex(calendar).fillna(0.0)
    lookup = {date: formed.loc[date].to_numpy(dtype=float) for date in formed.index}
    position = np.zeros(daily.shape[1])
    pending_cost = 0.0
    rows = []
    daily_roll_rate = TRADE_BPS / 1e4 * ROLLS_PER_YEAR / TRADING_DAYS_PER_YEAR
    for date, row in zip(calendar, returns.to_numpy()):
        held = position.copy()
        gross = float(held @ row)
        if gross <= -1: raise ValueError(f"Insolvent portfolio on {date.date()}")
        drift = held * (1 + row) / (1 + gross)
        trade_cost = pending_cost
        pending_cost = 0.0
        turnover = 0.0
        position = drift
        if date in lookup:
            target = lookup[date]
            turnover = float(np.abs(target - drift).sum())
            pending_cost = turnover * TRADE_BPS / 1e4
            position = target
        roll_cost = float(np.abs(held).sum()) * daily_roll_rate
        net = (1 + gross) * (1 - trade_cost - roll_cost) - 1
        rows.append((gross, net, turnover, trade_cost, roll_cost,
                     float(np.abs(held).sum()), float(held.sum())))
    return pd.DataFrame(rows, index=calendar, columns=[
        "gross_return", "net_return", "turnover", "trade_cost", "roll_cost",
        "gross_exposure", "net_exposure"])
