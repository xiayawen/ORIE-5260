"""Rebuild presentation numbers/figures for the selected fixed42-input policy.

Original submission outputs are preserved. Every enhancement construction and
cap diagnostic here uses the same frozen42 inputs; matched21day annualization
is used for all turnover/cost tables as well as Sharpe comparisons.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
from dataclasses import replace
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from data_utils import ROOT
from run_final_strategy import build_portfolio_inputs,inverse_vol_weight,dated_sleeves,BUDGETS
from risk_model import monthly_ewma_vol,monthly_covariance_cube,normalize_sleeve,LIMITS
from portfolio_engine import risk_normalize,blended_target
from costs_and_execution import execute,mark_daily
from compare_baseline import BASE,measures,drawdown_series
from exposure_sensitivity import gross_match

OUT=ROOT/'outputs'/'ppt42_update'
PERIODS={'IS':('1976-01-01','2014-12-31'),'OOS':('2015-01-01','2025-05-31')}
COLORS=['#8797A6','#008577']


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    x=build_portfolio_inputs();r=x['monthly'];dates=x['dates'];cov=x['covariance']
    probability=pd.read_csv(ROOT/'outputs/ic_t_feature_filter/ICT_Fixed42_probabilities.csv',index_col=0,parse_dates=True).reindex(index=r.index,columns=r.columns)
    vol=monthly_ewma_vol(r).where(r.notna().rolling(12,min_periods=12).sum().eq(12));mcov=monthly_covariance_cube(r)
    monthly_core=risk_normalize(inverse_vol_weight((r.rolling(12,min_periods=12).sum()/monthly_ewma_vol(r)).clip(-1,1),vol).to_numpy()*vol.notna().to_numpy(),mcov)
    direction=2*probability-1;raw=direction.div(vol);valid=raw.notna()&direction.ne(0)
    raw=raw.where(valid).div(valid.sum(axis=1).replace(0,np.nan),axis=0)
    ml=normalize_sleeve(raw,vol.notna().to_numpy(),mcov)
    mb=np.stack([monthly_core]*4,axis=1);mb[:,3]=np.where((np.abs(ml).sum(axis=1)>0)[:,None],ml,monthly_core)
    x['basis'][:,3]=dated_sleeves(r,mb,dates,x['daily_core'],cov,x['eligible'])[:,3]
    blend=np.einsum('tki,k->ti',x['basis'],BUDGETS);selected=risk_normalize(blend,cov,.10)
    limited=blended_target(x['basis'],BUDGETS,cov,x['groups'],LIMITS)
    slow,_=execute(limited,cov,x['forward'],x['groups'],x['eligible'],LIMITS)
    targets={'Trend10':x['daily_core'],'Selected42':selected,'Unscaled42':blend,'Capped42':limited,'CappedCost42':slow}
    daily={k:mark_daily(x['daily'],pd.DataFrame(w,index=dates,columns=r.columns)) for k,w in targets.items()}
    baseline=pd.read_csv(BASE,index_col='Date',parse_dates=True);endpoints=baseline.index.intersection(dates)
    aligned={'Baseline':baseline.net.reindex(endpoints)}
    for name,f in daily.items():
        wealth=(1+f.net_return).cumprod().reindex(endpoints);aligned[name]=wealth/wealth.shift(1)-1
    aligned=pd.DataFrame(aligned,index=endpoints).dropna()
    source=pd.read_csv(ROOT/'outputs/ic_t_feature_filter/aligned_period_returns.csv',index_col=0,parse_dates=True)
    common=aligned.index.intersection(source.index)
    np.testing.assert_allclose(aligned.loc[common,'Selected42'],source.loc[common,'ICT_Fixed42'],atol=1e-9)
    rows=[]
    for period,(start,end) in PERIODS.items():
        for name in aligned:
            row=dict(strategy=name,period=period,**measures(aligned[name].loc[start:end]))
            if name in daily:
                f=daily[name].loc[start:end];years=row['periods']/12
                wealth=(1+f.net_return).cumprod()
                row.update(annual_turnover=f.turnover.sum()/years,annual_cost=(f.trade_cost+f.roll_cost).sum()/years,
                    average_gross=f.gross_exposure.mean(),average_absolute_net=f.net_exposure.abs().mean(),
                    daily_max_drawdown=(wealth/wealth.cummax().clip(lower=1)-1).min(),
                    daily_sharpe=f.net_return.mean()/f.net_return.std()*np.sqrt(252))
            rows.append(row)
    table=pd.DataFrame(rows);table.to_csv(OUT/'performance_and_decomposition.csv',index=False)
    aligned.to_csv(OUT/'aligned_period_returns.csv');daily['Selected42'].to_csv(OUT/'selected42_daily_returns.csv')
    no_gross=replace(LIMITS,gross=np.inf);no_net=replace(LIMITS,net=np.inf);neither=replace(LIMITS,gross=np.inf,net=np.inf)
    unnet=blended_target(x['basis'],BUDGETS,cov,x['groups'],no_net)
    variants={'Both caps':(limited,LIMITS),'No gross cap':(blended_target(x['basis'],BUDGETS,cov,x['groups'],no_gross),no_gross),
        'No net cap':(unnet,no_net),'Neither cap':(blended_target(x['basis'],BUDGETS,cov,x['groups'],neither),neither)}
    caps=[]
    for name,(target,limits) in variants.items():
        actual,_=execute(target,cov,x['forward'],x['groups'],x['eligible'],limits)
        f=mark_daily(x['daily'],pd.DataFrame(actual,index=dates,columns=r.columns))
        for period,(start,end) in PERIODS.items():
            sample=f.loc[start:end];wealth=(1+sample.net_return).cumprod()
            caps.append(dict(variant=name,period=period,daily_sharpe=sample.net_return.mean()/sample.net_return.std()*np.sqrt(252),
                max_daily_dd=(wealth/wealth.cummax().clip(lower=1)-1).min(),target_change_fraction=float((np.abs(target-limited).sum(axis=1)[(dates>=pd.Timestamp(start))&(dates<=pd.Timestamp(end))]>1e-10).mean())))
    pd.DataFrame(caps).to_csv(OUT/'cap_sensitivity.csv',index=False)
    np.testing.assert_allclose(gross_match(unnet,limited),limited,atol=1e-10)
    plt.rcParams.update({'font.family':'Arial','font.size':11,'text.color':'#102B46','axes.labelcolor':'#526574','xtick.color':'#526574','ytick.color':'#526574'})
    # Same picture proportions as existing PPT media; high DPI replaces low-res images.
    width=.32;pos=np.arange(2)
    fig,ax=plt.subplots(figsize=(6,3.87))
    for i,name in enumerate(['Baseline','Selected42']):
        vals=[float(table.loc[(table.strategy==name)&(table.period==p),'sharpe_zero_rf'].iloc[0]) for p in PERIODS]
        bars=ax.bar(pos+(i-.5)*width,vals,width,color=COLORS[i],label=['Baseline','Four-sleeve (42)'][i])
        ax.bar_label(bars,labels=[f'{v:.4f}' for v in vals],padding=4,fontsize=12,fontweight='bold')
    ax.set_xticks(pos,['1976–2014','2015–May 2025']);ax.set_ylim(0,1.6);ax.set_ylabel('Net Sharpe');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=2,frameon=False,fontsize=10)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.tight_layout();fig.savefig(OUT/'image2.png',dpi=200);plt.close(fig)
    for image,period,size in [('image3','IS',(6,3.46)),('image1','OOS',(6,3.41))]:
        fig,ax=plt.subplots(figsize=size)
        start,end=PERIODS[period]
        for i,name in enumerate(['Baseline','Selected42']):
            series=drawdown_series(aligned[name].loc[start:end]);ax.plot(series.index,series,color=COLORS[i],label=['Baseline','Four-sleeve (42)'][i],lw=1.5)
        ax.set_ylim(-.30,.01);ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.grid(axis='y',alpha=.2)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2,frameon=False,fontsize=9)
        for spine in ax.spines.values():spine.set_visible(False)
        ax.tick_params(axis='x',labelsize=9);fig.tight_layout();fig.savefig(OUT/(image+'.png'),dpi=200);plt.close(fig)
    c=pd.DataFrame(caps);fig,ax=plt.subplots(figsize=(6,1.93));pos=np.arange(4);width=.34
    for i,period in enumerate(PERIODS):
        vals=[float(c[(c.variant==n)&c.period.eq(period)].daily_sharpe.iloc[0]) for n in variants]
        bars=ax.bar(pos+(i-.5)*width,vals,width,color=COLORS[i],label=['1976–2014','2015–May 2025'][i]);ax.bar_label(bars,labels=[f'{v:.4f}' for v in vals],padding=2,fontsize=7)
    ax.set_xticks(pos,list(variants),fontsize=7);ax.set_ylim(0,max(c.daily_sharpe)*1.2);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.16),ncol=2,frameon=False,fontsize=7)
    ax.tick_params(axis='y',labelsize=7)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.tight_layout(pad=.5);fig.savefig(OUT/'image4.png',dpi=250);plt.close(fig)
    print(table.to_string(index=False),flush=True)
    print('CAPS',c.to_string(index=False),flush=True)

if __name__=='__main__':main()
