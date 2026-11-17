"""Frozen Extra Trees forecasts for combined_strategy.Pipeline.

Reuse the exact 66/86 feature definitions and Extra Trees settings from our
fixed-holdout studies. Fit an initial pre-2005 model for development forecasts,
then refit once before 2015. Never backcast a fitted model onto its own training
period. A padded inference month preserves the latest available formation row.
"""
import numpy as np
import pandas as pd
from sign_return_prediction import prepare
from fixed_2015_holdout import make_model
from cross_asset_factor_research import cross_asset_signals


def extratrees_forecasts(returns):
    result={n:pd.DataFrame(np.nan,index=returns.index,columns=returns.columns)
            for n in ("Existing66","Extended86")}
    if returns.index.max()<pd.Timestamp("2004-12-31"):
        return result,pd.DataFrame()
    nxt=(returns.index[-1].to_period("M")+1).to_timestamp("M")
    padded=pd.concat([returns,pd.DataFrame(np.nan,index=[nxt],columns=returns.columns)])
    padded.index.name=returns.index.name
    data,base,y,classes,_=prepare(padded,evaluation_start="1969-01-01")
    new=cross_asset_signals(padded,classes)
    index=pd.MultiIndex.from_product([padded.index,padded.columns],names=data.index.names)
    panel=pd.DataFrame({n:f.to_numpy().ravel() for n,f in new.items()},index=index).reindex(data.index)
    ranks=panel.groupby([pd.Grouper(level="formation_date"),data.asset_class]).rank(pct=True)-.5
    extended=base.join(panel).join(ranks.add_prefix("rank_"))
    formation=data.index.get_level_values("formation_date")
    audits=[]
    for name,x in [("Existing66",base),("Extended86",extended)]:
        prob=pd.Series(np.nan,index=data.index)
        for phase,cutoff,end in [("development","2004-12-31","2014-12-31"),
                                  ("fixed_post2014","2014-12-31",None)]:
            boundary=pd.Timestamp(cutoff)
            future=formation>=boundary
            if end:future &= formation<pd.Timestamp(end)
            if not future.any():continue
            known=data.return_date.lt(boundary)&y.notna()
            assert data.loc[known,"return_date"].max()<formation[future].min()
            model=make_model("ExtraTrees")
            model.fit(x.loc[known],y.loc[known].astype(int))
            assert np.allclose(model[0].statistics_,x.loc[known].median().fillna(0),equal_nan=True)
            prob.loc[future]=model.predict_proba(x.loc[future])[:,1]
            audits.append(dict(features=name,phase=phase,feature_count=x.shape[1],
                training_rows=int(known.sum()),label_start=str(data.loc[known,"return_date"].min().date()),
                last_training_label=str(data.loc[known,"return_date"].max().date()),
                first_formation=str(formation[future].min().date()),last_formation=str(formation[future].max().date()),
                last_return_date=str(data.loc[future,"return_date"].max().date()),
                seed=5260,trees=200,max_depth=6,min_samples_leaf=30,max_features=.7))
        result[name]=prob.unstack("instrument").reindex(index=returns.index,columns=returns.columns)
    return result,pd.DataFrame(audits)
