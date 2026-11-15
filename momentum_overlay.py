"""Keep raw XSMOM core; select a defensive overlay before 2005."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from futures_factor_backtest import read_returns, read_asset_map, build_signals, factor_weights, evaluate

OUT = Path(__file__).resolve().parent / "outputs" / "momentum_overlay"


def combined_weights(core, extra, fraction):
    w = (1 - fraction) * core + fraction * extra
    # Equal gross exposure after offsetting opposing signals. Do not scale a
    # partial-universe portfolio above one dollar total gross.
    return w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0)


def backtest(w, r):
    executed = w.shift(1).fillna(0)
    prior = executed.shift(1).fillna(0)
    prev = r.shift(1)
    drifted = (prior * (1 + prev.fillna(0))).div(1 + (prior * prev).sum(axis=1), axis=0)
    traded = (executed - drifted).abs().sum(axis=1)
    valid = executed.abs().sum(axis=1).gt(0)
    valid &= ~(executed.ne(0) & r.isna()).any(axis=1)
    valid &= ~(prior.ne(0) & prev.isna()).any(axis=1)
    gross = (executed * r).sum(axis=1)
    return pd.DataFrame({"gross": gross.where(valid), "net": (gross - .001 * traded).where(valid),
                         "turnover": traded.where(valid), "gross_exposure": executed.abs().sum(axis=1)})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    signals, vol = build_signals(r)
    classes = read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    core = factor_weights(signals["XSMOM_12_1"], vol, classes)
    # Predefined non-trend families; train-only gate comes from prior screening.
    candidates = ["MildWorstReturn_12m", "LowDownside_12m", "ShallowDrawdown_12m",
                  "LowTailLoss_12m", "LowVol_12m", "LowKurtosis_12m", "NegativeSkew_12m"]
    screen_path = OUT.parent / "factor_selection" / "train_factor_screen.csv"
    if not screen_path.exists():
        raise FileNotFoundError("Run select_factor_subset.py first for training-only screening.")
    screen = pd.read_csv(screen_path).set_index("factor")
    candidates = [c for c in candidates if screen.loc[c, "mean"] > 0 and screen.loc[c, "hac3_t"] >= 1]
    if not candidates:
        raise ValueError("No overlay passed the training-only gate")
    extras = {name: factor_weights(signals[name], vol, classes) for name in candidates}
    extras["EqualDefensiveBasket"] = sum(extras.values()) / len(extras)
    weights = {"Mom": core}
    configs = {"Mom": {"overlay": "none", "fraction": 0}}
    for name, extra in extras.items():
        for fraction in (.1, .2, .3, .4):
            key = f"Mom_{name}_{int(fraction*100)}pct"
            weights[key] = combined_weights(core, extra, fraction)
            configs[key] = dict(overlay=name, fraction=fraction)
    runs = {name: backtest(w, r) for name, w in weights.items()}
    # One validation calendar intersection for every candidate; no later returns
    # enter the sample mask or selection criterion.
    net = pd.DataFrame({name: frame.net for name, frame in runs.items()})
    validation = net.loc["1995-01-01":"2004-12-31"].dropna()
    rows = [dict(strategy=name, **configs[name], **evaluate(validation[name])) for name in net]
    ranking = pd.DataFrame(rows).sort_values("sharpe_zero_rf", ascending=False)
    ranking.to_csv(OUT / "validation_candidates.csv", index=False)
    winner = ranking.iloc[0].strategy
    # Prespecified equal-basket 20% mix is exported alongside the selected mix.
    names = list(dict.fromkeys(["Mom", winner, "Mom_EqualDefensiveBasket_20pct"]))
    test = net.loc["2005-01-01":, names].dropna()
    results = []
    for name in names:
        sample = runs[name].reindex(test.index)
        results.append(dict(strategy=name, **configs[name], **evaluate(sample.net),
                            annual_turnover=sample.turnover.mean()*12,
                            gross_sharpe=evaluate(sample.gross)["sharpe_zero_rf"],
                            mean_gross_exposure=sample.gross_exposure.mean()))
        weights[name].loc["2004-12-01":].to_csv(OUT / f"{name}_formation_weights.csv")
    test.to_csv(OUT / "comparison_net_returns.csv")
    pd.DataFrame(results).to_csv(OUT / "comparison_summary.csv", index=False)
    subperiods = []
    for period, sample in [("2005_2009", test.loc[:"2009-12-31"]),
                           ("2010_2014", test.loc["2010-01-01":])]:
        for name in sample:
            subperiods.append(dict(period=period, strategy=name, **evaluate(sample[name])))
    pd.DataFrame(subperiods).to_csv(OUT / "comparison_subperiods.csv", index=False)
    # Save all candidates for audit, explicitly not for further test selection.
    net.to_csv(OUT / "all_candidate_net_returns_audit.csv")
    (OUT / "selection.json").write_text(json.dumps(dict(candidates=candidates, selected=winner,
        config=configs[winner], validation_months=len(validation), comparison_months=len(test),
        objective="validation net Sharpe including Mom-only option", costs_bps=10,
        weights="blend then normalize to unit gross; fraction is before netting",
        warning="2005-2014 previously inspected; not a pristine holdout"), indent=2))
    print("SELECTED", winner)
    print(ranking.head(5).to_string(index=False))
    print(pd.DataFrame(results).to_string(index=False))


if __name__ == "__main__":
    main()
