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








def __getattr__(name):
    """Lazy compatibility for functions moved into the execution package."""
    if name == "rebalance_metrics":
        from orie5260.execution.accounting import rebalance_metrics
        return rebalance_metrics
    if name in {"optimal_trade_fraction", "cost_aware_path"}:
        from orie5260.execution import optimizer
        return getattr(optimizer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
