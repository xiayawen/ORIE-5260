"""Train four sleeve budgets, freeze them, compare to the daily final submission.

Signal model, dates, 10% risk scaling, uncapped full execution and netted costs
are held fixed. Six utility settings are validated before 2015. No OOS selection.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data_utils import ROOT
from run_final_strategy import build_portfolio_inputs
from sleeve_allocation import DailyAllocationEngine, FIXED, fit_budgets
from costs_and_execution import mark_daily
from compare_baseline import BASE, measures

OUT=ROOT/'outputs'/'daily_budget_optimization'


def aligned_return(frame,endpoints):
    wealth=(1+frame.net_return).cumprod().reindex(endpoints)
    return wealth/wealth.shift(1)-1


def validation_metrics(frame, endpoints):
    p=aligned_return(frame,endpoints)
    prior=pd.Series(endpoints,index=endpoints).shift(1)
    # Exclude a crossing period formed before the training cutoff.
    valid=(p.index>=pd.Timestamp('2010-01-01'))&(p.index<=pd.Timestamp('2014-11-30'))&prior.ge('2010-01-01').to_numpy()
    return measures(p.loc[valid].dropna())


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    print('Building unchanged final-strategy signals and dated risk inputs',flush=True)
    x=build_portfolio_inputs();daily=x['daily'];dates=x['dates']
    train=DailyAllocationEngine(daily,dates,x['basis'],x['covariance'],end='2009-12-31')
    development=DailyAllocationEngine(daily,dates,x['basis'],x['covariance'],end='2014-11-30')
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True)
    endpoints=baseline.index.intersection(dates)
    # Truncation means no return after the cutoff is evaluated by the fit.
    assert train.index.max()<pd.Timestamp('2010-01-01')
    assert development.index.max()<pd.Timestamp('2014-12-01')
    rows=[];fits={}
    fixed_metrics=validation_metrics(development.frame(FIXED),endpoints)
    rows.append(dict(candidate='Fixed',allocation=json.dumps(FIXED.tolist()),**fixed_metrics))
    for risk in [2.,8.]:
        for cost in [1.,3.,10.]:
            name=f'Risk{risk:g}_Cost{cost:g}'
            a,audit=fit_budgets(train,'2005-01-01',risk,cost)
            schedule=np.tile(FIXED,(len(development.dates),1))
            schedule[development.dates>=pd.Timestamp('2010-01-01')]=a
            # Switch after fit availability; charge the actual initial switch.
            s=validation_metrics(development.frame(schedule),endpoints)
            rows.append(dict(candidate=name,allocation=json.dumps(a.tolist()),**s))
            fits[name]=dict(allocation=a.tolist(),audit=audit)
            print('VALIDATION',name,np.round(a,4),round(s['sharpe_zero_rf'],4),flush=True)
    ranking=pd.DataFrame(rows).sort_values('sharpe_zero_rf',ascending=False,kind='stable')
    best=ranking.loc[ranking.candidate.ne('Fixed')].iloc[0]
    selected=ranking.iloc[0].candidate
    old_fit=fits[best.candidate]['audit']
    a,refit=fit_budgets(development,'2005-01-01',old_fit['risk_aversion'],old_fit['cost_aversion'])
    frozen=dict(optimized_family_candidate=best.candidate,validation_winner=selected,
        final_optimized_allocation=a.tolist(),fixed_allocation=FIXED.tolist(),
        training='2005–2009; validation complete periods formed after2009 and ending byNov2014; final refit Jan2005–Nov2014',
        bounds='trend30–100%; macro/factor/ML each0–30%; all nonnegative; sum1',
        objective='0.5*annual daily gross mean - risk_aversion/2*annual daily gross variance - cost_aversion*exact annual gross-minus-net cost drag - .01*sum((a-fixed)^2)',
        risk_note='Final book remains at10% ex-ante risk. Forecast variance is constant after scaling; risk penalty therefore uses realized TRAINING variance, not that constant.',
        unchanged='ET66 signals, 252-day covariance, 10% ex-ante target, 21-day full rebalances, no exposure caps, 2bps costs plus4annual rolls',
        fits=fits,final_refit=refit,
        warning='Post2014 repeatedly inspected in earlier research; no new untouched OOS claim. Report optimized-family result even if Fixed wins validation.')
    ranking.to_csv(OUT/'validation_selection.csv',index=False)
    (OUT/'frozen_selection.json').write_text(json.dumps(frozen,indent=2))
    print('FROZEN',np.round(a,6),'validation winner',selected,flush=True)
    # Later-period performance is computed only after choices above are saved.
    full=DailyAllocationEngine(daily,dates,x['basis'],x['covariance'])
    frames={'Fixed':full.frame(FIXED),'Optimized':full.frame(a)}
    saved=pd.read_csv(ROOT/'outputs/final_strategy/daily_returns_and_costs.csv',index_col='Date',parse_dates=True)
    common=frames['Fixed'].index.intersection(saved.index)
    delta=(frames['Fixed'].loc[common]-saved.loc[common]).abs().max()
    print('Fixed engine reconciliation',delta.to_dict(),flush=True)
    # Saved outputs are a reference; independently verify both paths against
    # the current submitted marker, and record any historical-output discrepancy.
    fixed_marked=mark_daily(daily,pd.DataFrame(full.targets(FIXED),index=full.dates,columns=daily.columns))
    np.testing.assert_allclose(frames['Fixed'][fixed_marked.columns].to_numpy(),fixed_marked.to_numpy(),atol=1e-9,rtol=1e-9)
    saved_weights=pd.read_csv(ROOT/'outputs/final_strategy/formation_weights.csv',index_col='Date',parse_dates=True)
    wdiff=(pd.DataFrame(full.targets(FIXED),index=full.dates,columns=daily.columns)-saved_weights).abs()
    wdiff.max(axis=1).to_csv(OUT/'saved_target_max_difference.csv',header=['max_absolute_weight_difference'])
    print('Saved targets differing >1e-10:',int((wdiff.max(axis=1)>1e-10).sum()),'max',wdiff.max().max(),flush=True)
    audit=dict(fixed_matches_current_original_marker=True,optimized_matches_current_original_marker=True,
        saved_reference_max_daily_net_difference=float(delta['net_return']),
        saved_reference_formation_dates_differing_above_1e_minus10=int((wdiff.max(axis=1)>1e-10).sum()),
        saved_reference_max_weight_difference=float(wdiff.max().max()),
        note='Saved artifacts differ slightly on12 pre2015 formation dates. Comparisons use freshly regenerated fixed control and original marker; cause of historical saved-artifact discrepancy not established.')
    # Independently verify the actual optimized path using original daily marker.
    target=full.targets(a)
    marked=mark_daily(daily,pd.DataFrame(target,index=full.dates,columns=daily.columns))
    np.testing.assert_allclose(frames['Optimized'][marked.columns].to_numpy(),marked.to_numpy(),atol=1e-9,rtol=1e-9)
    predicted=np.sqrt(np.maximum(np.einsum('ti,tij,tj->t',target,full.covariance,target),0))
    assert np.allclose(predicted[predicted>0],.10)
    (OUT/'evaluation_audit.json').write_text(json.dumps(audit,indent=2))
    aligned=pd.DataFrame({'Baseline':baseline.net.reindex(endpoints),
        **{name:aligned_return(f,endpoints) for name,f in frames.items()}},index=endpoints).dropna()
    rows=[]
    periods={'IS_1976_2014':('1976-01-01','2014-12-31'),
        'Refit_subperiod_2005_2009':('2005-01-01','2009-12-31'),
        'Refit_subperiod_2010_Nov2014':('2010-01-01','2014-11-30'),
        'OOS_2015_2025':('2015-01-01','2025-05-31')}
    for period,(start,end) in periods.items():
        for name in aligned:
            row=dict(strategy=name,period=period,**measures(aligned[name].loc[start:end]))
            if name in frames:
                f=frames[name].loc[start:end];years=len(f)/252
                row.update(annual_turnover=f.turnover.sum()/years,annual_cost=(f.trade_cost+f.roll_cost).sum()/years,
                    average_gross_exposure=f.gross_exposure.mean(),average_absolute_net_exposure=f.net_exposure.abs().mean())
            rows.append(row)
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'matched_performance.csv',index=False)
    aligned.to_csv(OUT/'aligned_period_returns.csv',index_label='period_end')
    pd.DataFrame(target,index=full.dates,columns=daily.columns).to_csv(OUT/'optimized_formation_weights.csv',index_label='Date')
    frames['Optimized'].to_csv(OUT/'optimized_daily_returns_and_costs.csv',index_label='Date')
    pd.DataFrame({'metric':delta.index,'max_absolute_difference':delta.values}).to_csv(OUT/'fixed_reconciliation.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(13,4.8))
    for ax,(period,(start,end)) in zip(axes,[(k,v) for k,v in periods.items() if k in ['IS_1976_2014','OOS_2015_2025']]):
        for name in aligned:
            ret=aligned[name].loc[start:end]
            ax.plot(ret.index,np.log1p(ret).cumsum(),label=name)
        ax.set(title=period.replace('_',' '),ylabel='Cumulative log net return');ax.grid(alpha=.2);ax.legend()
    fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
    print(summary[['strategy','period','sharpe_zero_rf','cagr','annual_volatility','max_endpoint_drawdown']].to_string(index=False),flush=True)

if __name__=='__main__':main()
