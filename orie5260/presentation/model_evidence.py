"""Pre-2015 factor diagnostics and same-input model comparison for PPT.

Nothing is picked or retuned from post2014 performance. Model curves use frozen
pre2005 fits, identical42inputs, fixed budgets and identical daily construction.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesClassifier,RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
import joblib
from orie5260.common.data import ROOT,monthly_returns,daily_returns,asset_map,rebalance_dates
from orie5260.models.ic_feature_filter import panel
from orie5260.factors.ic import ic_statistics
from orie5260.backtests.final_strategy import inverse_vol_weight,dated_sleeves,BUDGETS
from orie5260.signals.macro_trend import macro_sleeve
from orie5260.signals.negative_skew import skew_sleeve
from orie5260.portfolio.risk_model import monthly_ewma_vol,monthly_covariance_cube,daily_covariance_cube,normalize_sleeve
from orie5260.signals.price_trend import daily_signal_and_vol
from orie5260.portfolio.engine import risk_normalize
from orie5260.portfolio.allocation import DailyAllocationEngine
from orie5260.backtests.compare_baseline import BASE,measures

OUT=ROOT/'outputs'/'ppt_factor_model_evidence'
SOURCE=ROOT/'outputs'/'ic_t_feature_filter'
COLORS={'ExtraTrees':'#008577','RandomForest':'#3A6EA5','HistGB':'#D68C45','Logistic':'#8797A6'}


def render_direction_formula():
    fig=plt.figure(figsize=(4.6,2.15));fig.patch.set_alpha(0)
    lines=[r'$s_j=\mathrm{sign}(\overline{IC}_{j,\,train}),\quad q_{j,t}=s_j\,IC_{j,t}$',
           r'$t_j^{dir}=\frac{\overline{q}_j}{SE_{NW,6}(\overline{q}_j)}$',
           r'$SE_{NW,6}^{\,2}(\overline{q}_j)=\frac{\widehat\gamma_0+2\sum_{\ell=1}^{6}(1-\ell/7)\widehat\gamma_\ell}{T}$']
    for y,text in zip([.83,.52,.20],lines):fig.text(.01,y,text,color='#102B46',fontsize=14.2,va='center')
    fig.savefig(OUT/'directional_t_formula.png',dpi=350,transparent=True);plt.close(fig)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=json.loads((SOURCE/'frozen_selection.json').read_text());features=frozen['initial_features'];assert len(features)==42
    screen=pd.read_csv(SOURCE/'pre2005_screen.csv')
    raw=screen.loc[screen.keep & ~screen.feature.str.startswith(('rank_','class_'))].copy();assert len(raw)==20
    series=pd.read_csv(ROOT/'outputs/factor_ic/monthly_feature_ic.csv',parse_dates=['return_date'])
    series=series.loc[series.return_date.between('1976-01-01','2014-12-31')]
    wide=series.pivot(index='return_date',columns='feature',values='rank_ic')
    signs=raw.set_index('feature').direction
    oriented=wide[raw.feature].mul(signs,axis=1)
    stat_rows=[]
    for name,start,end in [('Train','1976-01-01','2004-11-30'),('Validation','2005-01-01','2014-12-31')]:
        avg=oriented.loc[start:end].mean(axis=1)
        stats=ic_statistics(avg)
        mean=stats['mean_ic'];se=abs(mean/stats['hac_t6'])
        stat_rows.append(dict(period=name,**stats,hac_se=se,lower95=mean-1.96*se,upper95=mean+1.96*se))
    stats=pd.DataFrame(stat_rows)
    val_means=oriented.loc['2005':'2014'].mean()
    raw['validation_signed_ic']=raw.feature.map(val_means)
    raw.to_csv(OUT/'selected20_factor_evidence.csv',index=False);stats.to_csv(OUT/'directional_ic_statistics.csv',index=False)
    consistency=int((val_means>0).sum())
    plt.rcParams.update({'font.family':'Arial','font.size':10,'text.color':'#102B46','axes.labelcolor':'#526574','xtick.color':'#526574','ytick.color':'#526574'})
    numeric=screen.loc[~screen.feature.str.startswith('class_')]
    fig,ax=plt.subplots(figsize=(4.1,1.65))
    for keep,color,label in [(False,'#B8C2CA','Dropped'),(True,'#008577','Retained')]:
        v=numeric[numeric.keep.eq(keep)];ax.scatter(v.mean_train_rank_ic.abs(),v.hac_t6.abs(),s=15,c=color,label=label,alpha=.8)
    ax.axvline(.01,color='#D68C45',ls='--',lw=1);ax.axhline(1.96,color='#D68C45',ls='--',lw=1)
    ax.set(xlabel='|Training mean Rank IC|',ylabel='|HAC t|');ax.tick_params(labelsize=8);ax.legend(fontsize=7,loc='lower right',frameon=False)
    ax.grid(alpha=.15);fig.tight_layout(pad=.4);fig.savefig(OUT/'screen_scatter.png',dpi=300);plt.close(fig)
    fig,ax=plt.subplots(figsize=(4.25,1.29))
    ax.bar([0,1],stats.mean_ic,yerr=1.96*stats.hac_se,color=['#8797A6','#008577'],width=.5,capsize=4)
    ax.axhline(0,color='#526574',lw=.8);ax.set_xticks([0,1],['Train 1976–2004','Validation 2005–2014'],fontsize=8)
    ax.set_ylabel('Mean signed IC',fontsize=9)
    for i,row in stats.iterrows():ax.text(i,row.upper95+.003,f'{row.mean_ic:.3f}',ha='center',fontsize=9)
    ax.set_ylim(min(-.005,stats.lower95.min()-.005),stats.upper95.max()+.015);ax.grid(axis='y',alpha=.15)
    fig.tight_layout(pad=.4);fig.savefig(OUT/'signed_ic_validation.png',dpi=300);plt.close(fig)
    render_direction_formula()
    factor_meta=dict(selected_raw=20,selected_numeric=38,total_inputs=42,validation_same_direction=consistency,
        note='Trainingdirectionfixed; meanof20signedfactorICseries is diagnostic, notICofatradablecombinedportfolio; HAC6 errorbars; noFDRcorrection.')
    (OUT/'factor_evidence.json').write_text(json.dumps(factor_meta,indent=2))
    print('FACTOR',factor_meta,stats.to_string(index=False),flush=True)
    # Fit every model on exactly the same known labels and42inputs.
    r=monthly_returns().loc[:'2014-12-31'];classes=asset_map().set_index('ID').AssetClass.reindex(r.columns)
    x,target,return_date=panel(r,classes);formation=x.index.get_level_values('formation_date')
    label=target.gt(0).astype(float).where(target.notna()&target.ne(0))
    train=return_date.lt('2004-12-31')&label.notna();predict=formation>=pd.Timestamp('2004-12-31')
    assert return_date.loc[train].max()<formation[predict].min()
    constructors={
        'ExtraTrees':ExtraTreesClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
        'RandomForest':RandomForestClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
        'HistGB':HistGradientBoostingClassifier(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260),
        'Logistic':LogisticRegression(C=.1,max_iter=3000,random_state=5260)}
    probabilities={};audits=[];classification=[]
    for name,estimator in constructors.items():
        steps=[SimpleImputer(strategy='median',keep_empty_features=True)]
        if name=='Logistic':steps.append(StandardScaler())
        model=make_pipeline(*steps,estimator);model.fit(x.loc[train,features],label.loc[train].astype(int))
        p=pd.Series(np.nan,index=x.index);p.loc[predict]=model.predict_proba(x.loc[predict,features])[:,1]
        probabilities[name]=p.unstack('instrument').reindex(index=r.index,columns=r.columns)
        known=predict&label.notna().to_numpy()
        classification.append(dict(model=name,auc=roc_auc_score(label.loc[known],p.loc[known]),balanced_accuracy=balanced_accuracy_score(label.loc[known],p.loc[known]>=.5)))
        audits.append(dict(model=name,features=len(features),training_rows=int(train.sum()),last_training_label=str(return_date.loc[train].max().date()),
            first_formation=str(formation[predict].min().date()),model_params={k:v for k,v in estimator.get_params().items() if k not in ['n_jobs']}))
        if name=='ExtraTrees':
            roots=[]
            for b in range(3):
                tree=model[-1].estimators_[b].tree_;idx=int(tree.feature[0])
                roots.append(dict(tree=b+1,root_feature=features[idx],root_threshold=float(tree.threshold[0]),root_samples=int(tree.n_node_samples[0])))
            (OUT/'tree_root_examples.json').write_text(json.dumps(roots,indent=2))
        print('Fit',name,classification[-1],flush=True)
    # Original42classifier forecasts must be reproduced before comparing outcomes.
    saved=pd.read_csv(SOURCE/'development_probabilities.csv',index_col=0,parse_dates=True)
    np.testing.assert_allclose(probabilities['ExtraTrees'].loc[saved.index].to_numpy(),saved.to_numpy(),atol=1e-12,equal_nan=True)
    daily=daily_returns(list(r.columns)).loc[:'2014-12-31'];dates=rebalance_dates(daily.index);dates=dates[(dates>='1975-01-01')&(dates<=r.index.max())]
    slow,dvol=daily_signal_and_vol(daily,dates);eligible_frame=slow.notna()&dvol.notna()&slow.ne(0)
    cov=daily_covariance_cube(daily,dates,eligible_frame);core=risk_normalize(inverse_vol_weight(slow,dvol).to_numpy()*eligible_frame.to_numpy(),cov)
    vol=monthly_ewma_vol(r).where(r.notna().rolling(12,min_periods=12).sum().eq(12));eligible=vol.notna().to_numpy();mcov=monthly_covariance_cube(r)
    monthly_core=risk_normalize(inverse_vol_weight((r.rolling(12,min_periods=12).sum()/monthly_ewma_vol(r)).clip(-1,1),vol).to_numpy()*eligible,mcov)
    macro=macro_sleeve(r,classes,vol,mcov,eligible);skew=skew_sleeve(r,classes,vol,mcov,eligible)
    base=[monthly_core]+[np.where((np.abs(w).sum(axis=1)>0)[:,None],w,monthly_core)for w in [macro,skew]]
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True).loc[:'2014-12-31'];endpoints=baseline.index.intersection(dates)
    returns={}
    for name,p in probabilities.items():
        direction=2*p-1;raw=direction.div(vol);valid=raw.notna()&direction.ne(0);raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
        ml=normalize_sleeve(raw,eligible,mcov);mb=np.stack(base+[np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,monthly_core)],axis=1)
        basis=dated_sleeves(r,mb,dates,core,cov,eligible_frame.to_numpy());engine=DailyAllocationEngine(daily,dates,basis,cov);frame=engine.frame(BUDGETS)
        wealth=(1+frame.net_return).cumprod().reindex(endpoints);returns[name]=wealth/wealth.shift(1)-1
        frame.to_csv(OUT/(name+'_daily_pre2015.csv'))
    returns=pd.DataFrame(returns,index=endpoints).dropna();returns.to_csv(OUT/'aligned_pre2015_returns.csv')
    old=pd.read_csv(SOURCE/'aligned_period_returns.csv',index_col=0,parse_dates=True)
    common=old.index.intersection(returns.index);np.testing.assert_allclose(returns.loc[common,'ExtraTrees'],old.loc[common,'ICT_Fixed42'],atol=1e-9)
    results=pd.DataFrame([dict(model=name,**measures(returns[name].loc['2005':'2014']))for name in returns])
    results.to_csv(OUT/'validation_model_performance.csv',index=False);pd.DataFrame(classification).to_csv(OUT/'validation_classification.csv',index=False)
    (OUT/'model_training_audit.json').write_text(json.dumps(audits,indent=2,default=str))
    fig,ax=plt.subplots(figsize=(9,2.1))
    for name in ['ExtraTrees','RandomForest','HistGB','Logistic']:
        series=returns[name].loc['2005':'2014'];ax.plot(series.index,(1+series).cumprod(),color=COLORS[name],label=name,lw=2 if name=='ExtraTrees' else 1.5)
    ax.axhline(1,color='#526574',lw=.7);ax.set(ylabel='Net wealth from $1');ax.grid(alpha=.15)
    ax.set_xlim(pd.Timestamp('2005-01-01'),pd.Timestamp('2014-12-31'));ax.set_xticks(pd.to_datetime([f'{year}-01-01' for year in range(2005,2015)]),[str(year) for year in range(2005,2015)],fontsize=9)
    ax.legend(loc='upper left',ncol=4,frameon=False,fontsize=9);fig.tight_layout(pad=.5);fig.savefig(OUT/'candidate_model_pnl.png',dpi=250);plt.close(fig)
    print('MODELS',results.to_string(index=False),flush=True)

if __name__=='__main__':main()
