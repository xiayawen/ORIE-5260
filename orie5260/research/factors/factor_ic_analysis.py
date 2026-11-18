"""Monthly next-return IC for the final ET66 feature definitions.

Diagnostic only: no factor direction or portfolio is selected from later IC.
Ranks use the exact final feature eligibility and contemporaneous class groups.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/orie_mpl')
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from orie5260.common.data import ROOT,monthly_returns,asset_map
from orie5260.factors.features import price_features,peer_features
from orie5260.models.extra_trees import forecasts
from orie5260.factors.ic import row_ic,within_class_ic,ic_statistics,to_return_date

OUT=ROOT/'outputs'/'factor_ic'
PERIODS={'Train_1976_2004':('1976-01-01','2004-12-31'),
         'Development_2005_2014':('2005-01-01','2014-12-31'),
         'Historical_1976_2014':('1976-01-01','2014-12-31'),
         'Later_2015_2025':('2015-01-01','2025-05-31')}










def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=monthly_returns();classes=asset_map().set_index('ID').AssetClass.reindex(r.columns)
    raw={**price_features(r),**peer_features(r,classes)}
    assert len(raw)==31
    eligible=r.rolling(12,min_periods=12).std().clip(lower=.01).gt(0)
    rank={}
    for name,x in raw.items():
        q=pd.DataFrame(np.nan,index=r.index,columns=r.columns)
        for _,members in classes.groupby(classes):
            q[members.index]=x[members.index].where(eligible[members.index]).rank(axis=1,pct=True)-.5
        rank['rank_'+name]=q
    flags={'class_'+c:pd.DataFrame(np.broadcast_to(classes.eq(c).to_numpy(),r.shape).astype(float),index=r.index,columns=r.columns)
           for c in sorted(classes.unique())}
    features={**raw,**rank,**flags};assert len(features)==66
    print('Features',len(raw),len(rank),len(flags),flush=True)
    probability,audit=forecasts(r,classes,None)
    audit.to_csv(OUT/'model_training_audit.csv',index=False)
    features['ExtraTrees_probability']=probability
    target=r.shift(-1)
    rows=[];monthly=[];counts={}
    for name,score in features.items():
        score=score.where(eligible)
        p,s,count=row_ic(score,target)
        cp,cs=within_class_ic(score,target,classes)
        columns={'pearson_ic':p,'rank_ic':s,'within_class_pearson_ic':cp,'within_class_rank_ic':cs}
        dates={metric:to_return_date(series,r.index) for metric,series in columns.items()}
        coverage=to_return_date(count,r.index)
        kind=('model_forecast' if name=='ExtraTrees_probability' else 'class_control' if name.startswith('class_')
              else 'within_class_rank_feature' if name.startswith('rank_') else 'raw_factor')
        frame=pd.DataFrame(dates);frame['pairwise_markets']=coverage;frame['feature']=name
        monthly.append(frame.reset_index())
        for period,(start,end) in PERIODS.items():
            row=dict(feature=name,kind=kind,period=period)
            for metric,series in dates.items():
                for key,value in ic_statistics(series.loc[start:end]).items():row[metric+'_'+key]=value
            row['average_pairwise_markets']=coverage.loc[start:end].mean()
            rows.append(row)
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'feature_ic_summary.csv',index=False)
    pd.concat(monthly,ignore_index=True).to_csv(OUT/'monthly_feature_ic.csv',index=False)
    periods=['Train_1976_2004','Development_2005_2014','Later_2015_2025']
    table=summary.pivot(index=['feature','kind'],columns='period',values='rank_ic_mean_ic')[periods]
    table.to_csv(OUT/'rank_ic_overview.csv')
    raw_summary=summary.loc[summary.kind.eq('raw_factor')]
    heat=raw_summary.pivot(index='feature',columns='period',values='rank_ic_mean_ic')[periods]
    fig,ax=plt.subplots(figsize=(9,12))
    scale=max(np.nanmax(np.abs(heat.to_numpy())),.05)
    im=ax.imshow(heat,cmap='RdBu_r',vmin=-scale,vmax=scale,aspect='auto')
    ax.set_yticks(range(len(heat)),heat.index,fontsize=9);ax.set_xticks(range(3),['1976–2004','2005–2014','2015–May2025'])
    for i in range(len(heat)):
        for j in range(3):ax.text(j,i,f'{heat.iloc[i,j]:.3f}',ha='center',va='center',fontsize=9)
    ax.set_title('31 raw factors: mean monthly next-return Rank IC\nEqual-weight cross section; later results are descriptive')
    fig.colorbar(im,ax=ax,label='Mean Rank IC');fig.tight_layout();fig.savefig(OUT/'raw_factor_rank_ic.png',dpi=160);plt.close(fig)
    meta=dict(features='31raw +31within-class percentile ranks +4class flags; probability is an additional diagnostic, not input67',
        eligibility='Same rolling12month nonmissing-vol eligibility as final extra_trees.forecasts; observed feature/target pairs only; no imputation for IC',
        target='Actual next natural-month return; continuous magnitude, not sign label; final May2025 return uses April2025 features',
        headline='Monthly Spearman cross-sectional correlation, then equal mean over months; global>=10markets',
        class_neutral='Mean class IC, eachclass>=4markets and >=2classes per month; not a pooled regression-residual IC',
        notes='Ranks calculated within class before filtering next-return availability, matching model input construction. Flags are controls, not tradable alpha factors. No OOS sign flips or selection.',
        inference='HACt uses6Bartlett lags; many correlated hypotheses, no multiple-testing correction. ICIR=mean/monthlySD*sqrt12; not portfolioSharpe.',
        warning='Previously inspected later data; diagnostics are not new untouchedOOS evidence. Monthly IC differs from final21businessday portfolio PnL.')
    (OUT/'methodology.json').write_text(json.dumps(meta,indent=2))
    selected=summary.loc[summary.period.eq('Later_2015_2025')&summary.kind.eq('raw_factor')].copy()
    print(selected.sort_values('rank_ic_mean_ic',ascending=False)[['feature','rank_ic_mean_ic','within_class_rank_ic_mean_ic','rank_ic_months','rank_ic_hac_t6']].to_string(index=False),flush=True)
    print('MODEL',table.loc['ExtraTrees_probability'].to_string(),flush=True)

if __name__=='__main__':main()
