"""Staged pre-2015 robustness search; later returns never select a candidate.

Research iteration on an already inspected dataset, not an untouched holdout.
Each stage keeps its incumbent; selection trades mean/worst fold Sharpe against
instability and turnover. Static choices avoid fitting many sleeve coefficients.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optimize_combined_portfolio import build_inputs, statistics
from unified_portfolio import (Limits, constrain, blended_target, rebalance_metrics,
    cost_aware_path, optimal_trade_fraction, risk_normalize)
from risk_budgeting import read_full_sample_returns, ROOT
from futures_factor_backtest import build_signals
from sign_return_prediction import prepare
from fixed_2015_holdout import make_model
import economic_trend as econ

OUT=ROOT/'outputs'/'portfolio_improvement'
FOLDS=[('2005-01-01','2007-12-31'),('2008-01-01','2010-12-31'),('2011-01-01','2014-11-30')]
DEFAULT=dict(net=1.,class_volatility=.05,execution='cost5',allocation=[.3,.2,.2,.3],factor='NegativeSkew_12m',model='Existing66')


def adaptive_execution(target, inp, gamma=5.):
    """Monthly full rebalance if >20% of desired gross flips held sign.

    Otherwise use existing convex cost-aware execution. All decisions use t data;
    every actual holding is feasible and only earns return t+1.
    """
    returns=inp['r'].fillna(0).to_numpy(); cov=inp['cov']; groups=inp['groups']
    limits=inp['limits']; eligible=inp['eligible']
    held=np.zeros(target.shape[1]); actual=np.zeros_like(target); rapid=np.zeros(len(target))
    for t in range(len(target)):
        gross=held@returns[t]
        if 1+gross<=0:raise ValueError('Insolvent portfolio')
        drift=held*(1+returns[t])/(1+gross)
        live=drift*eligible[t]
        repair=constrain(live,cov[t],groups,limits)
        base=live if np.linalg.norm(repair)>np.linalg.norm(live) else repair
        flipped=(target[t]*base < -1e-12)
        share=np.abs(target[t][flipped]).sum()/max(np.abs(target[t]).sum(),1e-12)
        if share>.2:u=1.;rapid[t]=1
        else:u=optimal_trade_fraction(base,target[t],drift,cov[t],gamma)
        actual[t]=base+u*(target[t]-base);held=actual[t]
    b=rebalance_metrics(actual,returns);b['rapid']=rapid
    return actual,b


def normalized_direction(direction, inp):
    raw=econ.risk_weights(direction,inp['pipe'].sleeve_vol).fillna(0).to_numpy()*inp['eligible']
    return risk_normalize(raw,inp['cov'])


def factor_units(inp):
    signals=build_signals(inp['r'])[0]
    names=['NegativeSkew_12m','LowDownside_12m','Reversal_1m','Seasonality_5y','TrendEfficiency_12m']
    units={}
    for name in names:
        direction=pd.DataFrame(np.nan,index=inp['r'].index,columns=inp['r'].columns)
        for _,members in inp['pipe'].asset_class.groupby(inp['pipe'].asset_class):
            s=signals[name][members.index].where(inp['pipe'].sleeve_vol[members.index].gt(0))
            ranks=s.rank(axis=1,pct=True)
            direction[members.index]=(2*ranks.sub(ranks.mean(axis=1),axis=0)).where(s.count(axis=1).ge(4))
        units[name]=normalized_direction(direction,inp)
    units['NoFactor']=np.zeros_like(units[names[0]])
    return units


def extra_models(inp, final=False):
    """Same 66 features, train labels strictly before each forecast formation.

    Initial fit before first Dec2004 formation; final refit before Dec2014.
    No in-sample predictions are used for earlier strategy returns.
    """
    r=inp['r'];nxt=(r.index[-1].to_period('M')+1).to_timestamp('M')
    padded=pd.concat([r,pd.DataFrame(np.nan,index=[nxt],columns=r.columns)])
    data,x,y,_,_=prepare(padded,evaluation_start='1969-01-01')
    formation=data.index.get_level_values('formation_date'); units={}; audits=[]
    for name in ['Logistic','HistGB']:
        p=pd.Series(np.nan,index=data.index)
        phases=[('development','2004-12-31','2014-12-31')]
        if final:phases.append(('post2014','2014-12-31',None))
        for phase,cut,end in phases:
            cutoff=pd.Timestamp(cut);test=formation>=cutoff
            if end:test &= formation<pd.Timestamp(end)
            if not test.any():continue
            train=data.return_date.lt(cutoff)&y.notna()
            assert data.loc[train,'return_date'].max()<formation[test].min()
            model=make_model(name);model.fit(x.loc[train],y.loc[train].astype(int))
            p.loc[test]=model.predict_proba(x.loc[test])[:,1]
            audits.append(dict(model=name,phase=phase,features=x.shape[1],training_rows=int(train.sum()),
                last_training_label=str(data.loc[train,'return_date'].max()),first_formation=str(formation[test].min())))
        direction=2*p.unstack('instrument').reindex(index=r.index,columns=r.columns)-1
        units[name]=normalized_direction(direction,inp)
        print('Built',name,'final',final,flush=True)
    return units,audits


def enrich(inp,final=False):
    inp['factors']=factor_units(inp)
    inp['models']={k:v[:,3] for k,v in inp['bases'].items()}
    models,audit=extra_models(inp,final)
    inp['models'].update(models);inp['new_audit']=audit
    return inp


def run(config,inp):
    basis=inp['bases']['Existing66'].copy();core=basis[:,0]
    factor=inp['factors'][config['factor']];ml=inp['models'][config['model']]
    for i,w in [(2,factor),(3,ml)]:basis[:,i]=np.where((np.abs(w).sum(axis=1)>0)[:,None],w,core)
    limits=Limits(net=config['net'],class_volatility=config['class_volatility'])
    target=blended_target(basis,np.asarray(config['allocation']),inp['cov'],inp['groups'],limits)
    execution=config['execution'];returns=inp['r'].fillna(0).to_numpy()
    if execution=='direct':actual,b=target,rebalance_metrics(target,returns)
    elif execution=='flip5':actual,b=adaptive_execution(target,{**inp,'limits':limits})
    else:actual,b=cost_aware_path(target,inp['cov'],returns,inp['groups'],inp['eligible'],float(execution[4:]),limits)
    return actual,b


def fold_score(b,dates):
    stats=[statistics(b,dates,start,end) for start,end in FOLDS]
    sr=np.array([s['sharpe_zero_rf'] for s in stats]);turn=np.mean([s['annual_turnover'] for s in stats])
    # Announced fixed objective; no later-period input or threshold tuning.
    score=sr.mean()-.25*sr.std()+.25*sr.min()-.002*turn
    return dict(score=float(score),mean_sharpe=sr.mean(),worst_sharpe=sr.min(),
        dispersion=sr.std(),turnover=turn,**{f'fold{i+1}_sharpe':s for i,s in enumerate(sr)})


def search(inp):
    current=DEFAULT.copy();rows=[];chosen=[];configs={}
    def stage(name,alternatives):
        nonlocal current
        candidates=[current]+[{**current,**change} for change in alternatives]
        seen=set();rank=[]
        for cfg in candidates:
            key=json.dumps(cfg,sort_keys=True)
            if key in seen:continue
            seen.add(key);cid=f'{name}_{len(rank):02d}';configs[cid]=cfg
            _,b=run(cfg,inp);s=fold_score(b,inp['r'].index)
            row=dict(stage=name,candidate=cid,config=key,**s);rows.append(row);rank.append(row)
            print(cid,'score',round(s['score'],4),'folds',[round(s[f'fold{i}_sharpe'],3) for i in range(1,4)],flush=True)
        best=max(rank,key=lambda z:z['score']);current=configs[best['candidate']].copy()
        chosen.append(best.copy());print('Selected',name,current,flush=True)
    stage('risk',[dict(net=n,class_volatility=c) for n in [1.,2.,4.] for c in [.05,.075,.10]])
    stage('execution',[dict(execution=e) for e in ['direct','cost5','cost20','cost80','flip5']])
    stage('allocation',[dict(allocation=a) for a in [[1.,0.,0.,0.],[.7,.1,.1,.1],[.7,.1,0.,.2],[.7,0.,.1,.2],[.5,.15,.05,.3]]])
    stage('factor',[dict(factor=n) for n in inp['factors']])
    stage('model',[dict(model=n) for n in inp['models']])
    # Final small execution/risk interaction check around the chosen signal mix.
    stage('interaction',[dict(net=n,class_volatility=c,execution=e)
        for n,c in [(1.,.05),(2.,.075),(4.,.10)] for e in ['direct','cost5','cost20','flip5']])
    return current,pd.DataFrame(rows),chosen,configs


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'data'/'MonthlyReturns_FullSample.xlsx'
    # Input returns are physically truncated before any candidate is generated.
    all_r=read_full_sample_returns(source)
    dev=enrich(build_inputs(all_r.loc[:'2014-12-31']))
    selected,ranking,chosen,configs=search(dev)
    ranking.to_csv(OUT/'development_candidates.csv',index=False)
    frozen=dict(selected=selected,stages=chosen,folds=FOLDS,criterion='mean Sharpe - .25*SD + .25*minimum Sharpe - .002*annual turnover',
        training='Initial ML training labels strictly before Dec2004; frozen development model through Nov2014; refit strictly before Dec2014 for post2014',
        warning='2015 onward previously inspected; this is development research, not an untouched OOS test',
        search='Greedy staged search, not exhaustive global optimum; ~40 dependent candidates on three validation blocks',
        rapid_rule='If >20% desired gross would reverse held sign, full monthly rebalance; else gamma5 cost-aware',
        factors='Prespecified economic hypotheses; no direction fitted',new_model_audit=dev['new_audit'])
    (OUT/'frozen_selection.json').write_text(json.dumps(frozen,indent=2,default=str))
    print('FROZEN BEFORE LATER EVALUATION',selected,flush=True)
    full=enrich(build_inputs(all_r),final=True)
    # Historical input invariance excludes terminal unlabeled inference row.
    for model in dev['models']:
        np.testing.assert_allclose(full['models'][model][:len(dev['r'])-1],dev['models'][model][:-1],atol=1e-10)
    pd.DataFrame(full['new_audit']).to_csv(OUT/'model_training_audit.csv',index=False)
    evaluations={'PreviousFixedCostAware':DEFAULT,'Selected':selected}
    for s in chosen:evaluations['Stage_'+s['stage']]=configs[s['candidate']]
    # Explicit strong trend controls under original and newly selected execution/risk.
    evaluations['OriginalPureTrend']={**DEFAULT,'allocation':[1.,0.,0.,0.]}
    evaluations['MatchedPureTrend']={**selected,'allocation':[1.,0.,0.,0.]}
    # Conditional removal diagnostics only; never change frozen selection.
    for i,name in [(1,'Macro'),(2,'Factor'),(3,'ML')]:
        a=np.array(selected['allocation']).copy();a[0]+=a[i];a[i]=0
        evaluations['SelectedWithout'+name]={**selected,'allocation':a.tolist()}
    rows=[];monthly={};paths={};checks=[]
    for name,cfg in evaluations.items():
        actual,b=run(cfg,full);paths[name]=actual;monthly[name]=b['net']
        cap=Limits(net=cfg['net'],class_volatility=cfg['class_volatility'])
        assert np.isfinite(actual).all()
        assert np.abs(actual).sum(axis=1).max()<=cap.gross+1e-7
        assert np.abs(actual.sum(axis=1)).max()<=cap.net+1e-7
        sigma=np.sqrt(np.maximum(np.einsum('ti,tij,tj->t',actual,full['cov'],actual),0))
        assert sigma.max()<=cap.volatility+1e-7
        for group in full['groups']:
            w=actual*group;assert np.sqrt(np.maximum(np.einsum('ti,tij,tj->t',w,full['cov'],w),0)).max()<=cap.class_volatility+1e-7
        for period,start,end in [('IS','1976-01-01','2014-12-31'),('development','2005-01-01','2014-11-30'),('later','2015-01-01',None)]:
            rows.append(dict(strategy=name,period=period,**statistics(b,all_r.index,start,end)))
        # Predicted risk at formation dates; this is not realized volatility.
        checks.append(dict(strategy=name,mean_forecast_vol=float(sigma[all_r.index>='2015-01-01'].mean())))
    # Binary baseline under both original and matched caps/execution.
    for name,cfg in [('OriginalBinary',DEFAULT),('MatchedBinary',selected)]:
        cap=Limits(net=cfg['net'],class_volatility=cfg['class_volatility'])
        target=constrain(full['binary12'],full['cov'],full['groups'],cap)
        returns=all_r.fillna(0).to_numpy();execution=cfg['execution']
        if execution=='direct':actual,b=target,rebalance_metrics(target,returns)
        elif execution=='flip5':actual,b=adaptive_execution(target,{**full,'limits':cap})
        else:actual,b=cost_aware_path(target,full['cov'],returns,full['groups'],full['eligible'],float(execution[4:]),cap)
        monthly[name]=b['net']
        for period,start,end in [('IS','1976-01-01','2014-12-31'),('later','2015-01-01',None)]:rows.append(dict(strategy=name,period=period,**statistics(b,all_r.index,start,end)))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'performance_summary.csv',index=False)
    pd.DataFrame(monthly,index=all_r.index).to_csv(OUT/'monthly_net_returns.csv')
    pd.DataFrame(checks).to_csv(OUT/'risk_utilization.csv',index=False)
    pd.DataFrame(paths['Selected'],index=all_r.index,columns=all_r.columns).to_csv(OUT/'selected_formed_weights.csv')
    fig,ax=plt.subplots(1,2,figsize=(14,5))
    for name in ['PreviousFixedCostAware','Selected','MatchedPureTrend','MatchedBinary']:
        for axis,start,end in [(ax[0],'1976','2014'),(ax[1],'2015',None)]:
            series=pd.Series(monthly[name],index=all_r.index).loc[start:end]
            axis.plot(series.index,np.log1p(series).cumsum(),label=name)
    for axis,title in zip(ax,['IS 1976–2014','Later 2015–May2025 (previously inspected)']):
        axis.set_title(title);axis.set_ylabel('Cumulative log net return');axis.legend(fontsize=8);axis.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
    print(summary[['strategy','period','sharpe_zero_rf','cagr','annual_vol','max_drawdown']].to_string(index=False),flush=True)

if __name__=='__main__':main()
