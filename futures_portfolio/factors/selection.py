"""Train-only feature assembly and IC / directional HAC-t screening."""
import numpy as np
import pandas as pd
from futures_portfolio.factors.features import price_features,peer_features
from futures_portfolio.factors.ic import row_ic,to_return_date,ic_statistics

def feature_frames(r,classes):
    raw={**price_features(r),**peer_features(r,classes)}
    eligible=r.rolling(12,min_periods=12).std().clip(lower=.01).gt(0)
    frames=dict(raw)
    for name,score in raw.items():
        rank=pd.DataFrame(np.nan,index=r.index,columns=r.columns)
        for _,members in classes.groupby(classes):
            rank[members.index]=score[members.index].where(eligible[members.index]).rank(axis=1,pct=True)-.5
        frames['rank_'+name]=rank
    for c in sorted(classes.unique()):
        frames['class_'+c]=pd.DataFrame(np.broadcast_to(classes.eq(c).to_numpy(),r.shape).astype(float),index=r.index,columns=r.columns)
    assert len(frames)==66
    return frames,eligible



def select_inputs(r,classes,cutoff,threshold=.01,start='1976-01-01',min_abs_t=None):
    frames,eligible=feature_frames(r,classes)
    selected=[];rows=[];boundary=pd.Timestamp(cutoff)
    for name,score in frames.items():
        if name.startswith('class_'):
            selected.append(name);rows.append(dict(feature=name,mean_train_rank_ic=np.nan,months=0,keep=True,reason='class control, not alpha'))
            continue
        _,ic,_=row_ic(score.where(eligible),r.shift(-1))
        realized=to_return_date(ic,r.index)
        sample=realized.loc[(realized.index>=pd.Timestamp(start))&(realized.index<boundary)].dropna()
        mean=sample.mean();t=ic_statistics(sample)['hac_t6']
        pass_ic=bool(np.isfinite(mean) and abs(mean)>=threshold)
        # Two-sided direction-consistent rule: positiveIC needs positivet; negativeIC negativet.
        direction=1 if mean>0 else -1 if mean<0 else 0
        pass_t=bool(min_abs_t is None or (np.isfinite(t) and direction*t>=min_abs_t))
        keep=pass_ic and pass_t
        if keep:selected.append(name)
        rows.append(dict(feature=name,mean_train_rank_ic=mean,hac_t6=t,direction=direction,months=len(sample),keep=keep,passed_ic=pass_ic,passed_t=pass_t,
            reason='passed IC and optional direction t rule' if keep else 'weak/undefined IC' if not pass_ic else 'weak/undefined direction t'))
    return selected,pd.DataFrame(rows)



def panel(r,classes):
    frames,eligible=feature_frames(r,classes)
    index=pd.MultiIndex.from_product([r.index,r.columns],names=['formation_date','instrument'])
    x=pd.DataFrame({n:v.to_numpy().ravel() for n,v in frames.items()},index=index)
    nextdate=pd.Series(r.index[1:],index=r.index[:-1])
    return_date=pd.Series(index.get_level_values(0).map(nextdate),index=index)
    target=pd.Series(r.shift(-1).to_numpy().ravel(),index=index)
    known_row=eligible.to_numpy().ravel()&return_date.notna().to_numpy()
    return x.loc[known_row],target.loc[known_row],return_date.loc[known_row]

