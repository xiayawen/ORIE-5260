"""Predict sign(r[t+1]) with chronological binary classifiers and TSMOM overlays."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, log_loss, brier_score_loss
import economic_trend as econ
from alternative_factor_models import peer_signals
from futures_factor_backtest import build_signals, evaluate
from tree_factor_prediction import purge
from select_factor_subset import class_ic
from futures_factor_ic import summarize

OUT=Path(__file__).resolve().parent/"outputs"/"sign_return_prediction"


def prepare(r,evaluation_start="1976-01-01"):
    classes=econ.read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    old,_=build_signals(r)
    signals={**old,**peer_signals(r,classes)}
    idx=pd.MultiIndex.from_product([r.index,r.columns],names=["formation_date","instrument"])
    data=pd.DataFrame({n:s.to_numpy().ravel() for n,s in signals.items()},index=idx)
    data["asset_class"]=idx.get_level_values(1).map(classes)
    data["target"]=r.shift(-1).to_numpy().ravel()
    dates=pd.Series(r.index[1:],index=r.index[:-1])
    data["return_date"]=idx.get_level_values(0).map(dates)
    eligible=econ.instrument_vol(r).gt(0).to_numpy().ravel()
    data=data.loc[eligible & data.return_date.ge(evaluation_start) & data.return_date.notna()].copy()
    # Preserve absolute signs as well as within-class relative information.
    features=data[list(signals)].copy()
    ranks=features.groupby([pd.Grouper(level="formation_date"),data.asset_class]).rank(pct=True)-.5
    features=features.join(ranks.add_prefix("rank_"))
    for c in sorted(classes.unique()):features["class_"+c]=data.asset_class.eq(c).astype(float)
    label=data.target.gt(0).astype(float).where(data.target.notna() & data.target.ne(0))
    return data,features,label,classes,signals


def classification_metrics(y,p):
    y=np.asarray(y,dtype=int);p=np.clip(np.asarray(p),1e-8,1-1e-8)
    return dict(observations=len(y),positive_rate=y.mean(),accuracy=accuracy_score(y,p>=.5),
        balanced_accuracy=balanced_accuracy_score(y,p>=.5),auc=roc_auc_score(y,p),
        log_loss=log_loss(y,p,labels=[0,1]),brier=brier_score_loss(y,p))


def directional_sleeve(direction,r):
    raw=econ.risk_weights(direction,econ.instrument_vol(r))
    live=raw.shift(1).fillna(0).abs().sum(axis=1).gt(0)
    history=(raw.shift(1)*r.fillna(0)).sum(axis=1).where(live)
    vol=history.rolling(36,min_periods=24).std()*np.sqrt(12)
    return raw.mul((econ.TARGET_VOL/vol).replace([np.inf,-np.inf],np.nan),axis=0).fillna(0)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=econ.read_returns()
    data,x,y,classes,signals=prepare(r)
    launch=data.loc[data.return_date.ge("1995-01-01")]
    train=purge(data.loc[data.return_date.lt("1995-01-01") & y.notna()],launch)
    model_specs={
      "Logistic":LogisticRegression(C=.1,max_iter=3000,random_state=5260),
      "RandomForest":RandomForestClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
      "ExtraTrees":ExtraTreesClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
      "HistGB":HistGradientBoostingClassifier(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260),
    }
    probabilities={};config_models={}
    for name,estimator in model_specs.items():
        steps=[SimpleImputer(strategy="median",keep_empty_features=True)]
        if name=="Logistic":steps.append(StandardScaler())
        model=make_pipeline(*steps,estimator)
        model.fit(x.loc[train.index],y.loc[train.index].astype(int))
        probabilities[name]=pd.Series(model.predict_proba(x.loc[launch.index])[:,1],index=launch.index)
        config_models[name]=estimator.get_params()
    probabilities["TrainPrior"]=pd.Series(y.loc[train.index].mean(),index=launch.index)
    probabilities["AlwaysUp"]=pd.Series(1.,index=launch.index)
    # Original TSMOM sign is an observed directional baseline, not fitted.
    probabilities["TSMOM_sign"]=((launch.TSMOM+1)/2).clip(0,1)
    metric_rows=[];ic_rows=[]
    for name,p in probabilities.items():
        for period,start,end in [("validation","1998-01-01","2004-12-31"),("comparison","2005-01-01","2014-12-31"),
                                  ("2005_2009","2005-01-01","2009-12-31"),("2010_2014","2010-01-01","2014-12-31")]:
            mask=launch.return_date.between(start,end)&y.reindex(launch.index).notna()&p.notna()
            metric_rows.append(dict(model=name,period=period,**classification_metrics(y.loc[launch.index[mask]],p.loc[mask])))
            if name in model_specs and period in ("validation","comparison"):
                ic_rows.append(dict(model=name,period=period,**summarize(class_ic(launch.loc[mask],p.loc[mask]))))
    metrics=pd.DataFrame(metric_rows)
    best_classifier=metrics.loc[metrics.period.eq("validation")&metrics.model.isin(model_specs)].sort_values("log_loss").iloc[0].model
    core=econ.price_trend_weights(r)
    weights={"TSMOM":core,"TSMOM_rescaled_control":econ.scale_to_target(core,r)}
    for name in [*model_specs,"AlwaysUp"]:
        p=probabilities[name].unstack("instrument").reindex(index=r.index,columns=r.columns)
        for mode,direction in [("Soft",2*p-1),("Hard",np.sign(p-.5))]:
            extra=directional_sleeve(direction,r)
            weights[name+"_"+mode+"_Standalone"]=extra
            if name in model_specs:
                for fraction in (.1,.2,.3):
                    key=f"{name}_{mode}_{int(fraction*100)}pct"
                    weights[key]=econ.scale_to_target((1-fraction)*core+fraction*extra,r)
    # Frozen earlier best direct signal, with the same live warmup as last study.
    from alternative_factor_models import sleeve
    residual=signals["ResidualMomentum_12m"].copy()
    live_dates=launch.index.get_level_values(0).unique()
    residual.loc[~residual.index.isin(live_dates)]=np.nan
    previous=sleeve(residual,r,classes,econ.instrument_vol(r))
    weights["Prior_ResidualMomentum30"]=econ.scale_to_target(.7*core+.3*previous,r)
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    # Choose a classifier overlay, retaining the original/no-new-model alternatives.
    candidates=[n for n in net if not n.endswith("Standalone")]
    validation=net.loc["1998-01-01":"2004-12-31",candidates]
    ranking=pd.DataFrame([dict(strategy=n,**evaluate(validation[n])) for n in candidates]).sort_values("sharpe_zero_rf",ascending=False)
    winner=ranking.iloc[0].strategy
    overlay_ranking=ranking.loc[ranking.strategy.str.endswith("pct")]
    best_overlay=overlay_ranking.iloc[0].strategy
    names=list(dict.fromkeys(["TSMOM","TSMOM_rescaled_control","Prior_ResidualMomentum30",winner,best_overlay,
        best_classifier+"_Soft_Standalone","AlwaysUp_Soft_Standalone"]))
    rows=[]
    for name in names:
        for period,start,end in [("comparison","2005-01-01",None),("2005_2009","2005-01-01","2009-12-31"),("2010_2014","2010-01-01",None)]:
            b=runs[name].loc[start:end]
            rows.append(dict(strategy=name,period=period,**evaluate(b.net),mean_gross_exposure=b.leverage.mean(),annual_cost=b.tcost.mean()*12))
    summary=pd.DataFrame(rows)
    predictions=launch[["return_date","target"]].assign(label=y.reindex(launch.index))
    for name,p in probabilities.items():predictions[name]=p
    predictions.to_csv(OUT/"sign_predictions.csv")
    metrics.to_csv(OUT/"classification_metrics.csv",index=False)
    pd.DataFrame(ic_rows).to_csv(OUT/"probability_rank_ic.csv",index=False)
    ranking.to_csv(OUT/"validation_portfolio_candidates.csv",index=False)
    summary.to_csv(OUT/"portfolio_comparison.csv",index=False)
    net.to_csv(OUT/"all_net_returns_audit.csv")
    net.loc["1998-01-01":,names].to_csv(OUT/"selected_net_returns.csv")
    missing=pd.concat([(weights[n].shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for n in names],axis=1).any(axis=1)
    strict=net.loc["2005-01-01":,names].loc[~missing]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in names]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    for name in names:weights[name].to_csv(OUT/f"{name}_weights.csv")
    cfg=dict(best_classifier_by_validation_logloss=best_classifier,best_classifier_overlay=best_overlay,
        portfolio_winner_including_controls=winner,features=list(x),training_label_end=str(train.return_date.max().date()),
        train_observations=len(train),train_positive_rate=y.loc[train.index].mean(),
        target="1 if next raw monthly return>0, 0 if<0; exact zero and missing excluded from fitting/classification metrics",
        warmup="1995–1997 live out-of-training predictions; >=24 live returns for scaling",validation="1998–2004",comparison="2005–2014 previously inspected",
        trading_signal="Soft=2*p(up)-1; Hard=sign(p(up)-0.5); fixed threshold, no test calibration",
        model_refitting="none: frozen before 1995 throughout",models=config_models)
    (OUT/"config.json").write_text(json.dumps(cfg,indent=2,default=str))
    fig,ax=plt.subplots(figsize=(11,5.5),layout="constrained")
    for name in list(dict.fromkeys(["TSMOM","Prior_ResidualMomentum30",best_overlay])):
        ax.plot(np.log1p(net.loc["2005-01-01":,name]).cumsum(),label=name,lw=1.8)
    ax.set(title="Next-month sign classifiers as original TSMOM overlays",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.2)
    fig.supxlabel("Monthly rebalance | Native 10% volatility target, 2 bps trades + rolls | Previously inspected 2005–2014",fontsize=9)
    fig.savefig(OUT/"sign_model_comparison.png",dpi=180)
    print("CLASSIFIER",best_classifier,"BEST CLASSIFIER OVERLAY",best_overlay,"OVERALL WINNER",winner)
    print(metrics.loc[metrics.period.eq("comparison")].round(5).to_string(index=False))
    print(summary.loc[summary.period.eq("comparison")].round(5).to_string(index=False))


if __name__=="__main__":main()
