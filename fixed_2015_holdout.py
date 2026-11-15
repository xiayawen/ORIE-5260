"""All eligible pre-2015 development data; one refit; fixed 2015–2025 test."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
import economic_trend as econ
import out_of_sample_full_data as loader
from sign_return_prediction import prepare,directional_sleeve,classification_metrics
from tree_factor_prediction import purge
from futures_factor_backtest import evaluate

OUT=Path(__file__).resolve().parent/"outputs"/"fixed_2015_holdout"


def make_model(name):
    specs={
      "Logistic":LogisticRegression(C=.1,max_iter=3000,random_state=5260),
      "RandomForest":RandomForestClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
      "ExtraTrees":ExtraTreesClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2),
      "HistGB":HistGradientBoostingClassifier(max_iter=100,max_depth=3,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=10,learning_rate=.05,early_stopping=False,random_state=5260)}
    steps=[SimpleImputer(strategy="median",keep_empty_features=True)]
    if name=="Logistic":steps.append(StandardScaler())
    return make_pipeline(*steps,specs[name])


def split(data,y):
    validation=data.loc[data.return_date.ge("2005-01-01")&data.return_date.lt("2015-01-01")]
    test=data.loc[data.return_date.ge("2015-01-01")]
    train=purge(data.loc[data.return_date.lt("2005-01-01")&y.notna()],validation)
    final=purge(data.loc[data.return_date.lt("2015-01-01")&y.notna()],test)
    # Selection labels must be known strictly before the first test formation.
    selection=purge(validation,test)
    return train,validation,selection,final,test


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    loader.OUT=OUT
    r,audit=loader.load_and_audit(Path(__file__).resolve().parent/"data"/"MonthlyReturns_FullSample.xlsx")
    # Include the earliest eligible observations, not an arbitrary 1976 cutoff.
    data,x,y,classes,signals=prepare(r,evaluation_start="1969-01-01")
    train,validation,selection,final,test=split(data,y)
    model_names=["Logistic","RandomForest","ExtraTrees","HistGB"]
    validation_prob={};selection_rows=[]
    for name in model_names:
        model=make_model(name)
        model.fit(x.loc[train.index],y.loc[train.index].astype(int))
        assert np.allclose(model[0].statistics_,x.loc[train.index].median().fillna(0),equal_nan=True)
        p=pd.Series(model.predict_proba(x.loc[validation.index])[:,1],index=validation.index)
        validation_prob[name]=p
        observed=selection.index[y.loc[selection.index].notna()]
        selection_rows.append(dict(model=name,**classification_metrics(y.loc[observed],p.loc[observed])))
    classifier_ranking=pd.DataFrame(selection_rows).sort_values("log_loss")
    winner=classifier_ranking.iloc[0].model
    # Risk warmup uses only validation forecasts made by the earlier model.
    # Never use final-model in-sample predictions as a sleeve risk history.
    core=econ.price_trend_weights(r)
    vp=validation_prob[winner].unstack("instrument").reindex(index=r.index,columns=r.columns)
    val_sleeve=directional_sleeve(2*vp-1,r)
    val_weights={0.:core}
    for fraction in (.1,.2,.3):val_weights[fraction]=econ.scale_to_target((1-fraction)*core+fraction*val_sleeve,r)
    portfolio_rows=[]
    selection_end=selection.return_date.max()
    for fraction,w in val_weights.items():
        b=econ.backtest(w,r).loc["2008-01-01":selection_end]
        portfolio_rows.append(dict(share=fraction,**evaluate(b.net)))
    portfolio_ranking=pd.DataFrame(portfolio_rows).sort_values("sharpe_zero_rf",ascending=False)
    share=float(portfolio_ranking.iloc[0].share)
    positive_share=float(portfolio_ranking.loc[portfolio_ranking.share.gt(0)].iloc[0].share)
    # The only final fit: every eligible observed nonzero pre-test label.
    model=make_model(winner)
    model.fit(x.loc[final.index],y.loc[final.index].astype(int))
    assert np.allclose(model[0].statistics_,x.loc[final.index].median().fillna(0),equal_nan=True)
    test_p=pd.Series(model.predict_proba(x.loc[test.index])[:,1],index=test.index)
    p=pd.concat([validation_prob[winner],test_p])
    assert not p.index.has_duplicates
    matrix=p.unstack("instrument").reindex(index=r.index,columns=r.columns)
    extra=directional_sleeve(2*matrix-1,r)
    weights={"TSMOM":core,"TSMOM_rescaled_control":econ.scale_to_target(core,r),
             "SelectedStrategy":core if share==0 else econ.scale_to_target((1-share)*core+share*extra,r),
             "BestPositiveOverlay":econ.scale_to_target((1-positive_share)*core+positive_share*extra,r),
             "ClassifierStandalone":extra}
    runs={n:econ.backtest(w,r) for n,w in weights.items()}
    net=pd.DataFrame({n:b.net for n,b in runs.items()})
    results=[]
    for name,b in runs.items():
        for period,start,end in [("test_2015_2025","2015-01-01",None),
                                 ("test_2015_2019","2015-01-01","2019-12-31"),
                                 ("test_2020_onward","2020-01-01",None)]:
            q=b.loc[start:end]
            results.append(dict(strategy=name,period=period,**evaluate(q.net),
                cumulative_net_return=float((1+q.net).prod()-1),annual_cost=12*q.tcost.mean(),gross_exposure=q.leverage.mean()))
    observed=test.index[y.loc[test.index].notna()]
    test_metrics=[]
    for name,pred in [(winner,test_p),("FinalTrainPrior",pd.Series(y.loc[final.index].mean(),index=test.index)),
                      ("AlwaysUp",pd.Series(1.,index=test.index))]:
        test_metrics.append(dict(model=name,**classification_metrics(y.loc[observed],pred.loc[observed])))
    predictions=test[["return_date","target"]].assign(label=y.loc[test.index],probability_up=test_p)
    assert (predictions.index.get_level_values(0)<predictions.return_date).all()
    predictions.to_csv(OUT/"fixed_test_predictions.csv")
    pd.DataFrame(results).to_csv(OUT/"portfolio_results.csv",index=False)
    pd.DataFrame(test_metrics).to_csv(OUT/"test_classification_metrics.csv",index=False)
    classifier_ranking.to_csv(OUT/"validation_model_selection.csv",index=False)
    portfolio_ranking.to_csv(OUT/"validation_overlay_selection.csv",index=False)
    net.loc["2015-01-01":].to_csv(OUT/"test_net_returns.csv")
    split_audit=[]
    for name,d in [("initial_training",train),("validation_predictions",validation),("selection_labels",selection),
                   ("final_refit",final),("fixed_test",test)]:
        split_audit.append(dict(split=name,rows=len(d),observed_nonzero_labels=int(y.loc[d.index].notna().sum()),
            first_formation=str(d.index.get_level_values(0).min().date()),last_formation=str(d.index.get_level_values(0).max().date()),
            label_start=str(d.return_date.min().date()),label_end=str(d.return_date.max().date())))
    pd.DataFrame(split_audit).to_csv(OUT/"split_audit.csv",index=False)
    missing=pd.concat([(w.shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for w in weights.values()],axis=1).any(axis=1)
    strict=net.loc["2015-01-01":].loc[~missing]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in strict]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    for n,w in weights.items():
        assert np.isfinite(w.to_numpy()).all()
        w.loc["2014-12-01":].to_csv(OUT/f"{n}_weights.csv")
    cfg=dict(selected_model=winner,selected_share=share,best_positive_share=positive_share,
        model_parameters=model[-1].get_params(),features=list(x),
        rule="select model by validation log loss, share by validation net Sharpe including 0; refit once before test",
        validation="model 2005–Nov2014; sleeve warmup 2005–2007, share selection 2008–Nov2014",
        final_training="all eligible labels through Nov2014; Dec2014 embargoed",test="Jan2015–May2025, no model retraining",
        risk_history="earlier model validation predictions spliced to final model test probabilities; no in-sample warmup",
        warning="fixed chronological holdout by fitting rules; period already inspected in this conversation, not pristine")
    (OUT/"config.json").write_text(json.dumps(cfg,indent=2,default=str))
    display=["TSMOM","SelectedStrategy"]
    if share==0:display.append("BestPositiveOverlay")
    plot_labels={"TSMOM":"Original TSMOM","SelectedStrategy":f"Selected: {winner}, {share:.0%} sleeve",
                 "BestPositiveOverlay":f"Diagnostic overlay: {positive_share:.0%}"}
    later=net.loc["2015-01-01":,display]
    wealth=pd.concat([pd.DataFrame(1.,index=[pd.Timestamp("2014-12-31")],columns=display),(1+later).cumprod()])
    fig,(ax,dd)=plt.subplots(2,1,figsize=(12,8),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[2,1]})
    for name in display:
        ax.plot(np.log(wealth[name]),label=plot_labels[name],lw=1.8)
        dd.plot(wealth[name]/wealth[name].cummax()-1,lw=1.5)
    from matplotlib.ticker import PercentFormatter
    dd.yaxis.set_major_formatter(PercentFormatter(1));dd.set_ylabel("Drawdown")
    ax.set(title="Fixed 2015–2025 holdout: one pre-2015 model refit, no walk-forward",ylabel="Log cumulative net return")
    ax.legend(frameon=False);ax.grid(alpha=.2);dd.grid(alpha=.2)
    fig.supxlabel("Pre-2015 model/share selection and one final refit | Native TSMOM risk/cost rules\n"
                  "2015 onward has already been inspected; chronological holdout, not new untouched evidence.",fontsize=9)
    fig.savefig(OUT/"fixed_holdout_comparison.png",dpi=180)
    print("SELECTED",winner,"SHARE",share)
    print(pd.DataFrame(split_audit).to_string(index=False))
    print(classifier_ranking.round(5).to_string(index=False))
    print(portfolio_ranking.round(5).to_string(index=False))
    print(pd.DataFrame(results).query("period == 'test_2015_2025'").round(5).to_string(index=False))
    print(pd.DataFrame(test_metrics).round(5).to_string(index=False))


if __name__=="__main__":main()
