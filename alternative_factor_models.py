"""Alternative factors and rank-target models as original TSMOM overlays.

Frozen training before 1995. OOS sleeve warmup 1995–1997. Validation 1998–2004.
Previously inspected comparison 2005–2014. No model refits or test-based selection.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import economic_trend as econ
from tree_factor_prediction import forest, purge
from futures_factor_backtest import build_signals, evaluate
from select_factor_subset import class_ic
from futures_factor_ic import summarize

OUT = Path(__file__).resolve().parent / "outputs" / "alternative_factor_models"


def peer_signals(r, classes):
    names = ["LowPeerBeta_36m", "LowPeerCorrelation_36m", "LowResidualVol_12m",
             "ResidualMomentum_12m", "PeerRelativeReversal_1m", "PeerRelativeMomentum_12m"]
    output = {name: pd.DataFrame(np.nan,index=r.index,columns=r.columns) for name in names}
    for _, members in classes.groupby(classes):
        block = r[members.index]
        count = block.notna().sum(axis=1)
        for col in block:
            own = block[col]
            n = count - own.notna().astype(int)
            peer = (block.sum(axis=1,min_count=1) - own.fillna(0)).div(n.replace(0,np.nan)).where(n.ge(3))
            # Paired windows for beta: no use of other dates when own is missing.
            peer = peer.where(own.notna())
            beta = own.rolling(36,min_periods=24).cov(peer).div(peer.rolling(36,min_periods=24).var().replace(0,np.nan))
            residual = own - beta*peer
            residual_vol = residual.rolling(12,min_periods=12).std().replace(0,np.nan)
            relative = own-peer
            output[names[0]][col] = -beta
            output[names[1]][col] = -own.rolling(36,min_periods=24).corr(peer)
            output[names[2]][col] = -residual_vol
            output[names[3]][col] = residual.rolling(12,min_periods=12).sum()/residual_vol
            output[names[4]][col] = -relative
            output[names[5]][col] = relative.shift(1).rolling(11,min_periods=11).sum()/own.rolling(12,min_periods=12).std().replace(0,np.nan)
    return {n:x.replace([np.inf,-np.inf],np.nan) for n,x in output.items()}


def sleeve(score, r, classes, vol):
    direction = pd.DataFrame(np.nan,index=r.index,columns=r.columns)
    for _,members in classes.groupby(classes):
        values = score[members.index].where(vol[members.index].gt(0))
        ranks = values.rank(axis=1,pct=True)
        direction[members.index] = (2*ranks.sub(ranks.mean(axis=1),axis=0)).where(values.count(axis=1).ge(4))
    raw = econ.risk_weights(direction,vol)
    # Never estimate sleeve risk using in-sample predictions or pre-launch zeros.
    live = raw.shift(1).fillna(0).abs().sum(axis=1).gt(0)
    history = ((raw.shift(1)*r.fillna(0)).sum(axis=1)).where(live)
    realized = history.rolling(36,min_periods=24).std()*np.sqrt(12)
    scaled = raw.mul((.10/realized).replace([np.inf,-np.inf],np.nan),axis=0).fillna(0)
    return scaled


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=econ.read_returns()
    classes=econ.read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    original,_=build_signals(r)
    new=peer_signals(r,classes)
    signals={**original,**new}
    idx=pd.MultiIndex.from_product([r.index,r.columns],names=["formation_date","instrument"])
    data=pd.DataFrame({n:s.to_numpy().ravel() for n,s in signals.items()},index=idx)
    data["asset_class"]=idx.get_level_values(1).map(classes)
    data["target"]=r.shift(-1).to_numpy().ravel()
    next_dates=pd.Series(r.index[1:],index=r.index[:-1])
    data["return_date"]=idx.get_level_values(0).map(next_dates)
    vol=econ.instrument_vol(r)
    eligible=vol.gt(0).to_numpy().ravel()
    data=data.loc[eligible & data.return_date.ge("1976-01-01") & data.return_date.notna()].copy()
    grouping=[pd.Grouper(level="formation_date"),data.asset_class]
    # Same-date cross-sectional transforms require no future distribution fit.
    feature_frame=data[list(signals)].groupby(grouping).rank(pct=True)-.5
    for c in sorted(classes.unique()):
        feature_frame["class_"+str(c)]=data.asset_class.eq(c).astype(float)
    target_group=data.target.groupby(grouping)
    y=(target_group.rank(pct=True)-.5).where(target_group.transform("count").ge(4))
    launch=data.loc[data.return_date.ge("1995-01-01")]
    train=purge(data.loc[data.return_date.lt("1995-01-01") & y.notna()],launch)
    assert train.return_date.max()<launch.index.get_level_values(0).min()
    all_features=list(feature_frame)
    new_features=list(new)+[c for c in feature_frame if c.startswith("class_")]
    models={
        "RankRidge_All":(make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),Ridge(alpha=100)),all_features),
        "RankRF_All":(forest(6,30),all_features),
        "RankExtraTrees_All":(make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),ExtraTreesRegressor(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2)),all_features),
        "RankHistGB_All":(make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),HistGradientBoostingRegressor(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260)),all_features),
        "RankRidge_NewOnly":(make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),Ridge(alpha=100)),new_features),
        "RankHistGB_NewOnly":(make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),HistGradientBoostingRegressor(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260)),new_features),
    }
    scores={}
    prediction_rows=[]
    for name,(model,features) in models.items():
        model.fit(feature_frame.loc[train.index,features],y.loc[train.index])
        pred=pd.Series(model.predict(feature_frame.loc[launch.index,features]),index=launch.index)
        prediction_rows.append(launch[["target","return_date"]].assign(model=name,prediction=pred))
        scores[name]=pred.unstack("instrument").reindex(index=r.index,columns=r.columns)
    live_dates=launch.index.get_level_values(0).unique()
    for name in new:
        scores["Direct_"+name]=new[name].where(pd.DataFrame(np.repeat(r.index.isin(live_dates)[:,None],len(r.columns),axis=1),index=r.index,columns=r.columns))
    core=econ.price_trend_weights(r,vol)
    weights={"TSMOM":core,"TSMOM_rescaled_control":econ.scale_to_target(core,r)}
    # Frozen prior benchmark from previous experiment; do not retune it here.
    from tsmom_factor_overlay import construct
    prior,_=construct(r,["NegativeSkew_12m"])
    weights["Prior_NegativeSkew20"]=prior["TSMOM_NegativeSkew_12m_20pct"]
    icrows=[]
    for name,score in scores.items():
        extra=sleeve(score,r,classes,vol)
        for fraction in (.1,.2,.3):
            weights[f"{name}_{int(fraction*100)}pct"]=econ.scale_to_target((1-fraction)*core+fraction*extra,r)
        ps=score.stack(future_stack=True).reindex(launch.index)
        for period,start,end in [("validation","1998-01-01","2004-12-31"),("comparison","2005-01-01","2014-12-31")]:
            mask=launch.return_date.between(start,end)
            icrows.append(dict(signal=name,period=period,**summarize(class_ic(launch.loc[mask],ps.loc[mask]))))
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    validation=net.loc["1998-01-01":"2004-12-31"]
    ranking=pd.DataFrame([dict(strategy=n,**evaluate(validation[n])) for n in validation]).sort_values("sharpe_zero_rf",ascending=False)
    winner=ranking.iloc[0].strategy
    names=list(dict.fromkeys(["TSMOM","TSMOM_rescaled_control","Prior_NegativeSkew20",winner]))
    rows=[]
    for name in names:
        for period,start,end in [("comparison","2005-01-01",None),("2005_2009","2005-01-01","2009-12-31"),("2010_2014","2010-01-01",None)]:
            b=runs[name].loc[start:end]
            rows.append(dict(strategy=name,period=period,**evaluate(b.net),gross_exposure=b.leverage.mean()))
    summary=pd.DataFrame(rows)
    ranking.to_csv(OUT/"validation_candidates.csv",index=False)
    families=[]
    for family in [*models,"Direct_"]:
        candidate=ranking.loc[ranking.strategy.str.startswith(family)].iloc[0]
        rr=net.loc["2005-01-01":,candidate.strategy]
        families.append(dict(family=family,strategy=candidate.strategy,
                             validation_sharpe=candidate.sharpe_zero_rf,**evaluate(rr)))
    pd.DataFrame(families).to_csv(OUT/"family_comparison.csv",index=False)
    summary.to_csv(OUT/"selected_comparison_summary.csv",index=False)
    pd.DataFrame(icrows).to_csv(OUT/"rank_ic_summary.csv",index=False)
    pd.concat(prediction_rows).to_csv(OUT/"model_predictions.csv")
    net.to_csv(OUT/"all_net_returns_audit.csv")
    net.loc["1998-01-01":,names].to_csv(OUT/"selected_net_returns.csv")
    for name in names: weights[name].to_csv(OUT/f"{name}_weights.csv")
    # Matched strict sensitivity, native engine otherwise exactly unchanged.
    missing=pd.concat([(weights[n].shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for n in names],axis=1).any(axis=1)
    strict=net.loc["2005-01-01":,names].loc[~missing]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in names]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    config=dict(winner=winner,features=all_features,new_features=list(new),training_labels_end=str(train.return_date.max().date()),
                validation="1998–2004 net Sharpe",warmup="1995–1997 out-of-training predictions, excluded from selection",
                model_fit="once before 1995, frozen throughout; no in-sample predictions used for sleeve scaling",
                target="within-class next-month raw-return percentile rank, centered at zero",
                model_parameters={n:m.get_params(deep=False) for n,(m,_) in models.items()},
                warning="2005–2014 already inspected; model development, no new holdout")
    (OUT/"config.json").write_text(json.dumps(config,indent=2,default=str))
    fig,ax=plt.subplots(figsize=(11,5.5),layout="constrained")
    for name in names:
        if name=="TSMOM_rescaled_control":continue
        ax.plot(np.log1p(net.loc["2005-01-01":,name]).cumsum(),label=name,lw=1.8)
    ax.set(title="Original TSMOM + alternative factor/model sleeves (2005–2014)",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.2)
    fig.supxlabel("Monthly rebalance | Original 10% vol targeting, 2 bps trades + rolls | Previously inspected comparison period",fontsize=9)
    fig.savefig(OUT/"model_overlay_comparison.png",dpi=180)
    print("WINNER",winner)
    print(ranking.head(8).to_string(index=False))
    print(summary.loc[summary.period.eq("comparison")].to_string(index=False))


if __name__=="__main__":main()
