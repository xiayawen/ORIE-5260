"""Train-only factor screening and fixed-specification tree ablation.

2005 onward is a previously inspected comparison period, not a new holdout.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from tree_factor_prediction import panel_data, purge, forest, read_returns
from futures_factor_ic import monthly_ic, summarize
from futures_factor_backtest import factor_weights, evaluate

OUT = Path(__file__).resolve().parent / "outputs" / "factor_selection"


def class_ic(panel, scores):
    tmp = panel[["target", "asset_class"]].copy()
    tmp["score"] = scores
    rows = []
    for (date, cls), group in tmp.groupby([pd.Grouper(level="formation_date"), "asset_class"]):
        pair = group[["target", "score"]].dropna()
        value = pair.target.rank().corr(pair.score.rank()) if len(pair) >= 4 and pair.score.nunique() > 1 and pair.target.nunique() > 1 else np.nan
        rows.append((date, cls, value))
    frame = pd.DataFrame(rows, columns=["date", "class", "ic"]).pivot(index="date", columns="class", values="ic")
    return frame.mean(axis=1).where(frame.notna().sum(axis=1).ge(2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    data, all_features, signals, vol, classes = panel_data(r)
    valid = data.loc[data.return_date.ge("1995-01-01") & data.return_date.lt("2005-01-01")]
    comparison = data.loc[data.return_date.ge("2005-01-01")]
    train = purge(data.loc[data.return_date.lt("1995-01-01") & data.target.notna()], valid)
    dev = purge(data.loc[data.return_date.lt("2005-01-01") & data.target.notna()], comparison)
    rows = []
    for name in signals:
        ic = class_ic(train, train[name])
        rows.append(dict(factor=name, **summarize(ic)))
    screen = pd.DataFrame(rows).sort_values("mean", ascending=False)
    # Training-date/class ranks compare redundancy on contemporaneous information.
    rank = train[list(signals)].groupby([pd.Grouper(level="formation_date"), train.asset_class]).rank(pct=True)
    rank = rank - rank.groupby([pd.Grouper(level="formation_date"), train.asset_class]).transform("mean")
    corr = rank.corr(min_periods=500)
    selected, reasons = [], {}
    for row in screen.itertuples():
        if row.mean <= 0 or row.hac3_t < 1:
            reasons[row.factor] = "weak train IC (mean<=0 or HAC t<1)"
        elif selected and corr.loc[row.factor, selected].abs().max() >= .8:
            reasons[row.factor] = "redundant (absolute train rank correlation>=0.8)"
        elif len(selected) >= 6:
            reasons[row.factor] = "six-feature limit"
        else:
            selected.append(row.factor)
            reasons[row.factor] = "selected"
    screen["decision"] = screen.factor.map(reasons)
    screen.to_csv(OUT / "train_factor_screen.csv", index=False)
    corr.to_csv(OUT / "train_feature_rank_correlations.csv")
    context = [x for x in all_features if x.startswith("class_")]
    sets = {"MomOnly": ["XSMOM_12_1"] + context,
            "Selected": selected + context, "AllFactors": all_features}
    results, predictions, val_scores = [], [], []
    # Same forest for every feature set isolates feature selection. No new grid.
    for name, features in sets.items():
        model = forest(6, 30)
        model.fit(train[features], train.target)
        val_pred = model.predict(valid[features])
        ic = class_ic(valid, val_pred)
        val_scores.append(dict(model=name, **summarize(ic)))
    winner = max(val_scores, key=lambda x: x["mean"])["model"]
    portfolio = {}
    for name, features in sets.items():
        model = forest(6, 30)
        model.fit(dev[features], dev.target)
        pred = model.predict(comparison[features])
        pred_series = pd.Series(pred, index=comparison.index)
        ic = class_ic(comparison, pred)
        results.append(dict(model=name, **summarize(ic)))
        predictions.append(comparison[["target", "return_date"]].assign(model=name, prediction=pred))
        score = pred_series.unstack("instrument").reindex(index=r.index, columns=r.columns)
        executed = factor_weights(score, vol, classes).shift(1).fillna(0)
        prior = executed.shift(1).fillna(0)
        prev = r.shift(1)
        drifted = (prior * (1 + prev.fillna(0))).div(1 + (prior * prev).sum(axis=1), axis=0)
        turnover = (executed - drifted).abs().sum(axis=1)
        missing = (executed.ne(0) & r.isna()).any(axis=1) | (prior.ne(0) & prev.isna()).any(axis=1)
        pnl = (executed * r).sum(axis=1)
        valid_month = executed.abs().sum(axis=1).gt(0) & ~missing
        portfolio[name + "_gross"] = pnl.where(valid_month)
        portfolio[name + "_net"] = (pnl - .001 * turnover).where(valid_month)
    port = pd.DataFrame(portfolio).loc["2005-01-01":]
    common = port.notna().all(axis=1)
    perf = pd.DataFrame([dict(strategy=c, **evaluate(port.loc[common, c])) for c in port])
    pd.DataFrame(val_scores).to_csv(OUT / "validation_rank_ic.csv", index=False)
    pd.DataFrame(results).to_csv(OUT / "comparison_rank_ic.csv", index=False)
    pd.concat(predictions).to_csv(OUT / "comparison_predictions.csv")
    port.to_csv(OUT / "comparison_portfolio_returns.csv")
    perf.to_csv(OUT / "comparison_portfolio_summary.csv", index=False)
    (OUT / "selection_config.json").write_text(json.dumps(dict(selected=selected, feature_sets=sets,
        validation_winner=winner, rule="positive mean, HAC3 t>=1, abs rank corr<0.8, max six; train only",
        model="RF depth6 leaf30 trees200 seed5260; unchanged across sets",
        warning="2005 onward previously inspected; development comparison only"), indent=2))
    print("SELECTED", selected, "VALIDATION WINNER", winner)
    print(pd.DataFrame(val_scores).to_string(index=False))
    print(pd.DataFrame(results).to_string(index=False))
    print(perf.to_string(index=False))


if __name__ == "__main__":
    main()
