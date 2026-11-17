"""Switch on every compatible combined-strategy module; no return-based selection."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from combined_strategy import Pipeline,ALL_COMPONENTS_CONTINUOUS,POST_2015_DESIGN,EXCLUSIVE,stats,net_returns
from risk_budgeting import ROOT,read_full_sample_returns,IS_START,IS_END,OOS_START

OUT=ROOT/"outputs"/"all_modules_comparison"


def configurations():
    common={"economic_trend","factor_overlay","histgb_overlay","turning_point","half_short","net_cap","band_25"}
    result={"Final_selected":frozenset({"continuous_signal"}),
            "All_early_compatible":ALL_COMPONENTS_CONTINUOUS-POST_2015_DESIGN}
    for core in ("continuous_signal","risk_budget"):
        for smooth in ("smooth_leverage","smooth_leverage_imbalance"):
            result[f"All_{core}_{smooth}"]=frozenset(common|{core,smooth})
    for config in result.values():
        assert all(len(config&group)<=1 for group in EXCLUSIVE)
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/"MonthlyReturns_FullSample.xlsx"
    if not source.exists():source=ROOT/"data"/"MonthlyReturns_FullSample.xlsx"
    macro=ROOT/"macro_data"
    if not macro.exists():macro=ROOT/"data"
    r=read_full_sample_returns(source)
    pipe=Pipeline(r,macro_dir=macro)
    configs=configurations()
    runs={};rows=[];exposure=[]
    for name,config in configs.items():
        print("Running",name,flush=True)
        executed=pipe.executed(config)
        assert np.isfinite(executed.to_numpy()).all()
        assert executed.abs().sum(axis=1).le(4+1e-8).all()
        runs[name]=pipe.evaluate(executed)
        executed.to_csv(OUT/f"{name}_executed_weights.csv")
        formed=pipe.formed(config)
        targeted=pipe.targeted(config)
        for period,start,end in [("IS",IS_START,IS_END),("OOS",OOS_START,None)]:
            for convention in ("slide_2bps","lecture8"):
                rows.append(dict(strategy=name,period=period,costs=convention,
                    includes_post2015_rules=bool(config&POST_2015_DESIGN),**stats(runs[name],start,end,convention)))
            for stage,w in [("after_blend",targeted),("after_risk_controls",formed),("executed",executed)]:
                s=w.loc[start:end]
                exposure.append(dict(strategy=name,period=period,stage=stage,
                    average_gross=s.abs().sum(axis=1).mean(),average_net=s.sum(axis=1).mean()))
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/"all_modules_performance.csv",index=False)
    pd.DataFrame(exposure).to_csv(OUT/"exposure_by_stage.csv",index=False)
    net=pd.DataFrame({n:net_returns(b) for n,b in runs.items()})
    net.to_csv(OUT/"monthly_net_returns.csv")
    (OUT/"configurations.json").write_text(json.dumps(dict(
        variants={n:sorted(c) for n,c in configs.items()},data_file=str(source),macro_dir=str(macro),
        overlay_shares=dict(core=.3,economic_trend=.2,factor_overlay=.2,histgb_overlay=.3),
        pipeline="core -> signal sleeves -> covariance retarget -> turning reduction -> half short -> net cap -> smoothing -> gross cap -> no-trade-band execution",
        warning="All variants are descriptive; some rules were designed after examining 2015 onward. No new holdout or winner selection.",
        not_combinable=["continuous signal and risk-budget core", "two exposure smoothing alternatives"],
        unavailable="daily/weekly rebalance requires post2014 daily prices; monthly P&L cannot reconstruct it"),indent=2))
    fig,axes=plt.subplots(1,2,figsize=(14,5.2),layout="constrained")
    for ax,start,end,title in zip(axes,[IS_START,OOS_START],[IS_END,None],["IS 1976–2014","Later 2015–2025 (already inspected)"]):
        for name in configs:
            s=net.loc[start:end,name]
            ax.plot(np.log1p(s).cumsum(),label=name,lw=1.6)
        ax.set_title(title);ax.set_ylabel("Log cumulative net return");ax.grid(alpha=.2)
    axes[0].legend(frameon=False,fontsize=7)
    fig.supxlabel("All compatible modules, fixed component parameters | Lecture11 trading/roll costs | Four variants resolve mutually exclusive rules",fontsize=9)
    fig.savefig(OUT/"all_modules_wealth.png",dpi=180)
    print(summary.query("costs == 'slide_2bps'")[["strategy","period","net_cagr","annual_net_return","annual_volatility","net_sharpe","max_drawdown","average_gross_exposure"]].round(5).to_string(index=False))


if __name__=="__main__":main()
