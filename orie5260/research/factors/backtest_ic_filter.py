"""Pre-2015-only IC filtering experiment; does not calculate later performance."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from orie5260.common.data import ROOT,monthly_returns,asset_map,daily_returns,rebalance_dates
from orie5260.backtests.final_strategy import build_monthly_sleeves,dated_sleeves,inverse_vol_weight,BUDGETS
from orie5260.signals.price_trend import daily_signal_and_vol
from orie5260.portfolio.risk_model import daily_covariance_cube,monthly_covariance_cube,monthly_ewma_vol,normalize_sleeve
from orie5260.portfolio.engine import risk_normalize
from orie5260.portfolio.allocation import DailyAllocationEngine
from orie5260.backtests.compare_baseline import BASE,measures
from orie5260.models.ic_feature_filter import select_inputs,fit_model

OUT=ROOT/'outputs'/'ic_feature_filter'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    monthly=monthly_returns().loc[:'2014-12-31']
    classes=asset_map().set_index('ID').AssetClass.reindex(monthly.columns)
    selected,screen=select_inputs(monthly,classes,'2004-12-31')
    screen.to_csv(OUT/'pre2005_screen.csv',index=False)
    model,audit,(x,target,return_date)=fit_model(monthly,classes,'2004-12-31',selected)
    formation=x.index.get_level_values('formation_date')
    predict=(formation>=pd.Timestamp('2004-12-31'))&(formation<pd.Timestamp('2014-12-31'))
    assert pd.Timestamp(audit['last_training_label'])<formation[predict].min()
    p=pd.Series(np.nan,index=x.index)
    p.loc[predict]=model.predict_proba(x.loc[predict,selected])[:,1]
    probability=p.unstack('instrument').reindex(index=monthly.index,columns=monthly.columns)
    probability.to_csv(OUT/'development_probabilities.csv')
    # Final selector/model uses only data available before the2015 forecast boundary.
    # Freeze for future use, but do not load/compute/report any post2014 strategy return.
    final_features,final_screen=select_inputs(monthly,classes,'2014-12-31')
    final_screen.to_csv(OUT/'pre2015_screen.csv',index=False)
    final_model,final_audit,_=fit_model(monthly,classes,'2014-12-31',final_features)
    joblib.dump(dict(model=final_model,features=final_features,cutoff='2014-12-31',threshold=.01),OUT/'frozen_pre2015_model.joblib',compress=3)
    frozen=dict(threshold=.01,metric='absolute mean monthly global cross-sectional Spearman IC',
        screening_start='1976-01-01',development_boundary='2004-12-31',final_boundary='2014-12-31',
        development_features=selected,final_frozen_features=final_features,
        development_fit=audit,final_fit=final_audit,
        timing='Screening and model training labels strictly before each first forecast formation; boundary-month return excluded conservatively.',
        class_controls='Keep4flags; screen62numeric inputs independently; do not flip negative scores',
        model_training_history='Same original model: all eligible earlier labels, including available pre1976 observations; IC screen begins1976.',
        warning='No post2014 performance or IC used. Later data already inspected historically; freezing now does not restore a pristine holdout.')
    (OUT/'frozen_selection.json').write_text(json.dumps(frozen,indent=2))
    print('PRE2005',len(selected),'kept; dropped',screen.loc[~screen.keep,'feature'].tolist(),flush=True)
    print('PRE2015',len(final_features),'kept; dropped',final_screen.loc[~final_screen.keep,'feature'].tolist(),flush=True)
    print('Building matched pre2015 portfolio only',flush=True)
    daily=daily_returns(list(monthly.columns)).loc[:'2014-12-31']
    dates=rebalance_dates(daily.index)
    dates=dates[(dates>=pd.Timestamp('1975-01-01'))&(dates<=monthly.index.max())]
    slow,vol=daily_signal_and_vol(daily,dates)
    eligible_frame=slow.notna()&vol.notna()&slow.ne(0)
    covariance=daily_covariance_cube(daily,dates,eligible_frame)
    core=risk_normalize(inverse_vol_weight(slow,vol).to_numpy()*eligible_frame.to_numpy(),covariance)
    original_basis,_,_=build_monthly_sleeves(monthly)
    filtered_basis=original_basis.copy()
    sleeve_vol=monthly_ewma_vol(monthly).where(monthly.notna().rolling(12,min_periods=12).sum().eq(12))
    raw=(2*probability-1).div(sleeve_vol)
    valid=raw.notna()&(2*probability-1).ne(0)
    raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
    ml=normalize_sleeve(raw,sleeve_vol.notna().to_numpy(),monthly_covariance_cube(monthly))
    filtered_basis[:,3]=np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,original_basis[:,0])
    basis={name:dated_sleeves(monthly,b,dates,core,covariance,eligible_frame.to_numpy())
        for name,b in [('Original66',original_basis),('IC_filtered',filtered_basis)]}
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True).loc[:'2014-12-31']
    endpoints=baseline.index.intersection(dates)
    aligned={};frames={}
    for name,b in basis.items():
        engine=DailyAllocationEngine(daily,dates,b,covariance)
        frame=engine.frame(BUDGETS);frames[name]=frame
        wealth=(1+frame.net_return).cumprod().reindex(endpoints)
        aligned[name]=wealth/wealth.shift(1)-1
        if name=='IC_filtered':
            pd.DataFrame(engine.targets(BUDGETS),index=dates,columns=monthly.columns).to_csv(OUT/'filtered_formation_weights_pre2015.csv')
    aligned=pd.DataFrame(aligned,index=endpoints).dropna()
    assert aligned.index.max()<=pd.Timestamp('2014-12-31')
    aligned.to_csv(OUT/'aligned_period_returns_pre2015.csv')
    rows=[]
    for period,start,end in [('Historical_1976_2014','1976-01-01','2014-12-31'),
                              ('Validation_2005_2014','2005-01-01','2014-12-31')]:
        for name in aligned:rows.append(dict(strategy=name,period=period,**measures(aligned[name].loc[start:end])))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'performance_pre2015.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(13,4.5))
    for ax,(start,title) in zip(axes,[('1976','Historical 1976–2014'),('2005','Validation 2005–2014')]):
        for name in aligned:
            ret=aligned[name].loc[start:'2014']
            ax.plot(ret.index,np.log1p(ret).cumsum(),label=name)
        ax.set(title=title,ylabel='Cumulative log net return');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'pre2015_comparison.png',dpi=160);plt.close(fig)
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
