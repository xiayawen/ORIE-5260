"""Factor overlays using economic_trend.py's original TSMOM methodology."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import economic_trend as econ
from futures_factor_backtest import build_signals, evaluate

OUT = Path(__file__).resolve().parent / "outputs" / "tsmom_factor_overlay"


def construct(r, candidates):
    signals, _ = build_signals(r)
    vol = econ.instrument_vol(r)
    classes = econ.read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    core = econ.price_trend_weights(r, vol)
    extras = {}
    for name in candidates:
        direction = pd.DataFrame(np.nan, index=r.index, columns=r.columns)
        for _, members in classes.groupby(classes):
            score = signals[name][members.index].where(vol[members.index].gt(0))
            rank = score.rank(axis=1, pct=True)
            centered = 2 * rank.sub(rank.mean(axis=1), axis=0)
            direction[members.index] = centered.where(score.count(axis=1).ge(4), np.nan)
        extras[name] = econ.scale_to_target(econ.risk_weights(direction, vol), r)
    extras["EqualDefensiveBasket"] = econ.scale_to_target(sum(extras.values()) / len(extras), r)
    weights = {"TSMOM": core, "TSMOM_rescaled_control": econ.scale_to_target(core, r)}
    configs = {"TSMOM": dict(overlay="none", fraction=0),
               "TSMOM_rescaled_control": dict(overlay="none_rescaled", fraction=0)}
    for name, extra in extras.items():
        for fraction in (.1, .2, .3, .4):
            key = f"TSMOM_{name}_{int(fraction*100)}pct"
            weights[key] = econ.scale_to_target((1-fraction)*core + fraction*extra, r)
            configs[key] = dict(overlay=name, fraction=fraction)
    return weights, configs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = econ.read_returns()
    candidates = ["MildWorstReturn_12m", "LowDownside_12m", "ShallowDrawdown_12m",
                  "LowTailLoss_12m", "LowVol_12m", "LowKurtosis_12m", "NegativeSkew_12m"]
    screen = pd.read_csv(OUT.parent / "factor_selection" / "train_factor_screen.csv").set_index("factor")
    candidates = [c for c in candidates if screen.loc[c,"mean"]>0 and screen.loc[c,"hac3_t"]>=1]
    weights, configs = construct(r, candidates)
    runs = {name: econ.backtest(w,r) for name,w in weights.items()}
    net = pd.DataFrame({name: x.net for name,x in runs.items()})
    validation = net.loc["1995-01-01":"2004-12-31"]
    rank = pd.DataFrame([dict(strategy=c,**configs[c],**evaluate(validation[c])) for c in net]).sort_values("sharpe_zero_rf",ascending=False)
    rank.to_csv(OUT / "validation_candidates.csv",index=False)
    winner = rank.iloc[0].strategy
    names = list(dict.fromkeys(["TSMOM","TSMOM_rescaled_control",winner,
                               "TSMOM_NegativeSkew_12m_20pct","TSMOM_EqualDefensiveBasket_20pct"]))
    rows, coverage = [], []
    for name in names:
        executed = weights[name].shift(1).fillna(0)
        missing = (executed.ne(0)&r.isna()).any(axis=1)
        coverage.append(pd.DataFrame({"strategy":name,"missing_held_return":missing},index=r.index))
        for period,start,end in [("full_1980_2014","1980-01-01",None),
                                  ("comparison_2005_2014","2005-01-01",None),
                                  ("2005_2009","2005-01-01","2009-12-31"),
                                  ("2010_2014","2010-01-01",None)]:
            b = runs[name].loc[start:end]
            rows.append(dict(strategy=name,period=period,**evaluate(b.net),
                mean_gross_exposure=b.leverage.mean(),annual_cost=b.tcost.mean()*12,
                missing_held_months=int(missing.loc[start:end].sum())))
        weights[name].to_csv(OUT / f"{name}_formation_weights.csv")
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "performance_summary.csv",index=False)
    pd.concat(coverage).to_csv(OUT / "missing_held_returns.csv")
    net[names].to_csv(OUT / "monthly_net_returns.csv")
    # Strict missing-held-return sensitivity for baseline and selected overlay.
    missing_masks = [(weights[n].shift(1).fillna(0).ne(0)&r.isna()).any(axis=1) for n in names]
    valid = ~pd.concat(missing_masks,axis=1).any(axis=1)
    strict = net.loc["2005-01-01":,names].loc[valid]
    pd.DataFrame([dict(strategy=n,**evaluate(strict[n])) for n in names]).to_csv(OUT/"strict_missing_return_sensitivity.csv",index=False)
    plot_names = list(dict.fromkeys(["TSMOM",winner,"TSMOM_NegativeSkew_12m_20pct"]))
    fig,axes = plt.subplots(1,2,figsize=(13,5),layout="constrained")
    labels={"TSMOM":"Original TSMOM",winner:"Validation-selected mix"}
    if winner!="TSMOM_NegativeSkew_12m_20pct":
        labels["TSMOM_NegativeSkew_12m_20pct"]="80/20 TSMOM + negative skew"
    colors=["#2476ad","#29944c","#cb8b27"]
    for ax,start,title in zip(axes,["1980-01-01","2005-01-01"],["1980–2014 (includes development)","2005–2014 (previously inspected)"]):
        for name,color in zip(plot_names,colors):
            ax.plot(np.log1p(net.loc[start:,name]).cumsum(),label=labels.get(name,name),color=color,lw=1.8)
        ax.set_title(title,fontsize=11);ax.set_ylabel("Log cumulative net return");ax.grid(alpha=.2)
        ax.spines[["top","right"]].set_visible(False)
    axes[0].legend(frameon=False,fontsize=9)
    fig.suptitle("Original price-trend TSMOM + new factor sleeves",fontsize=16)
    fig.supxlabel("Native economic_trend.py rules: 10% volatility target; 2 bps trading + quarterly rolls; monthly rebalance.\n"
                  "Native accounting fills missing held returns with zero; strict sensitivity is exported separately.",fontsize=9)
    fig.savefig(OUT/"tsmom_overlay_comparison.png",dpi=180)
    fig.savefig(OUT/"tsmom_overlay_comparison.pdf")
    (OUT/"selection.json").write_text(json.dumps(dict(selected=winner,configuration=configs[winner],
        candidates=candidates,selection="1995–2004 net Sharpe; original and rescaled-only controls included",
        methodology="economic_trend.py native baseline, sleeve scaling, blend scaling and backtest",
        warning="2005–2014 previously inspected; full period includes development; not a new holdout"),indent=2))
    print("SELECTED",winner)
    print(rank.head(5).to_string(index=False))
    print(summary.loc[summary.period.eq("comparison_2005_2014")].to_string(index=False))


if __name__=="__main__":
    main()
