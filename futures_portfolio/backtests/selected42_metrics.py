"""Matched 21-business-day endpoint metrics for baseline comparisons."""
import numpy as np


def drawdown_series(returns):
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax().clip(lower=1) - 1


def measures(returns):
    wealth = (1 + returns).cumprod()
    vol = returns.std() * np.sqrt(12)
    return {
        "periods": len(returns),
        "annual_mean_net_return": returns.mean() * 12,
        "annual_volatility": vol,
        "sharpe_zero_rf": returns.mean() * 12 / vol,
        "cagr": wealth.iloc[-1] ** (12 / len(returns)) - 1,
        "max_endpoint_drawdown": drawdown_series(returns).min(),
    }
