"""Pure cross-sectional IC, class conditioning and monthly HAC statistics."""
import numpy as np
import pandas as pd

def row_ic(score,target,minimum=10):
    """Pairwise observed scores/next returns, equal-weight cross-sectional IC."""
    valid=score.notna()&target.notna()
    x=score.where(valid);y=target.where(valid)
    count=valid.sum(axis=1)
    pearson=x.corrwith(y,axis=1).where(count>=minimum)
    rank=x.rank(axis=1).corrwith(y.rank(axis=1),axis=1).where(count>=minimum)
    return pearson,rank,count



def within_class_ic(score,target,classes,minimum=4):
    """Equal mean of class ICs, requiring >=2 eligible classes per month.

    Monotonic within-class ranks reproduce raw-factor within-class Rank IC;
    this is not 62 independent sources of predictive information.
    """
    pearson={};rank={}
    for c,members in classes.groupby(classes):
        p,s,_=row_ic(score[members.index],target[members.index],minimum)
        pearson[c]=p;rank[c]=s
    p=pd.DataFrame(pearson);s=pd.DataFrame(rank)
    return p.mean(axis=1).where(p.count(axis=1)>=2),s.mean(axis=1).where(s.count(axis=1)>=2)



def ic_statistics(values):
    values=values.dropna();n=len(values)
    if not n:return dict(months=0,mean_ic=np.nan,ic_std=np.nan,annual_icir=np.nan,positive_fraction=np.nan,hac_t6=np.nan)
    mean=values.mean();sd=values.std()
    centered=values.to_numpy()-mean
    lrv=centered@centered/n
    for lag in range(1,min(6,n-1)+1):
        lrv+=2*(1-lag/7)*float(centered[lag:]@centered[:-lag])/n
    se=np.sqrt(max(lrv,0)/n)
    return dict(months=n,mean_ic=mean,ic_std=sd,annual_icir=mean/sd*np.sqrt(12) if sd>0 else np.nan,
        positive_fraction=float((values>0).mean()),hac_t6=mean/se if se>0 and n>=24 else np.nan)



def to_return_date(values,dates):
    result=values.iloc[:-1].copy();result.index=dates[1:];result.index.name='return_date'
    return result

