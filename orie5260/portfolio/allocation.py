"""Bounded signal-budget fitting on the final daily full-rebalance engine.

The objective sees only a physically truncated daily history. It uses actual
netted trading/roll costs, historical gross variance and a fixed prior, with the
same 10% ex-ante scaling as the final strategy. It does not change execution.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from orie5260.portfolio.engine import risk_normalize

FIXED = np.array([.3, .2, .2, .3])


class DailyAllocationEngine:
    """Vectorized exact counterpart of mark_daily for full target rebalances.

    Precomputed within-holding-period price relatives allow many allocation
    evaluations without a Python loop over every daily observation. Charges and
    drift retain the submitted engine's convention, including next-day costs.
    """
    def __init__(self, daily, dates, basis, covariance, end=None):
        end = pd.Timestamp(end) if end is not None else dates.max()
        keep = dates <= end
        self.dates = dates[keep]
        self.basis = np.asarray(basis)[keep]
        self.covariance = np.asarray(covariance)[keep]
        self.daily = daily.loc[self.dates.min():end].fillna(0.)
        self.index = self.daily.index
        self.r = self.daily.to_numpy(dtype=float)
        if np.any(self.r <= -1):
            raise ValueError('Daily price returns must exceed -100%')
        self.locations = self.index.get_indexer(self.dates)
        if np.any(self.locations < 0):
            raise ValueError('Formation date missing from daily calendar')
        day = np.arange(len(self.index))
        self.owner = np.searchsorted(self.locations, day, side='left') - 1
        self.live = self.owner >= 0
        owner = np.maximum(self.owner, 0)
        cumulative_log = np.log1p(self.r).cumsum(axis=0)
        previous_log = np.vstack([np.zeros(self.r.shape[1]), cumulative_log[:-1]])
        self.growth_before = np.exp(previous_log - cumulative_log[self.locations[owner]])
        self.growth_before[~self.live] = 1.

    def targets(self, allocation):
        allocation = np.asarray(allocation)
        raw = (np.einsum('tki,k->ti', self.basis, allocation) if allocation.ndim == 1
               else np.einsum('tki,tk->ti', self.basis, allocation))
        return risk_normalize(raw, self.covariance, .10)

    def evaluate(self, allocation):
        return self.evaluate_targets(self.targets(allocation))

    def evaluate_targets(self, target):
        """Mark any supplied formation holdings with the submitted daily convention."""
        start = target[np.maximum(self.owner, 0)].copy()
        start[~self.live] = 0.
        denominator = 1 + np.sum(start * (self.growth_before - 1), axis=1)
        if np.any(denominator <= 0):
            raise ValueError('Insolvent portfolio within holding interval')
        held = start * self.growth_before / denominator[:, None]
        gross = np.sum(held * self.r, axis=1)
        if np.any(gross <= -1):
            raise ValueError('Insolvent daily return')
        roll = np.abs(held).sum(axis=1) * .0002 * 4 / 252
        loc = self.locations
        drift = held[loc] * (1 + self.r[loc]) / (1 + gross[loc, None])
        formation_turnover = np.abs(target - drift).sum(axis=1)
        turnover = np.zeros(len(self.index));turnover[loc] = formation_turnover
        trade = np.zeros(len(self.index))
        pay = loc + 1;valid = pay < len(trade)
        trade[pay[valid]] = formation_turnover[valid] * .0002
        net = (1 + gross) * (1 - trade - roll) - 1
        return dict(gross_return=gross, net_return=net, trade_cost=trade, roll_cost=roll,
                    turnover=turnover, gross_exposure=np.abs(held).sum(axis=1),
                    net_exposure=held.sum(axis=1))

    def frame(self, allocation):
        return pd.DataFrame(self.evaluate(allocation), index=self.index)


def allocation_utility(engine, allocation, start, risk_aversion, cost_aversion,
                       mean_shrinkage=.5, regularization=.01):
    b = engine.evaluate(allocation)
    mask = engine.index >= pd.Timestamp(start)
    gross = b['gross_return'][mask];net = b['net_return'][mask]
    if len(gross) < 20:
        raise ValueError('Not enough daily training returns')
    # Exact gross-minus-net drag includes the submitted multiplicative cost rule.
    expected_gross = gross.mean() * 252 * mean_shrinkage
    realized_variance = gross.var(ddof=1) * 252
    cost = (gross - net).mean() * 252
    return float(expected_gross - risk_aversion * realized_variance / 2
                 - cost_aversion * cost - regularization * np.sum((allocation-FIXED)**2))


def fit_budgets(engine, start, risk_aversion, cost_aversion):
    """Four nonnegative budgets: trend >=30%, other sleeves <=30%, sum=1.

    Both the fixed original and pure-trend incumbent are retained. Selection of
    risk/cost aversion is a separate pre-2015 validation step, not part of this fit.
    """
    settings = dict(risk_aversion=risk_aversion, cost_aversion=cost_aversion)
    def utility(a):return allocation_utility(engine, a, start, **settings)
    candidates=[]
    for initial in [FIXED, np.array([1.,0.,0.,0.])]:
        candidates.append((utility(initial),initial.copy(),True,'feasible incumbent'))
        fit=minimize(lambda a:-utility(a),initial,method='SLSQP',
            bounds=[(.3,1.),(0.,.3),(0.,.3),(0.,.3)],
            constraints=[dict(type='eq',fun=lambda a:a.sum()-1)],
            options=dict(maxiter=120,ftol=1e-10))
        a=fit.x
        feasible=abs(a.sum()-1)<1e-7 and a[0]>=.3-1e-8 and a[0]<=1+1e-8 and np.all(a[1:]>=-1e-8) and np.all(a[1:]<=.3+1e-8)
        if feasible:candidates.append((utility(a),a.copy(),bool(fit.success),str(fit.message)))
    best=max(candidates,key=lambda x:x[0])
    return best[1],dict(**settings,training_utility=best[0],fixed_utility=utility(FIXED),
        solver_success=best[2],solver_message=best[3],mean_shrinkage=.5,regularization=.01,
        training_start=start,training_last_observation=str(engine.index.max().date()),
        daily_training_rows=int((engine.index>=pd.Timestamp(start)).sum()))
