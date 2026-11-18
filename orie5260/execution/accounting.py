"""Netted period-return accounting, retained for execution diagnostics."""
import numpy as np


def rebalance_metrics(formed,returns,trade_bps=2.):
    executed=np.zeros_like(formed);executed[1:]=formed[:-1]
    gross=np.sum(executed*returns,axis=1)
    prior=np.zeros_like(executed);prior[1:]=executed[:-1]
    lagged=np.zeros_like(returns);lagged[1:]=returns[:-1]
    prior_gross=np.sum(prior*lagged,axis=1)
    if np.any(1+prior_gross<=0):raise ValueError("Insolvent portfolio in drift calculation")
    drift=prior*(1+lagged)/(1+prior_gross[:,None])
    turnover=np.abs(executed-drift).sum(axis=1)
    roll=np.abs(executed).sum(axis=1)*trade_bps/1e4*4/12
    trade=turnover*trade_bps/1e4
    return dict(executed=executed,gross=gross,turnover=turnover,roll_cost=roll,trade_cost=trade,
                net=gross-roll-trade,gross_exposure=np.abs(executed).sum(axis=1),
                net_exposure=executed.sum(axis=1))

