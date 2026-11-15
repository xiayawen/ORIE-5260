"""Annual rolling-window HistGB sign forecasts with past-only fitting.

Compare fixed 15/20-year windows on pre-2015 validation; do not tune on later data.
"""
from pathlib import Path
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
from sign_return_prediction import prepare, directional_sleeve, classification_metrics
from out_of_sample_full_data import load_and_audit
from futures_factor_backtest import evaluate

OUT=Path(__file__).resolve().parent/"outputs"/"rolling_sign_prediction"


def estimator():
    return make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
        HistGradientBoostingClassifier(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,
            l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260))


def rolling_predictions(data,x,y,window,start_year=1997,end_year=None):
    predictions=pd.Series(np.nan,index=data.index)
    priors=predictions.copy()
    audits=[]
    final_year=int(data.return_date.dt.year.max()) if end_year is None else end_year
    for year in range(start_year,final_year+1):
        future=data.return_date.dt.year.eq(year)
        if not future.any():continue
        first_formation=data.index.get_level_values("formation_date")[future].min()
        lower=first_formation-pd.DateOffset(years=window)
        known=data.return_date.ge(lower)&data.return_date.lt(first_formation)&y.notna()
        train=data.loc[known]
        assert train.return_date.max()<first_formation
        assert train.return_date.min()>=lower
        assert not train.index.intersection(data.index[future]).size
        model=estimator()
        model.fit(x.loc[known],y.loc[known].astype(int))
        predictions.loc[future]=model.predict_proba(x.loc[future])[:,1]
        prior=float(y.loc[known].mean())
        priors.loc[future]=prior
        assert np.allclose(model[0].statistics_,x.loc[known].median().fillna(0),equal_nan=True)
        audits.append(dict(window_years=window,forecast_year=year,train_rows=len(train),
            allowed_label_start=str(lower.date()),actual_label_start=str(train.return_date.min().date()),
            last_training_label=str(train.return_date.max().date()),first_formation=str(first_formation.date()),
            last_formation=str(data.index.get_level_values(0)[future].max().date()),
            forecast_rows=int(future.sum()),training_positive_rate=prior))
        if year%5==0:print(f"{window}-year window: forecasts through {year}",flush=True)
    return predictions,priors,audits


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Shared loader preserves all original pre-2015 observations and audits Excel.
    # Redirect its audit artifacts here rather than overwrite the frozen study.
    import out_of_sample_full_data as frozen_io
    frozen_io.OUT=OUT
    path=Path(__file__).resolve().parent/"data"/"MonthlyReturns_FullSample.xlsx"
    r,audit=load_and_audit(path)
    data,x,y,classes,signals=prepare(r)
    predictions={};audits=[];priors={}
    for window in (15,20):
        p,prior,a=rolling_predictions(data,x,y,window)
        predictions[f"Rolling{window}y"]=p
        priors[f"Rolling{window}y_Prior"]=prior
        audits.extend(a)
    first_1995=data.loc[data.return_date.ge("1995-01-01")].index.get_level_values(0).min()
    known=data.return_date.lt(first_1995)&y.notna()
    fixed=estimator();fixed.fit(x.loc[known],y.loc[known].astype(int))
    live=data.return_date.ge("1997-01-01")
    predictions["Frozen1994"]=pd.Series(np.nan,index=data.index)
    predictions["Frozen1994"].loc[live]=fixed.predict_proba(x.loc[live])[:,1]
    # Identical live start for all model sleeves, so no in-sample risk histories.
    core=econ.price_trend_weights(r)
    weights={"TSMOM":core,"TSMOM_rescaled_control":econ.scale_to_target(core,r)}
    for name,p in predictions.items():
        matrix=p.unstack("instrument").reindex(index=r.index,columns=r.columns)
        extra=directional_sleeve(2*matrix-1,r)
        weights[name+"_Standalone"]=extra
        for fraction in (.1,.2,.3):
            weights[f"{name}_{int(fraction*100)}pct"]=econ.scale_to_target((1-fraction)*core+fraction*extra,r)
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    # Both windows require sufficient calendar history; 1997–1999 is warmup.
    candidates=[n for n in net if n.startswith("Rolling") and n.endswith("pct")]+["TSMOM","TSMOM_rescaled_control"]
    validation=net.loc["2000-01-01":"2004-12-31",candidates]
    ranking=pd.DataFrame([dict(strategy=n,**evaluate(validation[n])) for n in candidates]).sort_values("sharpe_zero_rf",ascending=False)
    winner=ranking.iloc[0].strategy
    best_rolling=ranking.loc[ranking.strategy.str.startswith("Rolling")].iloc[0].strategy
    chosen_window=int(best_rolling.split("_")[0].replace("Rolling","").replace("y",""))
    names=list(dict.fromkeys(["TSMOM","TSMOM_rescaled_control","Frozen1994_30pct",winner,best_rolling,
                             "Rolling15y_30pct","Rolling20y_30pct",f"Rolling{chosen_window}y_Standalone"]))
    rows=[]
    for name in names:
        for period,start,end in [("development_2005_2014","2005-01-01","2014-12-31"),
             ("later_2015_2025","2015-01-01",None),("later_2015_2019","2015-01-01","2019-12-31"),
             ("later_2020_onward","2020-01-01",None)]:
            b=runs[name].loc[start:end]
            rows.append(dict(strategy=name,period=period,**evaluate(b.net),
                gross_exposure=b.leverage.mean(),annual_cost=b.tcost.mean()*12))
    metric_rows=[]
    periods=[("validation","2000-01-01","2004-12-31"),("development_2005_2014","2005-01-01","2014-12-31"),
             ("later_2015_2025","2015-01-01","2025-12-31")]
    for name,p in {**predictions,**priors}.items():
        for period,start,end in periods:
            mask=data.return_date.between(start,end)&y.notna()&p.notna()
            metric_rows.append(dict(model=name,period=period,**classification_metrics(y.loc[mask],p.loc[mask])))
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/"portfolio_summary.csv",index=False)
    pd.DataFrame(metric_rows).to_csv(OUT/"classification_metrics.csv",index=False)
    pd.DataFrame(audits).to_csv(OUT/"annual_training_audit.csv",index=False)
    pred=data[["target","return_date"]].assign(label=y)
    for name,p in {**predictions,**priors}.items():pred[name]=p
    pred.loc[live].to_csv(OUT/"annual_oof_predictions.csv")
    ranking.to_csv(OUT/"validation_window_selection.csv",index=False)
    net.to_csv(OUT/"all_net_returns_audit.csv")
    net.loc["2015-01-01":,names].to_csv(OUT/"selected_later_net_returns.csv")
    missing=pd.concat([(weights[n].shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for n in names],axis=1).any(axis=1)
    strict=net.loc["2015-01-01":,names].loc[~missing]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in names]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    for n in names:weights[n].loc["2014-12-01":].to_csv(OUT/f"{n}_weights.csv")
    (OUT/"config.json").write_text(json.dumps(dict(model=estimator()[-1].get_params(),
        features=list(x),refit="annual, before first formation date of each return year",
        windows=[15,20],warmup="1997–1999",validation="2000–2004 net portfolio Sharpe",
        selected_strategy=winner,best_rolling=best_rolling,
        target="next-month positive vs negative return; zero/missing labels excluded",
        embargo="last training label strictly before first prediction formation date",
        latest_window_example=[a for a in audits if a['forecast_year']==2015],
        warning="2015 onward previously inspected; rolling development evaluation, not a pristine holdout"),indent=2,default=str))
    fig,(ax,dd)=plt.subplots(2,1,figsize=(12,8),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[2,1]})
    display=list(dict.fromkeys(["TSMOM","Frozen1994_30pct",best_rolling]))
    later=net.loc["2015-01-01":,display]
    wealth=pd.concat([pd.DataFrame(1.,index=[pd.Timestamp("2014-12-31")],columns=display),(1+later).cumprod()])
    for n in display:
        ax.plot(np.log(wealth[n]),label=n,lw=1.8)
        dd.plot(wealth[n]/wealth[n].cummax()-1,lw=1.5)
    from matplotlib.ticker import PercentFormatter
    dd.yaxis.set_major_formatter(PercentFormatter(1));dd.set_ylabel("Drawdown")
    ax.set(title="Annual rolling-window sign classifier + original TSMOM (2015–2025)",ylabel="Log cumulative net return")
    ax.legend(frameon=False);ax.grid(alpha=.2);dd.grid(alpha=.2)
    fig.supxlabel("Window/share selected on 2000–2004 only | Annual train-only imputation/refit | Native trading + roll costs\n"
                  "Later period already inspected; no new untouched holdout claim.",fontsize=9)
    fig.savefig(OUT/"rolling_window_comparison.png",dpi=180)
    print("SELECTED",winner,"BEST ROLLING",best_rolling)
    print(ranking.round(5).to_string(index=False))
    print(summary.loc[summary.period.eq("later_2015_2025")].round(5).to_string(index=False))
    print(pd.DataFrame(metric_rows).query("period == 'later_2015_2025'").round(5).to_string(index=False))


if __name__=="__main__":main()
