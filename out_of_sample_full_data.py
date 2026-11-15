"""Frozen post-2014 evaluation; never select parameters on supplied new returns."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
import economic_trend as econ
from alternative_factor_models import peer_signals, sleeve
from tsmom_factor_overlay import construct
from sign_return_prediction import prepare, directional_sleeve, classification_metrics
from tree_factor_prediction import purge
from futures_factor_backtest import evaluate

OUT=Path(__file__).resolve().parent/"outputs"/"full_sample_oos"


def load_and_audit(path):
    hist=econ.read_returns()
    hist.index=hist.index.to_period("M").to_timestamp("M")
    full=pd.read_excel(path,index_col=0)
    full.index=pd.to_datetime(full.index).to_period("M").to_timestamp("M")
    full.columns=full.columns.astype(str).str.strip()
    full=full.apply(pd.to_numeric,errors="raise").replace([np.inf,-np.inf],np.nan).sort_index()
    if full.index.has_duplicates or full.columns.has_duplicates:raise ValueError("Duplicate months or instruments")
    unknown=full.columns.difference(hist.columns)
    if len(unknown):raise ValueError(f"Unknown instruments: {list(unknown)}")
    expected=pd.date_range(full.index.min(),full.index.max(),freq="ME")
    if len(expected.difference(full.index)):raise ValueError("Missing calendar months in full sample")
    dates=hist.index.intersection(full.index)
    a,b=hist.loc[dates],full.reindex(index=dates,columns=hist.columns)
    both=a.notna()&b.notna()
    difference=(a-b).abs().where(both)
    missing_diff=a.isna()!=b.isna()
    missing_diff.stack().loc[lambda s:s].rename("missingness_disagrees").to_csv(OUT/"overlap_missingness_differences.csv")
    new=full.loc[full.index>pd.Timestamp(econ.IS_END)].reindex(columns=hist.columns)
    if new.empty:raise ValueError("No post-2014 observations")
    if new.index.min()!=pd.Timestamp("2015-01-31"):raise ValueError("OOS must begin January 2015")
    combined=pd.concat([hist.loc[:econ.IS_END],new])
    audit=dict(input=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        original_months=len(hist),full_file_months=len(full),overlap_months=len(dates),
        overlap_max_absolute_difference=float(difference.max().max()),
        overlap_pairs_differing_gt_1e_8=int((difference>1e-8).sum().sum()),
        overlap_missingness_disagreements=int(missing_diff.sum().sum()),
        historical_input="original MonthlyReturns.csv preserved through Dec 2014; append only newer Excel rows",
        oos_start=str(new.index.min().date()),oos_end=str(new.index.max().date()),oos_months=len(new),
        oos_instruments=int(new.notna().any().sum()),oos_returns_le_minus_one=int((new<=-1).sum().sum()))
    (OUT/"data_audit.json").write_text(json.dumps(audit,indent=2))
    new.notna().sum().rename("observed_oos_months").to_csv(OUT/"instrument_coverage.csv")
    new.stack().abs().sort_values(ascending=False).head(30).rename("absolute_return").to_csv(OUT/"largest_absolute_returns.csv")
    return combined,audit


def frozen_weights(r):
    core=econ.price_trend_weights(r)
    data,x,y,classes,signals=prepare(r)
    launch=data.loc[data.return_date.ge("1995-01-01")]
    train=purge(data.loc[data.return_date.lt("1995-01-01")&y.notna()],launch)
    classifier=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
        HistGradientBoostingClassifier(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,
          l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260))
    classifier.fit(x.loc[train.index],y.loc[train.index].astype(int))
    p=pd.Series(classifier.predict_proba(x.loc[launch.index])[:,1],index=launch.index)
    matrix=p.unstack("instrument").reindex(index=r.index,columns=r.columns)
    sign_sleeve=directional_sleeve(2*matrix-1,r)
    score=signals["ResidualMomentum_12m"].copy()
    score.loc[~score.index.isin(launch.index.get_level_values(0).unique())]=np.nan
    residual=sleeve(score,r,classes,econ.instrument_vol(r))
    prior,_=construct(r,["NegativeSkew_12m"])
    weights={"TSMOM":core,"TSMOM_rescaled_control":econ.scale_to_target(core,r),
      "TSMOM_ResidualMomentum30":econ.scale_to_target(.7*core+.3*residual,r),
      "TSMOM_NegativeSkew20":prior["TSMOM_NegativeSkew_12m_20pct"],
      "TSMOM_SignHistGB30":econ.scale_to_target(.7*core+.3*sign_sleeve,r),
      "SignHistGB_Standalone":sign_sleeve}
    predictions=launch[["return_date","target"]].assign(label=y.reindex(launch.index),probability_up=p)
    return weights,predictions,dict(training_observations=len(train),last_training_label=str(train.return_date.max().date()),
                                   classifier_parameters=classifier[-1].get_params())


def prefix_check(r,weights):
    # Full future data must reproduce the exact historical strategy weights.
    old,pred,_=frozen_weights(r.loc[:"2014-12-31"])
    # Previous runners omit the last formation row because no forward label
    # date exists in a truncated file. Compare all previously evaluated holdings,
    # through Nov 2014 formation / Dec 2014 execution, not that terminal row.
    for name in weights:
        comparable=old[name].index[:-1]
        assert np.allclose(weights[name].loc[comparable],old[name].loc[comparable],equal_nan=True),name
    return "PASS: all six strategies reproduce every evaluated pre-2015 holding (formation through Nov 2014)"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",type=Path,default=Path(__file__).resolve().parent/"data"/"MonthlyReturns_FullSample.xlsx")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    r,audit=load_and_audit(args.data)
    weights,predictions,model_config=frozen_weights(r)
    assert (predictions.index.get_level_values("formation_date") < predictions.return_date).all()
    observed=predictions.label.notna()
    assert (predictions.loc[observed,"label"] == predictions.loc[observed,"target"].gt(0)).all()
    for w in weights.values():assert np.isfinite(w.to_numpy()).all()
    prefix_result=prefix_check(r,weights)
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    masks={n:(w.shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for n,w in weights.items()}
    missing=pd.DataFrame(masks)
    rows=[]
    periods=[("development_2005_2014","2005-01-01","2014-12-31"),
             ("OOS_2015_onward","2015-01-01",None),("OOS_2015_2019","2015-01-01","2019-12-31"),
             ("OOS_2020_onward","2020-01-01",None)]
    for period,start,end in periods:
        for n,b in runs.items():
            sample=b.loc[start:end]
            rows.append(dict(strategy=n,period=period,start=str(sample.index.min().date()),end=str(sample.index.max().date()),
                **evaluate(sample.net),gross_sharpe=evaluate(sample.gross)["sharpe_zero_rf"],
                annual_cost=12*sample.tcost.mean(),annual_turnover=12*sample.turnover.mean(),
                mean_gross_exposure=sample.leverage.mean(),missing_held_months=int(masks[n].loc[start:end].sum())))
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/"performance_summary.csv",index=False)
    net.to_csv(OUT/"monthly_net_returns_full_history.csv")
    net.loc["2015-01-01":].to_csv(OUT/"oos_monthly_net_returns.csv")
    missing.loc["2015-01-01":].to_csv(OUT/"oos_missing_held_returns.csv")
    predictions.loc[predictions.return_date.ge("2015-01-01")].to_csv(OUT/"oos_classifier_predictions.csv")
    valid=~missing.any(axis=1)
    strict=net.loc["2015-01-01":].loc[valid]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in strict]).to_csv(OUT/"strict_common_month_sensitivity.csv",index=False)
    all_class=[]
    for name,start,end in [("OOS_full","2015-01-01",None),("OOS_2015_2019","2015-01-01","2019-12-31"),("OOS_2020_onward","2020-01-01",None)]:
        valid_prediction=predictions.return_date.ge(start)&predictions.label.notna()
        if end:valid_prediction &= predictions.return_date.le(end)
        pp=predictions.loc[valid_prediction]
        all_class.append(dict(period=name,**classification_metrics(pp.label,pp.probability_up)))
    pd.DataFrame(all_class).to_csv(OUT/"oos_classification_metrics.csv",index=False)
    for n,w in weights.items():w.loc["2014-12-01":].to_csv(OUT/f"{n}_formation_weights.csv")
    selected=["TSMOM","TSMOM_ResidualMomentum30","TSMOM_NegativeSkew20","TSMOM_SignHistGB30"]
    fig,(ax,dd)=plt.subplots(2,1,figsize=(12,8),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[2,1]})
    colors=["#287bb5","#2b9854","#cb8e32","#9a69b5"]
    labels=["Original TSMOM","70/30 TSMOM + residual momentum","80/20 TSMOM + negative skew","70/30 TSMOM + sign classifier"]
    oos=net.loc["2015-01-01":,selected]
    wealth=(1+oos).cumprod()
    initial=pd.DataFrame(1.,index=[pd.Timestamp("2014-12-31")],columns=selected)
    wealth=pd.concat([initial,wealth])
    for n,color,label in zip(selected,colors,labels):
        ax.plot(np.log(wealth[n]),label=label,color=color,lw=1.8)
        dd.plot(wealth[n]/wealth[n].cummax()-1,color=color,lw=1.5)
    ax.set(title=f"Frozen strategies: out-of-sample Jan 2015 – {oos.index[-1]:%b %Y}",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=9)
    from matplotlib.ticker import PercentFormatter
    dd.yaxis.set_major_formatter(PercentFormatter(1));dd.set_ylabel("Drawdown")
    for panel in (ax,dd):panel.grid(alpha=.2);panel.spines[["top","right"]].set_visible(False)
    fig.supxlabel("Monthly rebalance | Original 10% volatility target, 2 bps trades + quarterly rolls | No OOS tuning\n"
        "Native missing-held-return zero treatment retained for comparability; strict sensitivity exported separately.",fontsize=9)
    fig.savefig(OUT/"oos_strategy_comparison.png",dpi=180)
    fig.savefig(OUT/"oos_strategy_comparison.pdf")
    cfg=dict(strategy_parameters="Frozen: residual30%, negative-skew20%, HistGB soft30%; native economic_trend.py risk/cost rules",
        risk_update="rolling forecasts updated causally; classifier fit frozen before 1995",**model_config,
        no_oos_selection=True,prefix_check=prefix_result)
    (OUT/"frozen_config.json").write_text(json.dumps(cfg,indent=2,default=str))
    print(prefix_result)
    print(summary.loc[summary.period.eq("OOS_2015_onward")].round(5).to_string(index=False))
    print(pd.DataFrame(all_class).round(5).to_string(index=False))


if __name__=="__main__":main()
