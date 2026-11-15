"""Cross-asset exposure and lag-response factors; fixed pre/post-2015 split."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import economic_trend as econ
import out_of_sample_full_data as loader
from sign_return_prediction import prepare,directional_sleeve,classification_metrics
from fixed_2015_holdout import split,make_model
from alternative_factor_models import sleeve
from select_factor_subset import class_ic
from futures_factor_ic import summarize
from futures_factor_backtest import evaluate

OUT=Path(__file__).resolve().parent/"outputs"/"cross_asset_factors"


def cross_asset_signals(r,classes):
    """Ten fixed hypotheses. Each target instrument is excluded from proxies."""
    # Eurodollar is a rates contract, despite the legacy map's FX label.
    proxy_classes=classes.copy()
    proxy_classes.loc[proxy_classes.index.isin(econ.RATE_FUTURES_IN_FX)]="FI"
    names=["LowEquityBeta36","EquityDownsideHedge60","LowAbsoluteEquityBeta36",
           "LowBondBeta36","LowDollarBeta36","NegativeEquityCoskew60",
           "EquityLeadResponse60","BondLeadResponse60","DollarLeadResponse60","CommodityLeadResponse60"]
    output={n:pd.DataFrame(np.nan,index=r.index,columns=r.columns) for n in names}
    for col in r:
        own=r[col]
        proxies={}
        for theme,cls in [("Equity","EQ"),("Bond","FI"),("Dollar","FX"),("Commodity","COMM")]:
            members=proxy_classes.index[(proxy_classes==cls)&(proxy_classes.index!=col)]
            block=r[members]
            proxies[theme]=block.mean(axis=1).where(block.count(axis=1).ge(3))
            if theme=="Dollar":proxies[theme]=-proxies[theme]
        sd=own.rolling(36,min_periods=24).std().replace(0,np.nan)
        eq_beta=None
        for theme in ["Equity","Bond","Dollar"]:
            paired=proxies[theme].where(own.notna())
            beta=own.rolling(36,min_periods=24).cov(paired)/paired.rolling(36,min_periods=24).var().replace(0,np.nan)
            output[f"Low{theme}Beta36"][col]=-beta
            if theme=="Equity":eq_beta=beta
        output["LowAbsoluteEquityBeta36"][col]=-eq_beta.abs()
        eq=proxies["Equity"].where(own.notna())
        down=eq.lt(0)&eq.notna()&own.notna()
        downside_market=eq.where(down)
        output["EquityDownsideHedge60"][col]=-(own.where(down).rolling(60,min_periods=18).cov(downside_market)
            /downside_market.rolling(60,min_periods=18).var().replace(0,np.nan))
        # Rolling centered third cross-moment, standardized; fixed negative sign.
        z=eq.pow(2)
        mean_eq=eq.rolling(60,min_periods=36).mean()
        cov_rm=own.rolling(60,min_periods=36).cov(eq,ddof=0)
        centered_third=own.rolling(60,min_periods=36).cov(z,ddof=0)-2*mean_eq*cov_rm
        denom=own.where(eq.notna()).rolling(60,min_periods=36).std(ddof=0)*eq.rolling(60,min_periods=36).var(ddof=0)
        output["NegativeEquityCoskew60"][col]=-centered_third/denom.replace(0,np.nan)
        for theme,proxy in proxies.items():
            lag=proxy.shift(1).where(own.notna())
            beta=own.rolling(60,min_periods=36).cov(lag)/lag.rolling(60,min_periods=36).var().replace(0,np.nan)
            # Forecast at t uses regression fitted on (r_s, proxy_{s-1}), s<=t.
            # Demean current proxy by its training-window lag mean.
            forecast=beta*(proxy-lag.rolling(60,min_periods=36).mean())
            output[f"{theme}LeadResponse60"][col]=forecast/sd
    return {n:v.replace([np.inf,-np.inf],np.nan) for n,v in output.items()}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    loader.OUT=OUT
    r,audit=loader.load_and_audit(Path(__file__).resolve().parent/"data"/"MonthlyReturns_FullSample.xlsx")
    data,x,y,classes,_=prepare(r,evaluation_start="1969-01-01")
    train,validation,selection,final,test=split(data,y)
    new=cross_asset_signals(r,classes)
    newpanel=pd.DataFrame({n:v.to_numpy().ravel() for n,v in new.items()},
        index=pd.MultiIndex.from_product([r.index,r.columns],names=data.index.names)).reindex(data.index)
    ranks=newpanel.groupby([pd.Grouper(level="formation_date"),data.asset_class]).rank(pct=True)-.5
    extended=x.join(newpanel).join(ranks.add_prefix("rank_"))
    screening=[]
    for n in new:
        screening.append(dict(factor=n,**summarize(class_ic(train,newpanel.loc[train.index,n]))))
    screen=pd.DataFrame(screening).sort_values("mean",ascending=False)
    selected=screen.loc[screen["mean"].gt(0)&screen.hac3_t.ge(1),"factor"].tolist()
    screen["direct_eligible"]=screen.factor.isin(selected)
    screen.to_csv(OUT/"training_factor_screen.csv",index=False)
    core=econ.price_trend_weights(r)
    validation_weights={"TSMOM":core}
    configurations={"TSMOM":dict(kind="baseline",share=0.)}
    for n in selected:
        # Launch in 2005, only out-of-training observations initialize scaling.
        score=new[n].copy();score.loc[score.index<pd.Timestamp("2004-12-31")]=np.nan
        extra=sleeve(score,r,classes,econ.instrument_vol(r))
        for share in (.1,.2,.3):
            key=f"Direct_{n}_{int(share*100)}pct"
            validation_weights[key]=econ.scale_to_target((1-share)*core+share*extra,r)
            configurations[key]=dict(kind="direct",factor=n,share=share)
    feature_sets={"Existing66":x,"Extended86":extended}
    val_prob={};classifier_metrics=[]
    for name,features in feature_sets.items():
        model=make_model("ExtraTrees")
        model.fit(features.loc[train.index],y.loc[train.index].astype(int))
        prob=pd.Series(model.predict_proba(features.loc[validation.index])[:,1],index=validation.index)
        val_prob[name]=prob
        observed=selection.index[y.loc[selection.index].notna()]
        classifier_metrics.append(dict(features=name,period="validation",**classification_metrics(y.loc[observed],prob.loc[observed])))
        score=prob.unstack("instrument").reindex(index=r.index,columns=r.columns)
        extra=directional_sleeve(2*score-1,r)
        for share in (.1,.2,.3):
            key=f"ExtraTrees_{name}_{int(share*100)}pct"
            validation_weights[key]=econ.scale_to_target((1-share)*core+share*extra,r)
            configurations[key]=dict(kind="classifier",features=name,share=share)
    rank=[]
    end=selection.return_date.max()
    for name,w in validation_weights.items():
        b=econ.backtest(w,r).loc["2008-01-01":end]
        rank.append(dict(strategy=name,**evaluate(b.net)))
    ranking=pd.DataFrame(rank).sort_values("sharpe_zero_rf",ascending=False)
    winner=ranking.iloc[0].strategy
    ranking.to_csv(OUT/"validation_strategy_selection.csv",index=False)
    # Final classifier fits use all development labels, never later targets.
    final_prob={}
    for name,features in feature_sets.items():
        model=make_model("ExtraTrees")
        model.fit(features.loc[final.index],y.loc[final.index].astype(int))
        assert np.allclose(model[0].statistics_,features.loc[final.index].median().fillna(0),equal_nan=True)
        p=pd.Series(model.predict_proba(features.loc[test.index])[:,1],index=test.index)
        final_prob[name]=p
        observed=test.index[y.loc[test.index].notna()]
        classifier_metrics.append(dict(features=name,period="test",**classification_metrics(y.loc[observed],p.loc[observed])))
    def final_weight(name):
        c=configurations[name]
        if c["kind"]=="baseline":return core
        if c["kind"]=="direct":return validation_weights[name]
        p=pd.concat([val_prob[c["features"]],final_prob[c["features"]]])
        score=p.unstack("instrument").reindex(index=r.index,columns=r.columns)
        extra=directional_sleeve(2*score-1,r)
        return econ.scale_to_target((1-c["share"])*core+c["share"]*extra,r)
    # One best configuration per family is chosen using validation only.
    names=["TSMOM","ExtraTrees_Existing66_30pct",winner]
    for prefix in ("Direct_","ExtraTrees_Extended86_"):
        subset=ranking.loc[ranking.strategy.str.startswith(prefix)]
        if len(subset):names.append(subset.iloc[0].strategy)
    names=list(dict.fromkeys(names))
    weights={n:final_weight(n) for n in names}
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    results=[]
    for n,b in runs.items():
        for period,start,end in [("test_2015_2025","2015-01-01",None),("test_2015_2019","2015-01-01","2019-12-31"),("test_2020_onward","2020-01-01",None)]:
            q=b.loc[start:end]
            results.append(dict(strategy=n,period=period,**evaluate(q.net),
                cumulative_net_return=(1+q.net).prod()-1,mean_gross_exposure=q.leverage.mean(),annual_cost=12*q.tcost.mean()))
    pd.DataFrame(results).to_csv(OUT/"test_results.csv",index=False)
    pd.DataFrame(classifier_metrics).to_csv(OUT/"classifier_feature_comparison.csv",index=False)
    net.loc["2015-01-01":].to_csv(OUT/"test_net_returns.csv")
    pred=test[["return_date","target"]].assign(label=y.loc[test.index])
    for n,p in final_prob.items():pred[n]=p
    pred.to_csv(OUT/"test_probabilities.csv")
    missing=pd.concat([(w.shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for w in weights.values()],axis=1).any(axis=1)
    strict=net.loc["2015-01-01":].loc[~missing]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in strict]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    for n,w in weights.items():w.loc["2014-12-01":].to_csv(OUT/f"{n}_weights.csv")
    for n,f in new.items():f.to_csv(OUT/f"{n}_scores.csv")
    config=dict(new_factors=list(new),direct_train_gate="positive IC and HAC3 t>=1; no sign flips",
        eligible_direct=selected,selected_strategy=winner,selected_configuration=configurations[winner],
        feature_counts={n:len(f.columns) for n,f in feature_sets.items()},
        selection="train-only IC gate; Jan2008–Nov2014 net Sharpe; original no-overlay option included",
        classifier="fixed ExtraTrees from previous experiment; final fit through Nov2014; frozen thereafter",
        warning="2015 onward already inspected; no test-based configuration choice; not a pristine holdout",
        daily_data_limitation="local volume/open interest ends2014; not extrapolated or forward-filled into later tests")
    (OUT/"config.json").write_text(json.dumps(config,indent=2))
    fig,ax=plt.subplots(figsize=(12,5.5),layout="constrained")
    for n in names:ax.plot(np.log1p(net.loc["2015-01-01":,n]).cumsum(),label=n,lw=1.8)
    ax.set(title="Cross-asset factors: fixed pre-2015 development / later comparison",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.2)
    fig.supxlabel("All displayed shares/configurations selected before2015; native TSMOM risk/costs. Later period already inspected.",fontsize=9)
    fig.savefig(OUT/"cross_asset_comparison.png",dpi=180)
    print("TRAIN ELIGIBLE",selected,"WINNER",winner)
    print(screen.round(5).to_string(index=False))
    print(ranking.head(6).round(5).to_string(index=False))
    print(pd.DataFrame(results).query("period=='test_2015_2025'").round(5).to_string(index=False))
    print(pd.DataFrame(classifier_metrics).round(5).to_string(index=False))


if __name__=="__main__":main()
