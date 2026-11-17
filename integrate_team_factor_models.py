"""Compare team combinations with legacy HistGB vs frozen Extra Trees 66/86."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from combined_strategy import Pipeline,stats,net_returns,EXCLUSIVE,COMPONENTS
from risk_budgeting import ROOT,read_full_sample_returns,IS_START,IS_END,OOS_START

OUT=ROOT/"outputs"/"integrated_factor_models"
ML={"HistGB15y":"histgb_overlay","ExtraTrees66":"extratrees_overlay",
    "ExtraTrees86":"extratrees_crossasset_overlay"}


def configurations():
    common={"economic_trend","factor_overlay","turning_point","half_short","net_cap","band_25"}
    contexts={"ContinuousCore":{"continuous_signal"},
        "AllContinuous":common|{"continuous_signal","smooth_leverage_imbalance"},
        "AllRiskBudget":common|{"risk_budget","smooth_leverage_imbalance"}}
    configs={"ExistingFinal":frozenset({"continuous_signal"})}
    for context,flags in contexts.items():
        for name,component in ML.items():configs[f"{context}_{name}"]=frozenset(flags|{component})
    for c in configs.values():assert all(len(c&g)<=1 for g in EXCLUSIVE)
    assert not any(c in COMPONENTS for c in ["extratrees_overlay","extratrees_crossasset_overlay"])
    return configs


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    file=ROOT/"MonthlyReturns_FullSample.xlsx"
    if not file.exists():file=ROOT/"data"/"MonthlyReturns_FullSample.xlsx"
    macro=ROOT/"macro_data"
    if not macro.exists():macro=ROOT/"data"
    pipe=Pipeline(read_full_sample_returns(file),macro_dir=macro)
    configs=configurations()
    runs={};rows=[];exposures=[]
    for name,config in configs.items():
        print("Running",name,flush=True)
        executed=pipe.executed(config)
        assert np.isfinite(executed.to_numpy()).all()
        assert executed.abs().sum(axis=1).le(4+1e-8).all()
        executed.to_csv(OUT/f"{name}_executed_weights.csv")
        runs[name]=pipe.evaluate(executed)
        for period,start,end in [("IS",IS_START,IS_END),("validation_2008_2014","2008-01-01","2014-11-30"),
                                  ("later_2015_2025",OOS_START,None),
                                  ("later_2015_2019",OOS_START,"2019-12-31"),("later_2020_onward","2020-01-01",None)]:
            for cost in ("slide_2bps","lecture8"):
                rows.append(dict(strategy=name,period=period,costs=cost,**stats(runs[name],start,end,cost)))
        for stage,w in [("mixed_target",pipe.targeted(config)),("controlled",pipe.formed(config)),("executed",executed)]:
            s=w.loc[OOS_START:]
            exposures.append(dict(strategy=name,stage=stage,gross=s.abs().sum(axis=1).mean(),net=s.sum(axis=1).mean()))
    net=pd.DataFrame({n:net_returns(b) for n,b in runs.items()})
    pd.DataFrame(rows).to_csv(OUT/"performance_summary.csv",index=False)
    pd.DataFrame(exposures).to_csv(OUT/"exposure_by_stage.csv",index=False)
    net.to_csv(OUT/"monthly_net_returns.csv")
    probabilities,audit=pipe.extratrees_forecast_data()
    audit.to_csv(OUT/"classifier_training_audit.csv",index=False)
    for name,p in probabilities.items():p.to_csv(OUT/f"{name}_probabilities.csv")
    coverage=pd.DataFrame({n:p.notna().sum(axis=1) for n,p in probabilities.items()})
    coverage.to_csv(OUT/"forecast_coverage.csv")
    (OUT/"integration_config.json").write_text(json.dumps(dict(
        configurations={n:sorted(c) for n,c in configs.items()},
        classifier_settings="200 Extra Trees, depth6, leaf30, max_features0.7, seed5260; median imputation from respective train only",
        features={"ExtraTrees66":"31 original raw factors, 31 class ranks, 4 class indicators",
                  "ExtraTrees86":"above plus10 cross-asset factors and10 class ranks"},
        fitting="pre2005 model for out-of-training development forecasts; single pre2015 refit then frozen; no annual Extra Trees refits",
        signal="2*p(up)-1; native branch EWMA instrument sizing and covariance sleeve scaling",
        ML_share=.3,all_modules_shares=dict(core=.3,macro=.2,negative_skew=.2,ML=.3),
        old_search="optional components excluded from original stepwise/default candidate pools",
        caveat="descriptive integration ablations; no later-period winner selection; prior research already inspected2015 onward"),indent=2))
    display=["ExistingFinal",*[f"AllContinuous_{n}" for n in ML]]
    later=net.loc[OOS_START:,display]
    wealth=pd.concat([pd.DataFrame(1.,index=[pd.Timestamp("2014-12-31")],columns=display),(1+later).cumprod()])
    fig,(ax,dd)=plt.subplots(2,1,figsize=(12,8),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[2,1]})
    for n in display:
        ax.plot(np.log(wealth[n]),label=n,lw=1.8)
        dd.plot(wealth[n]/wealth[n].cummax()-1,lw=1.5)
    from matplotlib.ticker import PercentFormatter
    dd.yaxis.set_major_formatter(PercentFormatter(1));dd.set_ylabel("Drawdown")
    ax.set(title="Team modules + our factor/classifier sleeves (2015–2025)",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.2);dd.grid(alpha=.2)
    fig.supxlabel("Replace the30% ML slot, do not stack classifiers | Identical native risk/execution/cost rules\n"
                  "Extra Trees fits frozen before2015; HistGB retains legacy annual15y refits. Descriptive, already inspected later period.",fontsize=9)
    fig.savefig(OUT/"integrated_model_comparison.png",dpi=180)
    print(pd.DataFrame(rows).query("period=='later_2015_2025' and costs=='slide_2bps'")[["strategy","net_cagr","annual_net_return","annual_volatility","net_sharpe","max_drawdown","average_gross_exposure"]].round(5).to_string(index=False))


if __name__=="__main__":main()
