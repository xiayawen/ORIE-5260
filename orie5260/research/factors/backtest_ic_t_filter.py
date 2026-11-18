"""Train-only |RankIC|>=.01 and direction-consistent |HACt6|>=1.96 screen.

Thresholds fixed before evaluation. Keep class controls. Compare fixed input-list
and pre2015 re-screen policies; both use the same frozen ExtraTrees and portfolio.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from orie5260.common.data import ROOT,monthly_returns,asset_map
from orie5260.models.ic_feature_filter import select_inputs,fit_model,panel
from orie5260.backtests.final_strategy import build_portfolio_inputs,build_monthly_sleeves,dated_sleeves,BUDGETS
from orie5260.portfolio.risk_model import monthly_ewma_vol,monthly_covariance_cube,normalize_sleeve
from orie5260.portfolio.allocation import DailyAllocationEngine
from orie5260.backtests.compare_baseline import BASE,measures

OUT=ROOT/'outputs'/'ic_t_feature_filter'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=monthly_returns().loc[:'2014-12-31'];classes=asset_map().set_index('ID').AssetClass.reindex(r.columns)
    initial,screen=select_inputs(r,classes,'2004-12-31',min_abs_t=1.96)
    final,final_screen=select_inputs(r,classes,'2014-12-31',min_abs_t=1.96)
    screen.to_csv(OUT/'pre2005_screen.csv',index=False);final_screen.to_csv(OUT/'pre2015_screen.csv',index=False)
    initial_model,initial_audit,(dev_x,_,_)=fit_model(r,classes,'2004-12-31',initial)
    formation=dev_x.index.get_level_values('formation_date');valid=(formation>=pd.Timestamp('2004-12-31'))&(formation<pd.Timestamp('2014-12-31'))
    assert pd.Timestamp(initial_audit['last_training_label'])<formation[valid].min()
    development=pd.Series(np.nan,index=dev_x.index);development.loc[valid]=initial_model.predict_proba(dev_x.loc[valid,initial])[:,1]
    development.unstack('instrument').to_csv(OUT/'development_probabilities.csv')
    fixed_model,fixed_audit,_=fit_model(r,classes,'2014-12-31',initial)
    rescreen_model,rescreen_audit,_=fit_model(r,classes,'2014-12-31',final)
    fixed_name=f'ICT_Fixed{len(initial)}';rescreen_name=f'ICT_Rescreen{len(final)}'
    definitions={fixed_name:dict(features=initial,model=fixed_model,audit=fixed_audit),
                 rescreen_name:dict(features=final,model=rescreen_model,audit=rescreen_audit)}
    metadata=dict(ic_threshold=.01,t_threshold=1.96,hac_lags=6,
        rule='meanIC>=.01 and HACt>=1.96 OR meanIC<=-.01 and HACt<=-1.96',
        periods='ICstart1976; initial boundaryDec2004; initial model predicts2005–2014; refit boundaryDec2014; frozen2015 onward',
        initial_features=initial,final_rescreen_features=final,initial_model_audit=initial_audit,
        final_model_audits={k:v['audit'] for k,v in definitions.items()},
        controls='4class flags retained;62numeric inputs screened independently; no manual sign flips',
        unchanged='ET200trees depth6 leaf30 maxfeatures.7 seed5260;fixed30/20/20/30;10%risk;21dayfullrebalance;uncapped;same costs',
        caution='HAC6 t cutoff is nominal two-sided5%, no multiple-testing correction; previously inspected OOS is descriptive research, not pristine holdout.')
    (OUT/'frozen_selection.json').write_text(json.dumps(metadata,indent=2))
    for name,items in definitions.items():joblib.dump(items,OUT/(name+'_frozen_model.joblib'),compress=3)
    print('FROZEN initial',len(initial),'rescreen',len(final),flush=True)
    # No post2014 input is constructed for selection or model fitting above.
    x=build_portfolio_inputs();monthly=x['monthly'];dates=x['dates']
    all_x,_,_=panel(monthly,classes);formation=all_x.index.get_level_values('formation_date');later=formation>=pd.Timestamp('2014-12-31')
    old,_,_=build_monthly_sleeves(monthly)
    vol=monthly_ewma_vol(monthly).where(monthly.notna().rolling(12,min_periods=12).sum().eq(12));cov=monthly_covariance_cube(monthly)
    strategies={'Original66':x['basis']}
    for name,items in definitions.items():
        assert pd.Timestamp(items['audit']['last_training_label'])<formation[later].min()
        p=development.reindex(all_x.index)
        p.loc[later]=items['model'].predict_proba(all_x.loc[later,items['features']])[:,1]
        probability=p.unstack('instrument').reindex(index=monthly.index,columns=monthly.columns)
        probability.to_csv(OUT/(name+'_probabilities.csv'))
        direction=2*probability-1;raw=direction.div(vol);valid=raw.notna()&direction.ne(0)
        raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
        ml=normalize_sleeve(raw,vol.notna().to_numpy(),cov)
        monthly_basis=old.copy();monthly_basis[:,3]=np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,old[:,0])
        strategies[name]=dated_sleeves(monthly,monthly_basis,dates,x['daily_core'],x['covariance'],x['eligible'])
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True);endpoints=baseline.index.intersection(dates)
    aligned={'Baseline':baseline.net.reindex(endpoints)}
    for name,basis in strategies.items():
        engine=DailyAllocationEngine(x['daily'],dates,basis,x['covariance'])
        frame=engine.frame(BUDGETS);wealth=(1+frame.net_return).cumprod().reindex(endpoints)
        aligned[name]=wealth/wealth.shift(1)-1
        frame.to_csv(OUT/(name+'_daily_returns.csv'))
    prior=pd.read_csv(ROOT/'outputs/ic_feature_filter_oos/aligned_period_returns.csv',index_col=0,parse_dates=True)
    aligned['IC_Only_Fixed56']=prior.FixedInputs56.reindex(endpoints)
    aligned['IC_Only_Rescreen55']=prior.Rescreen55.reindex(endpoints)
    aligned=pd.DataFrame(aligned,index=endpoints).dropna()
    common=prior.index.intersection(aligned.index)
    np.testing.assert_allclose(prior.loc[common,'Original66'],aligned.loc[common,'Original66'],atol=1e-9)
    np.testing.assert_allclose(aligned.loc[:'2014',fixed_name],aligned.loc[:'2014',rescreen_name],atol=1e-12)
    rows=[]
    for period,start,end in [('Historical_1976_2014','1976-01-01','2014-12-31'),('Validation_2005_2014','2005-01-01','2014-12-31'),('OOS_2015_2025','2015-01-01','2025-05-31')]:
        for name in aligned:rows.append(dict(strategy=name,period=period,**measures(aligned[name].loc[start:end])))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'matched_performance.csv',index=False);aligned.to_csv(OUT/'aligned_period_returns.csv')
    fig,axes=plt.subplots(1,2,figsize=(13,4.8))
    for ax,(start,end,title) in zip(axes,[('1976','2014','Historical1976–2014'),('2015',None,'Later2015–May2025')]):
        for name in ['Original66','IC_Only_Fixed56',fixed_name,rescreen_name]:
            ret=aligned[name].loc[start:end];ax.plot(ret.index,np.log1p(ret).cumsum(),label=name)
        ax.set(title=title,ylabel='Cumulative log net return');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
