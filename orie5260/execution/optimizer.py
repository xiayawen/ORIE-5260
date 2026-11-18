"""Cost-aware partial trading with mandatory feasibility repair."""
import numpy as np
from orie5260.portfolio.engine import Limits, constrain
from orie5260.execution.accounting import rebalance_metrics


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

