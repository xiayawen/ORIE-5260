"""Fair controls, ablations, sleeve optimization and centralized implementation.

Calibration 2005–2009; validation 2010–Nov2014; freeze before 2015.
Only two existing Extra Trees input sets and four utility settings are compared.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import economic_trend as econ
from combined_strategy import Pipeline
from covariance_risk_validation import covariance,HALFLIFE
from risk_budgeting import ROOT,read_full_sample_returns,risk_budget_weights
from futures_factor_backtest import evaluate
from unified_portfolio import Limits,risk_normalize,constrain,blended_target,rebalance_metrics,fit_allocation,cost_aware_path
from turning_point_model.dynamic_speed import fit_frozen_mixing_parameters,dynamic_speed_direction

OUT=ROOT/"outputs"/"portfolio_optimization"
LIMITS=Limits()
CORE=np.array([1.,0.,0.,0.]);FIXED=np.array([.3,.2,.2,.3])


def build_inputs(r):
    """Common dated covariance for every strategy, without repeated sleeve caps."""
    macro=ROOT/"macro_data"
    if not macro.exists():macro=ROOT/"data"
    pipe=Pipeline(r,macro_dir=macro)
    classes=pipe.asset_class.copy()
    classes.loc[classes.index.isin(econ.RATE_FUTURES_IN_FX)]="FI"
    groups=[classes.eq(c).to_numpy() for c in sorted(classes.unique())]
    cube=np.zeros((len(r),len(r.columns),len(r.columns)))
    count=r.notna().cumsum();variance=r.expanding().var()
    for t,date in enumerate(r.index):
        known=(count.iloc[t]>=36)&variance.iloc[t].gt(0)
        active=np.flatnonzero(known)
        if len(active):cube[t][np.ix_(active,active)]=covariance(r.iloc[:t+1,active],HALFLIFE)[0]
    eligible=pipe.sleeve_vol.notna().to_numpy()
    def normalized(raw):return risk_normalize(raw.fillna(0).to_numpy()*eligible,cube)
    cont=normalized(econ.risk_weights(pipe.cont_signal,pipe.sleeve_vol))
    binary12=normalized(econ.risk_weights(pipe.signal,(r.rolling(12,min_periods=12).std()*np.sqrt(12)).where(pipe.sleeve_vol.notna())))
    binaryewma=normalized(econ.risk_weights(pipe.signal,pipe.sleeve_vol))
    themes=econ.macro_signals(r,macro).rolling(econ.SMOOTH_MONTHS,min_periods=1).mean()
    macro_parts=[]
    universe=econ.macro_universe(r.columns)
    for theme in econ.SIGNS.index:
        d=econ.theme_direction(themes[theme],theme,r.columns,classes)
        d.loc[:,~d.columns.isin(universe)]=0
        macro_parts.append(normalized(econ.risk_weights(d,pipe.sleeve_vol)))
    macro_unit=risk_normalize(sum(macro_parts)/len(macro_parts),cube)
    from futures_factor_backtest import build_signals
    score=build_signals(r)[0]["NegativeSkew_12m"]
    direction=pd.DataFrame(np.nan,index=r.index,columns=r.columns)
    for _,members in pipe.asset_class.groupby(pipe.asset_class):
        s=score[members.index].where(pipe.sleeve_vol[members.index].gt(0))
        ranks=s.rank(axis=1,pct=True)
        direction[members.index]=(2*ranks.sub(ranks.mean(axis=1),axis=0)).where(s.count(axis=1).ge(4))
    factor=normalized(econ.risk_weights(direction,pipe.sleeve_vol))
    probs,audit=pipe.extratrees_forecast_data()
    bases={}
    for name,p in probs.items():
        ml=normalized(econ.risk_weights(2*p-1,pipe.sleeve_vol))
        pieces=[cont,macro_unit,factor,ml]
        # Return unavailable sleeve budgets to the core, not idle cash.
        effective=[pieces[0]]+[np.where((np.abs(w).sum(axis=1)>0)[:,None],w,cont) for w in pieces[1:]]
        bases[name]=np.stack(effective,axis=1)
    return dict(r=r,cov=cube,groups=groups,eligible=eligible,bases=bases,
                binary12=binary12,binaryewma=binaryewma,classes=classes,audit=audit,pipe=pipe)


def statistics(b,dates,start,end=None):
    mask=dates>=pd.Timestamp(start)
    if end:mask &= dates<=pd.Timestamp(end)
    ret=pd.Series(b["net"][mask],index=dates[mask])
    result=evaluate(ret)
    result.update(annual_cost=float(np.mean((b["roll_cost"]+b["trade_cost"])[mask])*12),
        annual_turnover=float(np.mean(b["turnover"][mask])*12),
        gross_exposure=float(np.mean(b["gross_exposure"][mask])),
        absolute_net_exposure=float(np.mean(np.abs(b["net_exposure"][mask]))),
        cumulative_net_return=float((1+ret).prod()-1))
    return result


def hac_annual_mean_difference(series,max_lag=3):
    """Annualized mean difference with a Bartlett Newey-West confidence interval."""
    x=pd.Series(series).dropna().to_numpy(dtype=float);n=len(x)
    if n<2:return dict(months=n,annual_mean_difference=np.nan,hac_standard_error=np.nan,
                       confidence_lower=np.nan,confidence_upper=np.nan,t_statistic=np.nan)
    centered=x-x.mean();long_run=float(centered@centered/n)
    for lag in range(1,min(max_lag,n-1)+1):
        covariance=float(centered[lag:]@centered[:-lag]/n)
        long_run+=2*(1-lag/(min(max_lag,n-1)+1))*covariance
    annual=float(x.mean()*12);standard_error=float(np.sqrt(max(long_run,0)/n)*12)
    return dict(months=n,annual_mean_difference=annual,hac_standard_error=standard_error,
                confidence_lower=annual-1.96*standard_error,confidence_upper=annual+1.96*standard_error,
                t_statistic=annual/standard_error if standard_error>0 else np.nan)


def run_target(target,inp,tracking=None):
    returns=inp["r"].fillna(0).to_numpy()
    if tracking is None:return target,rebalance_metrics(target,returns)
    return cost_aware_path(target,inp["cov"],returns,inp["groups"],inp["eligible"],tracking,LIMITS)


def select_development(dev):
    dates=dev["r"].index
    # Utility fitting can safely crop old rows once signals/covariances are built.
    crop=dates>=pd.Timestamp("2004-10-01")
    train_dates=dates[crop]
    calibration=(train_dates>=pd.Timestamp("2005-01-01"))&(train_dates<=pd.Timestamp("2009-12-31"))
    validation_rows=[];fits={}
    for model,basis in dev["bases"].items():
        for risk in (2.,8.):
            for cost in (1.,3.):
                key=f"{model}_risk{risk:g}_cost{cost:g}"
                a,fit=fit_allocation(basis[crop],dev["cov"][crop],dev["r"].fillna(0).to_numpy()[crop],
                    dev["groups"],calibration,risk,cost,LIMITS)
                fits[key]=dict(allocation=a.tolist(),**fit)
                target=blended_target(basis,a,dev["cov"],dev["groups"],LIMITS)
                for tracking in (None,5.,20.):
                    _,b=run_target(target,dev,tracking)
                    validation_rows.append(dict(candidate=key,model=model,risk_aversion=risk,cost_aversion=cost,
                        tracking=tracking,**statistics(b,dates,"2010-01-01","2014-11-30")))
                print("Calibrated",key,np.round(a,3),flush=True)
    # Same feasible pure-trend and fixed-blend alternatives, not forced optimization.
    for name,a in [("PureTrend",CORE),("FixedFour",FIXED)]:
        for model,basis in dev["bases"].items():
            target=blended_target(basis,a,dev["cov"],dev["groups"],LIMITS)
            for tracking in (None,5.,20.):
                _,b=run_target(target,dev,tracking)
                validation_rows.append(dict(candidate=name,model=model,risk_aversion=np.nan,cost_aversion=np.nan,
                    tracking=tracking,**statistics(b,dates,"2010-01-01","2014-11-30")))
    for name,raw in [("FairBinary12",dev["binary12"]),("FairBinaryEWMA",dev["binaryewma"])]:
        target=constrain(raw,dev["cov"],dev["groups"],LIMITS)
        for tracking in (None,5.,20.):
            _,b=run_target(target,dev,tracking)
            validation_rows.append(dict(candidate=name,model="none",risk_aversion=np.nan,cost_aversion=np.nan,
                tracking=tracking,**statistics(b,dates,"2010-01-01","2014-11-30")))
    ranking=pd.DataFrame(validation_rows).sort_values("sharpe_zero_rf",ascending=False,kind="stable")
    optimized=ranking.loc[ranking.candidate.isin(fits)].iloc[0]
    selected=ranking.iloc[0]
    # Refit only the validation-selected utility parameters using all available
    # pre-test 2005–Nov2014 calibration labels, never the later-period returns.
    basis=dev["bases"][optimized.model]
    final_mask=(train_dates>=pd.Timestamp("2005-01-01"))&(train_dates<=pd.Timestamp("2014-11-30"))
    final_a,final_fit=fit_allocation(basis[crop],dev["cov"][crop],dev["r"].fillna(0).to_numpy()[crop],
        dev["groups"],final_mask,float(optimized.risk_aversion),float(optimized.cost_aversion),LIMITS)
    return ranking,selected,optimized,final_a,final_fit,fits


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reuse-frozen-selection",action="store_true",help="Reuse saved pre2015 choices for diagnostics; no reselection")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/"MonthlyReturns_FullSample.xlsx"
    if not source.exists():source=ROOT/"data"/"MonthlyReturns_FullSample.xlsx"
    r=read_full_sample_returns(source)
    dev=None
    if args.reuse_frozen_selection:
        frozen=json.loads((OUT/"frozen_selection.json").read_text())
        selected=pd.Series(frozen["selected_candidate"]);optimized=pd.Series(frozen["optimized_candidate"])
        a=np.array(frozen["final_allocation"]);fit=frozen["final_fit"];fits=frozen["calibration_fits"]
        ranking=pd.read_csv(OUT/"validation_selection.csv")
    else:
        print("Building development inputs only",flush=True)
        dev=build_inputs(r.loc[:"2014-12-31"])
        ranking,selected,optimized,a,fit,fits=select_development(dev)
    ranking.to_csv(OUT/"validation_selection.csv",index=False)
    config=dict(selected_candidate=selected.to_dict(),optimized_candidate=optimized.to_dict(),final_allocation=a.tolist(),
        final_fit=fit,calibration_fits=fits,limits=LIMITS.__dict__,sleeve_order=["trend","macro","factor","ML"],
        training="2005–2009 utility fit;2010–Nov2014 validation; selected utility refit2005–Nov2014",
        expected_return="50% shrinkage of calibration gross annual mean; not a guaranteed true alpha",
        objective="0.5*annual mean gross - risk_aversion/2*mean forecast variance - cost_aversion*annual actual netted costs -0.01*||a-core||^2",
        tax=0,allocation_bounds="core>=30%, each noncore0–30%, sum1",
        execution="tracking-risk plus trading/roll cost along feasible prior-to-target segment; forced risk repairs cannot be postponed",
        cost="2bps actual NAV-drift-adjusted net trades +4 annual rolls; differs from legacy unnormalized slide accounting",
        class_risk="each class standalone predicted vol<=5%; not equal Euler PCR",
        warning="2015 onward repeatedly inspected; descriptive fixed-rule evaluation, no new untouched holdout")
    (OUT/"frozen_selection.json").write_text(json.dumps(config,indent=2,default=str))
    print("Frozen selection",selected.candidate,"optimized weights",a,flush=True)
    print("Building full evaluation inputs after freezing choices",flush=True)
    full=build_inputs(r)
    if dev is not None:
        for model in dev["bases"]:
            assert np.allclose(full["bases"][model][:len(dev["r"])-1],dev["bases"][model][:-1],equal_nan=True),model
    model=optimized.model
    basis=full["bases"][model];cov=full["cov"];groups=full["groups"]
    targets={"FairBinary12":constrain(full["binary12"],cov,groups,LIMITS),
        "FairBinaryEWMA":constrain(full["binaryewma"],cov,groups,LIMITS)}
    allocations={"PureTrend":CORE,"TrendMacro":np.array([.8,.2,0,0]),
        "TrendFactor":np.array([.8,0,.2,0]),"TrendML":np.array([.7,0,0,.3]),
        "FixedFour":FIXED,"OptimizedFour":a}
    for name,allocation in allocations.items():targets[name]=blended_target(basis,allocation,cov,groups,LIMITS)
    raw_fixed=np.einsum("tki,k->ti",basis,FIXED)
    disagreement,opposition=full["pipe"].turning_flags()
    turning_modifier=np.where((disagreement&opposition).to_numpy(),.5,1.)
    targets["FixedFour_Turning"]=blended_target(basis,FIXED,cov,groups,LIMITS,turning_modifier)
    targets["FixedFour_HalfShort"]=constrain(np.where(raw_fixed<0,.5*raw_fixed,raw_fixed),cov,groups,LIMITS)
    from exposure_smoothing_backtest import smooth_exposure
    smooth=smooth_exposure(pd.DataFrame(raw_fixed,index=r.index,columns=r.columns))[1]
    targets["FixedFour_ExposureSmooth"]=constrain(smooth.to_numpy(),cov,groups,LIMITS)
    # Conditional ablations reassign removed sleeve budget to trend without refitting.
    for j,name in enumerate(["Macro","Factor","ML"],start=1):
        ab=a.copy();ab[0]+=ab[j];ab[j]=0
        targets["Optimized_without_"+name]=blended_target(basis,ab,cov,groups,LIMITS)
    tracking=None if pd.isna(optimized.tracking) else float(optimized.tracking)
    implementations={};actual={}
    for name,target in targets.items():
        actual[name],implementations[name]=run_target(target,full)
    actual["OptimizedCostAware"],implementations["OptimizedCostAware"]=run_target(targets["OptimizedFour"],full,tracking)
    for source_name in ("FixedFour","PureTrend","FairBinary12"):
        name=source_name+"CostAware"
        actual[name],implementations[name]=run_target(targets[source_name],full,tracking)
    chosen_tracking=None if pd.isna(selected.tracking) else float(selected.tracking)
    if selected.candidate in ("FairBinary12","FairBinaryEWMA"):
        if chosen_tracking is None:selected_name=selected.candidate
        else:
            actual["ValidationSelected"],implementations["ValidationSelected"]=run_target(targets[selected.candidate],full,chosen_tracking)
            selected_name="ValidationSelected"
    elif selected.candidate in ("PureTrend","FixedFour"):
        selected_basis=full["bases"][selected.model]
        allocation=CORE if selected.candidate=="PureTrend" else FIXED
        t=blended_target(selected_basis,allocation,cov,groups,LIMITS)
        actual["ValidationSelectedFullRebalance"],implementations["ValidationSelectedFullRebalance"]=run_target(t,full)
        actual["ValidationSelected"],implementations["ValidationSelected"]=run_target(t,full,chosen_tracking)
        if selected.candidate=="FixedFour":
            # Apply the previously frozen turning-point rule only after the
            # common portfolio risk constraints.  This preserves the intended
            # conditional de-risking instead of re-levering the reduced target.
            # Execution and all remaining assumptions are identical to the
            # validation-selected FixedFour comparison above.
            turning_raw=t*turning_modifier
            turning_target=constrain(turning_raw,cov,groups,LIMITS)
            # A one-sided reduction can increase absolute net exposure by
            # removing an offsetting position. Repair any resulting breach,
            # but do not scale a compliant reduced target back up.
            relevered=np.linalg.norm(turning_target,axis=1)>np.linalg.norm(turning_raw,axis=1)+1e-12
            turning_target[relevered]=turning_raw[relevered]
            actual["ValidationSelected_Turning"],implementations["ValidationSelected_Turning"]=run_target(
                turning_target,full,chosen_tracking)
            # Paper-inspired state-dependent slow/fast blend. Parameters use
            # returns through 2004 only and are frozen before the first live
            # target formed at 2004-12 for execution in 2005-01.
            speed_parameters=fit_frozen_mixing_parameters(r,"2004-12-31")
            speed_parameters.to_csv(OUT/"dynamic_speed_parameters.csv")
            speed_direction=dynamic_speed_direction(r,speed_parameters)
            speed_raw=econ.risk_weights(speed_direction,full["pipe"].sleeve_vol).fillna(0).to_numpy()
            speed_core=risk_normalize(speed_raw*full["eligible"],cov)
            static_core=full["binaryewma"]

            def replace_core(source,new_core):
                """Replace core and return inactive sleeve budgets to that core."""
                out=source.copy();old_core=source[:,0].copy()
                for sleeve in range(1,source.shape[1]):
                    active=np.abs(source[:,sleeve]-old_core).sum(axis=1)>1e-12
                    out[:,sleeve]=np.where(active[:,None],source[:,sleeve],new_core)
                out[:,0]=new_core
                return out

            static_target=blended_target(replace_core(selected_basis,static_core),allocation,cov,groups,LIMITS)
            speed_target=blended_target(replace_core(selected_basis,speed_core),allocation,cov,groups,LIMITS)
            live=r.index>=pd.Timestamp("2004-12-31")
            static_target=np.where(live[:,None],static_target,t)
            speed_target=np.where(live[:,None],speed_target,t)
            actual["ValidationSelected_StaticSlow"],implementations["ValidationSelected_StaticSlow"]=run_target(
                static_target,full,chosen_tracking)
            actual["ValidationSelected_DynamicSpeed"],implementations["ValidationSelected_DynamicSpeed"]=run_target(
                speed_target,full,chosen_tracking)
        for j,label in enumerate(["Macro","Factor","ML"],start=1):
            removed=allocation.copy();removed[0]+=removed[j];removed[j]=0
            ablation=blended_target(selected_basis,removed,cov,groups,LIMITS)
            name="ValidationSelected_without_"+label
            actual[name],implementations[name]=run_target(ablation,full,chosen_tracking)
        selected_name="ValidationSelected"
    else:selected_name="OptimizedCostAware"
    net=pd.DataFrame({n:b["net"] for n,b in implementations.items()},index=r.index)
    rows=[]
    for name,b in implementations.items():
        for period,start,end in [("IS_fitted_1976_2014","1976-01-01","2014-12-31"),
            ("later_2015_2025","2015-01-01",None),("later_2015_2019","2015-01-01","2019-12-31"),
            ("later_2020_onward","2020-01-01",None)]:
            rows.append(dict(strategy=name,period=period,**statistics(b,r.index,start,end)))
        pd.DataFrame(actual[name],index=r.index,columns=r.columns).to_csv(OUT/f"{name}_formed_weights.csv")
    summary=pd.DataFrame(rows);summary.to_csv(OUT/"performance_summary.csv",index=False)
    net.to_csv(OUT/"monthly_net_returns.csv")
    conditional=[]
    for name in net:
        if name in ("ValidationSelected","ValidationSelected_Turning","ValidationSelected_StaticSlow",
                    "ValidationSelected_DynamicSpeed") or name.startswith("ValidationSelected_without_"):
            for period,start,end in [("validation_diagnostic","2010-01-01","2014-11-30"),
                                      ("later_diagnostic","2015-01-01",None)]:
                x=net.loc[start:end,name]
                conditional.append(dict(strategy=name,period=period,months=len(x),
                    annual_mean=x.mean()*12,net_sharpe=x.mean()/x.std()*np.sqrt(12)))
    pd.DataFrame(conditional).to_csv(OUT/"selected_conditional_ablation.csv",index=False)
    speed_names=["ValidationSelected","ValidationSelected_Turning","ValidationSelected_StaticSlow",
                 "ValidationSelected_DynamicSpeed"]
    speed_periods=[("development_2005_2009","2005-01-01","2009-12-31"),
                   ("validation_2010_2014","2010-01-01","2014-11-30"),
                   ("pre2015_evaluation_2005_2014","2005-01-01","2014-12-31"),
                   ("later_2015_2025","2015-01-01",None)]
    speed_rows=[]
    for name in speed_names:
        if name not in implementations:continue
        for period,start,end in speed_periods:
            speed_rows.append(dict(strategy=name,period=period,**statistics(
                implementations[name],r.index,start,end)))
    pd.DataFrame(speed_rows).to_csv(OUT/"dynamic_speed_comparison.csv",index=False)
    incremental=[]
    pairs=[("turning_vs_selected","ValidationSelected_Turning","ValidationSelected"),
           ("static_slow_vs_selected","ValidationSelected_StaticSlow","ValidationSelected"),
           ("dynamic_speed_vs_selected","ValidationSelected_DynamicSpeed","ValidationSelected"),
           ("dynamic_speed_vs_static_slow","ValidationSelected_DynamicSpeed","ValidationSelected_StaticSlow")]
    for comparison,left,right in pairs:
        for period,start,end in speed_periods:
            difference=net.loc[start:end,left]-net.loc[start:end,right]
            incremental.append(dict(comparison=comparison,period=period,left=left,right=right,
                                    **hac_annual_mean_difference(difference)))
    pd.DataFrame(incremental).to_csv(OUT/"dynamic_speed_incremental_hac.csv",index=False)
    full["audit"].to_csv(OUT/"classifier_audit.csv",index=False)
    # Isolate the cost/risk trade-off without changing the selected configuration.
    legacy_rows=[]
    from combined_strategy import stats as legacy_stats
    for name,b in implementations.items():
        legacy=full["pipe"].evaluate(pd.DataFrame(b["executed"],index=r.index,columns=r.columns))
        for convention in ("slide_2bps","lecture8"):
            legacy_rows.append(dict(strategy=name,costs=convention,**legacy_stats(legacy,"2015-01-01",None,convention)))
    pd.DataFrame(legacy_rows).to_csv(OUT/"legacy_cost_sensitivity.csv",index=False)
    policy_rows=[]
    policies={"RiskGrossOnly":Limits(net=np.inf,class_volatility=np.inf),
              "AddNetLimit":Limits(class_volatility=np.inf),"AddClassRiskLimit":LIMITS}
    for policy,limits in policies.items():
        t=constrain(full["binary12"],cov,groups,limits)
        b=rebalance_metrics(t,r.fillna(0).to_numpy())
        for period,start,end in [("IS","1976-01-01","2014-12-31"),("later","2015-01-01",None)]:
            policy_rows.append(dict(policy=policy,period=period,**statistics(b,r.index,start,end)))
    pd.DataFrame(policy_rows).to_csv(OUT/"baseline_constraint_ablation.csv",index=False)
    diagnostics=[]
    for name,w in actual.items():
        v=np.einsum("ti,tij,tj->t",w,cov,w)
        assert (np.abs(w).sum(axis=1)<=LIMITS.gross+1e-7).all()
        assert (np.abs(w.sum(axis=1))<=LIMITS.net+1e-7).all()
        assert (v<=LIMITS.volatility**2+1e-9).all()
        for cls,group in zip(sorted(full["classes"].unique()),groups):
            wg=w*group
            standalone=np.einsum("ti,tij,tj->t",wg,cov,wg)
            assert (standalone<=LIMITS.class_volatility**2+1e-9).all()
            contribution=np.einsum("ti,tij,tj->t",wg,cov,w)
            share=np.divide(contribution,v,out=np.zeros_like(v),where=v>1e-16)
            mask=r.index>=pd.Timestamp("2015-01-01")
            diagnostics.append(dict(strategy=name,asset_class=cls,mean_exante_PCR=share[mask].mean(),
                mean_class_standalone_vol=np.sqrt(np.maximum(standalone[mask],0)).mean()))
    pd.DataFrame(diagnostics).to_csv(OUT/"class_risk_diagnostics.csv",index=False)
    # Matched missing-held-return sensitivity, not silent per-strategy sample changes.
    miss=np.zeros(len(r),dtype=bool)
    for b in implementations.values():miss|=((b["executed"]!=0)&r.isna().to_numpy()).any(axis=1)
    strict=(r.index>=pd.Timestamp("2015-01-01"))&~miss
    pd.DataFrame([dict(strategy=n,**evaluate(net.loc[strict,n])) for n in net]).to_csv(OUT/"strict_missing_sensitivity.csv",index=False)
    # Left-tail quarterly diagnostics for all main portfolios, current-period bins descriptive only.
    main=list(dict.fromkeys(["FairBinary12","FairBinary12CostAware","PureTrend","FixedFour",
                            "OptimizedFour","OptimizedCostAware",selected_name,
                            "ValidationSelected_Turning","ValidationSelected_StaticSlow",
                            "ValidationSelected_DynamicSpeed"]))
    main=[n for n in main if n in net]
    monthly=net.loc["2015-01-01":,main]
    quarter_end=pd.offsets.QuarterEnd()
    quarterly=(1+monthly).resample(quarter_end).prod()-1
    market=(1+r.SP.loc["2015-01-01":]).resample(quarter_end).prod()-1
    complete=monthly.resample(quarter_end).count().min(axis=1).eq(3)&r.SP.loc["2015-01-01":].resample(quarter_end).count().eq(3)
    quarterly=quarterly.loc[complete];market=market.reindex(quarterly.index)
    bins=pd.qcut(market,10,labels=False)+1
    tail=[]
    for n in main:
        for decile,value in (quarterly[n].groupby(bins).mean()*4).items():
            tail.append(dict(strategy=n,market_decile=decile,annualized_quarterly_return=value))
    pd.DataFrame(tail).to_csv(OUT/"quarterly_sp_smile.csv",index=False)
    display=[n for n in dict.fromkeys([selected_name,"ValidationSelected_Turning",
             "ValidationSelected_StaticSlow","ValidationSelected_DynamicSpeed"]) if n in net]
    later=net.loc["2015-01-01":,display]
    wealth=pd.concat([pd.DataFrame(1.,index=[pd.Timestamp("2014-12-31")],columns=display),(1+later).cumprod()])
    fig,(ax,dd)=plt.subplots(2,1,figsize=(12,8),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[2,1]})
    for n in display:
        ax.plot(np.log(wealth[n]),label=n,lw=1.6)
        dd.plot(wealth[n]/wealth[n].cummax()-1,lw=1.4)
    from matplotlib.ticker import PercentFormatter
    dd.yaxis.set_major_formatter(PercentFormatter(1));dd.set_ylabel("Drawdown")
    ax.set(title="Common constraints + optimized signal allocation + cost-aware execution",ylabel="Log cumulative net return")
    ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.2);dd.grid(alpha=.2)
    fig.supxlabel("Same10% risk cap,4x gross,1x net and5% standalone class-risk caps | Pre2015 calibration only\n"
                  "Netted NAV-drift trade costs + quarterly rolls. Later period already inspected.",fontsize=9)
    fig.savefig(OUT/"optimization_comparison.png",dpi=180)
    print("VALIDATION SELECTED",selected_name,"OPTIMIZED",model,a,"TRACKING",tracking)
    print(ranking.head(6).round(5).to_string(index=False))
    print(summary.query("period=='later_2015_2025'").round(5).to_string(index=False))


if __name__=="__main__":main()
