"""Pure portfolio math: common risk limits and cost-aware execution.

All covariance/return arrays passed here must already be dated causally by the
caller. Tax is zero. Costs use 2bps trading and 4 rolls/year on actual holdings.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Limits:
    volatility:float=.10
    gross:float=4.
    net:float=1.
    class_volatility:float=.05


def risk_normalize(w,cov,target=.10):
    variance=np.einsum("ti,tij,tj->t",w,cov,w)
    scale=np.divide(target,np.sqrt(np.maximum(variance,0)),out=np.zeros(len(w)),where=variance>1e-16)
    return w*scale[:,None]


def constrain(w,cov,groups,limits=Limits()):
    """One radial scaling satisfying all convex upper bounds simultaneously.

    Per-class limit is standalone volatility, not an Euler risk-share guarantee.
    No sequential side trimming, half-short or leverage-smoothing stack follows.
    """
    one=w.ndim==1
    if one:w=w[None,:];cov=cov[None,:,:]
    variance=np.maximum(np.einsum("ti,tij,tj->t",w,cov,w),0)
    gross=np.abs(w).sum(axis=1);net=np.abs(w.sum(axis=1))
    ratios=[]
    for cap,value in [(limits.volatility,np.sqrt(variance)),(limits.gross,gross),(limits.net,net)]:
        ratios.append(np.divide(cap,value,out=np.full(len(w),np.inf),where=value>1e-14))
    for group in groups:
        v=w*group
        sigma=np.sqrt(np.maximum(np.einsum("ti,tij,tj->t",v,cov,v),0))
        ratios.append(np.divide(limits.class_volatility,sigma,out=np.full(len(w),np.inf),where=sigma>1e-14))
    scale=np.minimum.reduce(ratios)
    scale[~np.isfinite(scale)]=0
    result=w*scale[:,None]
    return result[0] if one else result


def blended_target(basis,allocation,cov,groups,limits=Limits(),modifier=None):
    # Basis columns for inactive sleeves contain the core, returning their budget.
    raw=np.einsum("tki,k->ti",basis,allocation)
    if modifier is not None:raw=raw*modifier
    return constrain(raw,cov,groups,limits)


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


def optimal_trade_fraction(base,target,drift,cov,tracking_aversion,trade_bps=2.):
    """Exact 1D convex optimum along two feasible holdings, including forced trades.

    Min gamma/2 * tracking-error variance(monthly) + trade cost + roll cost.
    Equivalently alpha=gamma*Sigma*target/12, risk penalty gamma*Sigma/24,
    plus costs. This is an execution surrogate, not a newly estimated alpha.
    """
    delta=target-base;error=base-target;c=trade_bps/1e4
    if np.max(np.abs(delta))<1e-14:return 0.
    breaks=[0.,1.]
    for offset in (base-drift,base):
        nonzero=np.abs(delta)>1e-14
        roots=-offset[nonzero]/delta[nonzero]
        breaks.extend(roots[(roots>0)&(roots<1)].tolist())
    breaks=np.unique(breaks)
    q1=float(error@cov@delta);q2=max(float(delta@cov@delta),0.)
    candidates=list(breaks)
    for lo,hi in zip(breaks[:-1],breaks[1:]):
        mid=(lo+hi)/2
        linear=c*np.sum(np.sign(base-drift+mid*delta)*delta)
        linear+=c*4/12*np.sum(np.sign(base+mid*delta)*delta)
        if q2>1e-18:
            root=-(tracking_aversion*q1/12+linear)/(tracking_aversion*q2/12)
            if lo<root<hi:candidates.append(root)
    def objective(u):
        w=base+u*delta;err=w-target
        return tracking_aversion/24*float(err@cov@err)+c*np.abs(w-drift).sum()+c*4/12*np.abs(w).sum()
    return float(min(candidates,key=objective))


def cost_aware_path(formed,cov,returns,groups,eligible,tracking_aversion,limits=Limits()):
    """Constraints apply before execution; convex blend preserves every limit."""
    actual=np.zeros_like(formed);fraction=np.zeros(len(formed));forced=np.zeros(len(formed))
    held=np.zeros(formed.shape[1])
    for t in range(len(formed)):
        gross=float(held@returns[t])
        if 1+gross<=0:raise ValueError("Insolvent portfolio")
        drift=held*(1+returns[t])/(1+gross)
        live_drift=drift*eligible[t]
        # Prior holdings can have drifted outside limits: this mandatory repair is
        # never delayed by the cost optimizer. Do not lever up existing holdings.
        repaired=constrain(live_drift,cov[t],groups,limits)
        base=live_drift if np.linalg.norm(repaired)>np.linalg.norm(live_drift) else repaired
        forced[t]=np.abs(base-drift).sum()
        u=optimal_trade_fraction(base,formed[t],drift,cov[t],tracking_aversion)
        actual[t]=base+u*(formed[t]-base);fraction[t]=u
        held=actual[t]
    b=rebalance_metrics(actual,returns)
    b["trade_fraction"]=fraction;b["forced_trade"]=forced
    return actual,b
