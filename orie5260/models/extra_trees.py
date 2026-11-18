"""Frozen 66-feature Extra Trees forecasts for the final 30% sleeve.

Feature definitions and two chronological fits reproduce the Existing66 model.
Labels must be observed before each fit's first formation date.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

from orie5260.portfolio.risk_model import normalize_sleeve
from orie5260.factors.features import price_features, peer_features






def forecasts(returns, classes, monthly_vol):
    """Predict at month-end; initial fit before 2005 and one refit before 2015."""
    next_month = (returns.index[-1].to_period("M") + 1).to_timestamp("M")
    padded = pd.concat([returns, pd.DataFrame(np.nan, index=[next_month], columns=returns.columns)])
    signals = {**price_features(padded), **peer_features(padded, classes)}
    index = pd.MultiIndex.from_product([padded.index, padded.columns], names=["formation_date", "instrument"])
    panel = pd.DataFrame({name: frame.to_numpy().ravel() for name, frame in signals.items()}, index=index)
    panel["asset_class"] = index.get_level_values(1).map(classes)
    panel["target"] = padded.shift(-1).to_numpy().ravel()
    next_dates = pd.Series(padded.index[1:], index=padded.index[:-1])
    panel["return_date"] = index.get_level_values(0).map(next_dates)
    vol = padded.rolling(12, min_periods=12).std().clip(lower=.01)
    eligible = vol.gt(0).to_numpy().ravel()
    panel = panel.loc[eligible & panel.return_date.ge("1969-01-01") & panel.return_date.notna()].copy()
    features = panel[list(signals)].copy()
    ranks = features.groupby([pd.Grouper(level="formation_date"), panel.asset_class]).rank(pct=True) - .5
    features = features.join(ranks.add_prefix("rank_"))
    for c in sorted(classes.unique()):
        features["class_"+c] = panel.asset_class.eq(c).astype(float)
    if features.shape[1] != 66:
        raise AssertionError(f"Expected 66 ML features; got {features.shape[1]}")
    labels = panel.target.gt(0).astype(float).where(panel.target.notna() & panel.target.ne(0))
    formation = panel.index.get_level_values("formation_date")
    probabilities = pd.Series(np.nan, index=panel.index)
    audit = []
    for phase, cutoff, end in [("development", "2004-12-31", "2014-12-31"),
                                ("later", "2014-12-31", None)]:
        boundary = pd.Timestamp(cutoff)
        inference = formation >= boundary
        if end: inference &= formation < pd.Timestamp(end)
        known = panel.return_date.lt(boundary) & labels.notna()
        if not inference.any(): continue
        model = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            ExtraTreesClassifier(n_estimators=200, max_depth=6, min_samples_leaf=30,
                                 max_features=.7, random_state=5260, n_jobs=2))
        model.fit(features.loc[known], labels.loc[known].astype(int))
        probabilities.loc[inference] = model.predict_proba(features.loc[inference])[:, 1]
        audit.append({"phase": phase, "last_training_label": str(panel.loc[known, "return_date"].max().date()),
                      "first_formation": str(formation[inference].min().date()), "training_rows": int(known.sum())})
    return probabilities.unstack("instrument").reindex(index=returns.index, columns=returns.columns), pd.DataFrame(audit)


def extra_trees_sleeve(returns, classes, monthly_vol, covariance, eligible):
    probs, audit = forecasts(returns, classes, monthly_vol)
    direction = 2 * probs - 1
    raw = direction.div(monthly_vol)
    valid = raw.notna() & direction.ne(0)
    raw = raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0)
    return normalize_sleeve(raw, eligible, covariance), audit
