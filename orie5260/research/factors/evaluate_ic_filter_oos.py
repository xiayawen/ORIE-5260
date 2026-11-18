"""Evaluate previously frozen IC rules; never reselect with post2014 IC.

Primary policy: screen before2005, validate2005–2014, re-screen/refit before2015
(55 final inputs). Secondary fixed56 policy keeps the old input list and only
refits its classifier before2015. Both use the same fixed portfolio construction.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json,hashlib
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from orie5260.common.data import ROOT,asset_map
from orie5260.backtests.final_strategy import build_portfolio_inputs,build_monthly_sleeves,dated_sleeves,BUDGETS
from orie5260.portfolio.risk_model import monthly_ewma_vol,monthly_covariance_cube,normalize_sleeve
from orie5260.portfolio.allocation import DailyAllocationEngine
from orie5260.backtests.compare_baseline import BASE,measures
from orie5260.models.ic_feature_filter import fit_model,panel

SOURCE=ROOT/'outputs'/'ic_feature_filter'
OUT=ROOT/'outputs'/'ic_feature_filter_oos'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=json.loads((SOURCE/'frozen_selection.json').read_text())
    artifact=joblib.load(SOURCE/'frozen_pre2015_model.joblib')
    assert artifact['features']==frozen['final_frozen_features']
    assert artifact['threshold']==.01
    # Preserve identities before any later-period return is evaluated.
    metadata=dict(threshold=.01,primary='55 inputs re-screened/refitted before2015',
        secondary='56 inputs screened before2005; classifier refitted before2015 without changing inputs',
        frozen_model_sha256=hashlib.sha256((SOURCE/'frozen_pre2015_model.joblib').read_bytes()).hexdigest(),
        frozen_selection_sha256=hashlib.sha256((SOURCE/'frozen_selection.json').read_bytes()).hexdigest(),
        primary_features=artifact['features'],secondary_features=frozen['development_features'],
        warning='No OOSIC or return used to select features/threshold. OOS already viewed historically; two policy results descriptive, not a new untouched test.')
    (OUT/'evaluation_config.json').write_text(json.dumps(metadata,indent=2))
    x=build_portfolio_inputs();monthly=x['monthly'];dates=x['dates'];classes=x['classes'] if 'classes' in x else asset_map().set_index('ID').AssetClass.reindex(monthly.columns)
    development=pd.read_csv(SOURCE/'development_probabilities.csv',index_col=0,parse_dates=True)
    models={'Rescreen55':artifact['model']}
    features={'Rescreen55':artifact['features'],'FixedInputs56':frozen['development_features']}
    models['FixedInputs56'],audit56,_=fit_model(monthly.loc[:'2014-12-31'],classes,'2014-12-31',features['FixedInputs56'])
    features_x,_,return_date=panel(monthly,classes)
    formation=features_x.index.get_level_values('formation_date')
    later=formation>=pd.Timestamp('2014-12-31')
    assert pd.Timestamp(frozen['final_fit']['last_training_label'])<formation[later].min()
    assert pd.Timestamp(audit56['last_training_label'])<formation[later].min()
    old,_classes,_audit=build_monthly_sleeves(monthly)
    vol=monthly_ewma_vol(monthly).where(monthly.notna().rolling(12,min_periods=12).sum().eq(12))
    cov=monthly_covariance_cube(monthly)
    strategies={'Original66':x['basis']}
    for name,model in models.items():
        p=development.stack().reindex(features_x.index)
        p.loc[later]=model.predict_proba(features_x.loc[later,features[name]])[:,1]
        p=p.unstack('instrument').reindex(index=monthly.index,columns=monthly.columns)
        p.to_csv(OUT/(name+'_probabilities.csv'))
        direction=2*p-1;raw=direction.div(vol);valid=raw.notna()&direction.ne(0)
        raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
        ml=normalize_sleeve(raw,vol.notna().to_numpy(),cov)
        basis=old.copy();basis[:,3]=np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,old[:,0])
        strategies[name]=dated_sleeves(monthly,basis,dates,x['daily_core'],x['covariance'],x['eligible'])
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True)
    endpoints=baseline.index.intersection(dates)
    aligned={'Baseline':baseline.net.reindex(endpoints)};paths={}
    for name,basis in strategies.items():
        engine=DailyAllocationEngine(x['daily'],dates,basis,x['covariance'])
        frame=engine.frame(BUDGETS);wealth=(1+frame.net_return).cumprod().reindex(endpoints)
        aligned[name]=wealth/wealth.shift(1)-1
        frame.to_csv(OUT/(name+'_daily_returns.csv'))
        paths[name]=frame
    aligned=pd.DataFrame(aligned,index=endpoints).dropna();rows=[]
    for period,start,end in [('Historical_1976_2014','1976-01-01','2014-12-31'),('Validation_2005_2014','2005-01-01','2014-12-31'),('OOS_2015_2025','2015-01-01','2025-05-31')]:
        for name in aligned:rows.append(dict(strategy=name,period=period,**measures(aligned[name].loc[start:end])))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'matched_performance.csv',index=False)
    aligned.to_csv(OUT/'aligned_period_returns.csv')
    # Both policies have the same pre2015 feature policy and development predictions.
    np.testing.assert_allclose(aligned.loc[:'2014','Rescreen55'],aligned.loc[:'2014','FixedInputs56'],atol=1e-12)
    historical=pd.read_csv(SOURCE/'aligned_period_returns_pre2015.csv',index_col=0,parse_dates=True)
    common=historical.index.intersection(aligned.index)
    np.testing.assert_allclose(historical.loc[common,'IC_filtered'],aligned.loc[common,'Rescreen55'],atol=1e-9)
    (OUT/'model_audit.json').write_text(json.dumps(dict(Rescreen55=frozen['final_fit'],FixedInputs56=audit56),indent=2))
    fig,ax=plt.subplots(figsize=(10,5))
    for name in aligned:
        ret=aligned[name].loc['2015':]
        ax.plot(ret.index,np.log1p(ret).cumsum(),label=name)
    ax.set(title='Later evaluation, Jan2015–May2025: frozen IC policies',ylabel='Cumulative log net return')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'oos_comparison.png',dpi=160);plt.close(fig)
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
