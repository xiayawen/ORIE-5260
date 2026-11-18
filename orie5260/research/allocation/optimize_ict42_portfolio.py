"""Two-layer budget fitting and cost-aware execution for the frozen42-input model.

Budget utility fits use actual full-rebalance gross risk and costs; validation
jointly chooses utility settings and execution gamma. This is a staged research
procedure, not a global optimum of asset-level alpha/risk/cost execution.
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
from orie5260.common.data import ROOT,asset_map,period_returns
from orie5260.backtests.final_strategy import build_portfolio_inputs,build_monthly_sleeves,dated_sleeves
from orie5260.portfolio.risk_model import monthly_ewma_vol,monthly_covariance_cube,normalize_sleeve
from orie5260.models.ic_feature_filter import panel
from orie5260.portfolio.allocation import DailyAllocationEngine,FIXED,fit_budgets
from orie5260.portfolio.engine import Limits
from orie5260.execution.optimizer import cost_aware_path
from orie5260.execution.costs_and_execution import mark_daily
from orie5260.research.allocation.optimize_daily_budgets import validation_metrics
from orie5260.backtests.compare_baseline import BASE,measures

OUT=ROOT/'outputs'/'ict42_portfolio_optimization'
SOURCE=ROOT/'outputs'/'ic_t_feature_filter'
LIMITS=Limits(volatility=.10,gross=np.inf,net=np.inf,class_volatility=np.inf)


def json_safe(value):
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list):return [json_safe(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def replay(engine,allocation,execution,forward,eligible):
    target=engine.targets(allocation)
    if execution is None:return target,engine.frame(allocation),None
    n=len(engine.dates)
    actual,diagnostics=cost_aware_path(target,engine.covariance,forward[:n],[],eligible[:n],float(execution),LIMITS)
    sigma=np.sqrt(np.maximum(np.einsum('ti,tij,tj->t',actual,engine.covariance,actual),0))
    assert sigma.max()<=.1+1e-8
    return actual,pd.DataFrame(engine.evaluate_targets(actual),index=engine.index),diagnostics


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=json.loads((SOURCE/'frozen_selection.json').read_text())
    features=frozen['initial_features'];assert len(features)==42
    artifact=joblib.load(SOURCE/'ICT_Fixed42_frozen_model.joblib')
    assert artifact['features']==features
    print('Build fixed42 signals; no feature re-selection',flush=True)
    x=build_portfolio_inputs();monthly=x['monthly'];daily=x['daily'];dates=x['dates']
    classes=asset_map().set_index('ID').AssetClass.reindex(monthly.columns)
    all_x,_,_=panel(monthly,classes);formation=all_x.index.get_level_values('formation_date')
    later=formation>=pd.Timestamp('2014-12-31')
    assert pd.Timestamp(artifact['audit']['last_training_label'])<formation[later].min()
    p=pd.read_csv(SOURCE/'development_probabilities.csv',index_col=0,parse_dates=True).stack().reindex(all_x.index)
    p.loc[later]=artifact['model'].predict_proba(all_x.loc[later,features])[:,1]
    p=p.unstack('instrument').reindex(index=monthly.index,columns=monthly.columns)
    old,_,_=build_monthly_sleeves(monthly)
    vol=monthly_ewma_vol(monthly).where(monthly.notna().rolling(12,min_periods=12).sum().eq(12))
    direction=2*p-1;raw=direction.div(vol);valid=raw.notna()&direction.ne(0)
    raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
    ml=normalize_sleeve(raw,vol.notna().to_numpy(),monthly_covariance_cube(monthly))
    old[:,3]=np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,old[:,0])
    basis=dated_sleeves(monthly,old,dates,x['daily_core'],x['covariance'],x['eligible'])
    # Only truncated histories are exposed to utility fitting and validation.
    train=DailyAllocationEngine(daily,dates,basis,x['covariance'],end='2009-12-31')
    dev=DailyAllocationEngine(daily,dates,basis,x['covariance'],end='2014-11-30')
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True);endpoints=baseline.index.intersection(dates)
    forward=period_returns(daily,dates).reindex(dates).fillna(0).to_numpy()
    # Truncate formation returns before any training/validation replay.
    dev_forward=forward[:len(dev.dates)];dev_eligible=x['eligible'][:len(dev.dates)]
    rows=[];fits={}
    for execution in [None,5.,20.]:
        _,frame,_=replay(dev,FIXED,execution,dev_forward,dev_eligible)
        rows.append(dict(candidate='Fixed',execution=execution,**validation_metrics(frame,endpoints)))
    for risk in [2.,8.]:
        for cost in [1.,3.,10.]:
            name=f'Risk{risk:g}_Cost{cost:g}'
            allocation,audit=fit_budgets(train,'2005-01-01',risk,cost)
            fits[name]=dict(allocation=allocation.tolist(),audit=audit)
            schedule=np.tile(FIXED,(len(dev.dates),1));schedule[dev.dates>=pd.Timestamp('2010-01-01')]=allocation
            for execution in [None,5.,20.]:
                _,frame,_=replay(dev,schedule,execution,dev_forward,dev_eligible)
                stats=validation_metrics(frame,endpoints)
                rows.append(dict(candidate=name,execution=execution,**stats))
                print(name,'gamma',execution,'validation',round(stats['sharpe_zero_rf'],4),flush=True)
    ranking=pd.DataFrame(rows).sort_values('sharpe_zero_rf',ascending=False,kind='stable')
    ranking.to_csv(OUT/'validation_candidates.csv',index=False)
    weight_choice=ranking.loc[ranking.candidate.ne('Fixed')&ranking.execution.isna()].iloc[0]
    fixed_cost_choice=ranking.loc[ranking.candidate.eq('Fixed')&ranking.execution.notna()].iloc[0]
    combined_choice=ranking.loc[ranking.candidate.ne('Fixed')&ranking.execution.notna()].iloc[0]
    allocations={};refits={}
    for choice in [weight_choice,combined_choice]:
        if choice.candidate in allocations:continue
        audit=fits[choice.candidate]['audit']
        allocation,refit=fit_budgets(dev,'2005-01-01',audit['risk_aversion'],audit['cost_aversion'])
        allocations[choice.candidate]=allocation;refits[choice.candidate]=refit
    config=dict(weight_only_choice=weight_choice.to_dict(),fixed_execution_choice=fixed_cost_choice.to_dict(),
        combined_choice=combined_choice.to_dict(),overall_validation_winner=ranking.iloc[0].to_dict(),
        allocations={k:v.tolist() for k,v in allocations.items()},calibration_fits=fits,refits=refits,
        features=features,source_model_sha256=hashlib.sha256((SOURCE/'ICT_Fixed42_frozen_model.joblib').read_bytes()).hexdigest(),
        training='budgetfit2005–2009; validation complete periods formed after2009 ending byNov2014; selectedutility refit2005–Nov2014',
        objective='0.5*annual gross daily mean - lambda/2*annual realized training variance - kappa*actual net cost drag - .01*||a-fixed||^2',
        construction='42inputs unchanged; 10% exante target before execution; no gross/net/class caps; execution imposes10% forecast-vol ceiling; 21day decisions; daily netted costs',
        execution='1D convex trade fraction: monthly tracking variance penalty plus trading/roll costs; forced risk/eligibility repairs are immediate',
        method='Two-stage: budget utility fitted with full execution, then validation chooses execution jointly. No claim of joint global execution-aware optimum.',
        warning='Previously inspected OOS. No later performance used to choose configs; final whole-IS is fitted history, not independent validation.')
    (OUT/'frozen_selection.json').write_text(json.dumps(json_safe(config),indent=2,default=str,allow_nan=False))
    print('FROZEN',config['allocations'],'overall',config['overall_validation_winner'],flush=True)
    full=DailyAllocationEngine(daily,dates,basis,x['covariance'])
    definitions={'Fixed42_Full':(FIXED,None),
        'WeightOptimized42_Full':(allocations[weight_choice.candidate],None),
        'Fixed42_CostAware':(FIXED,float(fixed_cost_choice.execution)),
        'WeightOptimized42_CostAware':(allocations[combined_choice.candidate],float(combined_choice.execution))}
    aligned={'Baseline':baseline.net.reindex(endpoints)};stats_rows=[];diagnostics=[]
    for name,(allocation,execution) in definitions.items():
        actual,frame,diag=replay(full,allocation,execution,forward,x['eligible'])
        # Independent accounting check against the final submitted marker.
        marked=mark_daily(daily,pd.DataFrame(actual,index=dates,columns=daily.columns))
        np.testing.assert_allclose(frame[marked.columns].to_numpy(),marked.to_numpy(),atol=1e-9,rtol=1e-9)
        wealth=(1+frame.net_return).cumprod().reindex(endpoints);aligned[name]=wealth/wealth.shift(1)-1
        frame.to_csv(OUT/(name+'_daily_returns.csv'))
        pd.DataFrame(actual,index=dates,columns=daily.columns).to_csv(OUT/(name+'_formed_weights.csv'))
        for period,start,end in [('Historical_1976_2014','1976-01-01','2014-12-31'),('OOS_2015_2025','2015-01-01','2025-05-31')]:
            f=frame.loc[start:end];years=len(f)/252
            diagnostics.append(dict(strategy=name,period=period,annual_turnover=f.turnover.sum()/years,
                annual_cost=(f.trade_cost+f.roll_cost).sum()/years,mean_gross=f.gross_exposure.mean(),
                annual_realized_vol=f.net_return.std()*np.sqrt(252)))
        if diag is not None:pd.DataFrame({'trade_fraction':diag['trade_fraction'],'forced_trade':diag['forced_trade']},index=dates).to_csv(OUT/(name+'_execution.csv'))
    aligned=pd.DataFrame(aligned,index=endpoints).dropna()
    prior=pd.read_csv(SOURCE/'aligned_period_returns.csv',index_col=0,parse_dates=True)
    common=aligned.index.intersection(prior.index)
    np.testing.assert_allclose(aligned.loc[common,'Fixed42_Full'],prior.loc[common,'ICT_Fixed42'],atol=1e-9)
    for period,start,end in [('Historical_1976_2014','1976-01-01','2014-12-31'),('Refit_subperiod_2005_2014','2005-01-01','2014-12-31'),('OOS_2015_2025','2015-01-01','2025-05-31')]:
        for name in aligned:stats_rows.append(dict(strategy=name,period=period,**measures(aligned[name].loc[start:end])))
    summary=pd.DataFrame(stats_rows);summary.to_csv(OUT/'matched_performance.csv',index=False)
    pd.DataFrame(diagnostics).to_csv(OUT/'execution_diagnostics.csv',index=False);aligned.to_csv(OUT/'aligned_period_returns.csv')
    fig,axes=plt.subplots(1,2,figsize=(13,4.8))
    for ax,(start,end,title) in zip(axes,[('1976','2014','IS1976–2014'),('2015',None,'Later2015–May2025')]):
        for name in definitions:
            ret=aligned[name].loc[start:end];ax.plot(ret.index,np.log1p(ret).cumsum(),label=name)
        ax.set(title=title,ylabel='Cumulative log net return');ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
