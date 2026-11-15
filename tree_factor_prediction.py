"""Chronological random-forest forecast of next-month raw futures returns.

Run: MPLCONFIGDIR=/private/tmp/orie-mpl python3 tree_factor_prediction.py
No random row split, test tuning, backward fill or full-sample imputation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from futures_factor_backtest import build_signals, read_returns, read_asset_map, factor_weights, evaluate
from futures_factor_ic import monthly_ic, summarize

OUT = Path(__file__).resolve().parent / "outputs" / "tree_factor_prediction"


def panel_data(r):
    signals, vol = build_signals(r)
    classes = read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    index = pd.MultiIndex.from_product([r.index, r.columns], names=["formation_date", "instrument"])
    data = pd.DataFrame({name: value.to_numpy().ravel() for name, value in signals.items()}, index=index)
    data["eligible"] = vol.gt(0).to_numpy().ravel()
    data["target"] = r.shift(-1).to_numpy().ravel()
    next_dates = pd.Series(r.index[1:], index=r.index[:-1])
    data["return_date"] = data.index.get_level_values(0).map(next_dates)
    data["asset_class"] = data.index.get_level_values(1).map(classes)
    features = list(signals)
    # Static class metadata; no return-derived full-sample encoding.
    for c in sorted(classes.unique()):
        name = "class_" + str(c)
        data[name] = data.asset_class.eq(c).astype(float)
        features.append(name)
    data = data.loc[data.eligible & data.return_date.ge("1976-01-01") & data.return_date.notna()]
    return data, features, signals, vol, classes


def purge(earlier, later):
    boundary = later.index.get_level_values("formation_date").min()
    result = earlier.loc[earlier.return_date.lt(boundary)]
    assert result.return_date.max() < boundary
    return result


def metrics(y, pred):
    return {"observations": len(y), "mse": mean_squared_error(y, pred),
            "mae": mean_absolute_error(y, pred), "r2": r2_score(y, pred),
            "direction_accuracy": (np.mean(np.sign(y) == np.sign(pred))
                                   if np.any(np.asarray(pred) != 0) else np.nan)}


def forest(depth, leaf):
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                         RandomForestRegressor(n_estimators=200, max_depth=depth,
                                               min_samples_leaf=leaf, max_features=0.7,
                                               random_state=5260, n_jobs=2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    data, features, signals, vol, classes = panel_data(r)
    train = data.loc[data.return_date.lt("1995-01-01") & data.target.notna()]
    valid = data.loc[data.return_date.ge("1995-01-01") & data.return_date.lt("2005-01-01")]
    test = data.loc[data.return_date.ge("2005-01-01")]
    train = purge(train, valid)
    observed_valid = valid.loc[valid.target.notna()]
    selection = []
    for depth, leaf in [(3, 100), (6, 100), (6, 30)]:
        model = forest(depth, leaf)
        model.fit(train[features], train.target)
        pred = model.predict(observed_valid[features])
        selection.append(dict(depth=depth, leaf=leaf, **metrics(observed_valid.target, pred)))
    selection = pd.DataFrame(selection)
    selection.to_csv(OUT / "validation_selection.csv", index=False)
    best = selection.sort_values("mse").iloc[0]
    # Refit selected settings on the development period, purged at test boundary.
    development = purge(data.loc[data.return_date.lt("2005-01-01") & data.target.notna()], test)
    models = {"RandomForest": forest(int(best.depth), int(best.leaf)),
              "Ridge": make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                                     StandardScaler(), Ridge(alpha=100.0))}
    predictions = test[["return_date", "target", "asset_class"]].copy()
    for name, model in models.items():
        model.fit(development[features], development.target)
        predictions[name] = model.predict(test[features])
    predictions["Zero"] = 0.0
    predictions["HistoricalMean"] = development.target.mean()
    predictions.to_csv(OUT / "test_predictions.csv")
    pd.Series(models["RandomForest"][-1].feature_importances_, index=features,
              name="impurity_importance").sort_values(ascending=False).to_csv(OUT / "feature_importance.csv")
    observed = predictions.loc[predictions.target.notna()]
    result = []
    for name in [*models, "Zero", "HistoricalMean"]:
        for period, sample in [("test_full", observed),
                               ("2005_2009", observed.loc[observed.return_date.lt("2010-01-01")]),
                               ("2010_onward", observed.loc[observed.return_date.ge("2010-01-01")])]:
            result.append(dict(model=name, period=period, **metrics(sample.target, sample[name])))
    pd.DataFrame(result).to_csv(OUT / "test_prediction_metrics.csv", index=False)
    ic_rows, monthly_rows, portfolio = [], [], {}
    forward = r.shift(-1)
    for name in ["RandomForest", "Ridge", "XSMOM"]:
        if name == "XSMOM":
            score = signals["XSMOM_12_1"].where(vol.gt(0))
            test_dates = test.index.get_level_values(0).unique()
            score.loc[~score.index.isin(test_dates)] = np.nan
        else:
            score = predictions[name].unstack("instrument").reindex(index=r.index, columns=r.columns)
        pooled = monthly_ic(score, forward)
        panels = [monthly_ic(score[m.index], forward[m.index]) for _, m in classes.groupby(classes)]
        within = pd.DataFrame(index=r.index)
        for metric in ("IC", "RankIC"):
            p = pd.concat([x[metric] for x in panels], axis=1)
            within[metric] = p.mean(axis=1).where(p.notna().sum(axis=1).ge(2))
        for scope, frame in [("all_markets", pooled), ("within_class_equal", within)]:
            frame = frame.reindex(test.index.get_level_values(0).unique())
            monthly_rows.append(frame.assign(model=name, scope=scope).rename_axis("formation_date").reset_index())
            for metric in ("IC", "RankIC"):
                ic_rows.append(dict(model=name, scope=scope, metric=metric, **summarize(frame[metric])))
        formed = factor_weights(score, vol, classes)
        executed = formed.shift(1).fillna(0)
        missing = (executed.ne(0) & r.isna()).any(axis=1)
        gross = (executed * r).sum(axis=1)
        prior = executed.shift(1).fillna(0)
        prev_returns = r.shift(1)
        prev_pnl = (prior * prev_returns).sum(axis=1)
        drifted = (prior * (1 + prev_returns.fillna(0))).div(1 + prev_pnl, axis=0)
        turnover = (executed - drifted).abs().sum(axis=1)
        usable = executed.abs().sum(axis=1).gt(0) & ~missing
        usable &= ~(prior.ne(0) & prev_returns.isna()).any(axis=1)
        portfolio[name + "_gross"] = gross.where(usable)
        portfolio[name + "_net10bps"] = (gross - turnover * .001).where(usable)
        executed.loc["2005-01-01":].to_csv(OUT / (name + "_executed_weights.csv"))
    pd.DataFrame(ic_rows).to_csv(OUT / "test_ic_summary.csv", index=False)
    pd.concat(monthly_rows, ignore_index=True).to_csv(OUT / "test_ic_monthly.csv", index=False)
    port = pd.DataFrame(portfolio).loc["2005-01-01":]
    port.to_csv(OUT / "test_portfolio_returns.csv")
    common = port.notna().all(axis=1)
    stats = pd.DataFrame([dict(strategy=c, **evaluate(port.loc[common, c])) for c in port])
    stats.to_csv(OUT / "test_portfolio_summary.csv", index=False)
    audit = []
    for name, frame in [("selection_train", train), ("validation", valid),
                        ("final_development", development), ("test", test)]:
        audit.append(dict(split=name, rows=len(frame), labeled_rows=int(frame.target.notna().sum()),
                          formation_start=str(frame.index.get_level_values(0).min().date()),
                          formation_end=str(frame.index.get_level_values(0).max().date()),
                          return_start=str(frame.return_date.min().date()), return_end=str(frame.return_date.max().date())))
    pd.DataFrame(audit).to_csv(OUT / "split_audit.csv", index=False)
    (OUT / "model_config.json").write_text(json.dumps(dict(selected_depth=int(best.depth), selected_leaf=int(best.leaf),
          selection_metric="validation MSE", features=features, seed=5260, trees=200,
          retraining="once before test; fixed during test", boundary="earlier label date strictly before later formation date"), indent=2))
    print(pd.DataFrame(audit).to_string(index=False))
    print(pd.DataFrame(result).query("period == 'test_full'").to_string(index=False))
    print(pd.DataFrame(ic_rows).query("scope == 'within_class_equal'").to_string(index=False))
    print(stats.to_string(index=False))


if __name__ == "__main__":
    main()
