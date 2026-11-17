"""Frozen 66-feature Extra Trees forecasts for the final 30% sleeve.

Feature definitions and two chronological fits reproduce the Existing66 model.
Labels must be observed before each fit's first formation date.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

from risk_model import normalize_sleeve


def price_features(r):
    vol = r.expanding(min_periods=36).std() * np.sqrt(12)
    sd = r.rolling(12, min_periods=12).std().replace(0, np.nan)
    log = np.log1p(r.where(r > -1))
    roll = r.rolling(12, min_periods=12)
    positive = r.gt(0).astype(float).where(r.notna())

    def path_stat(x, kind):
        path = np.r_[0.0, np.cumsum(x)]
        if kind == "high": return path[-1] - path.max()
        if kind == "drawdown": return np.min(path - np.maximum.accumulate(path))
        return path[-1] / np.abs(x).sum() if np.abs(x).sum() else np.nan

    def persistence(x):
        if np.std(x[:-1]) == 0 or np.std(x[1:]) == 0: return np.nan
        return np.corrcoef(x[:-1], x[1:])[0, 1]

    signals = {
        "TSMOM": np.sign(roll.sum()),
        "Reversal_1m": -r / vol,
        "LowVol_12m": -roll.std(),
        "LowDownside_12m": -r.clip(upper=0).pow(2).rolling(12, min_periods=12).mean().pow(.5),
        "XSMOM_12_1": r.shift(1).rolling(11, min_periods=11).sum() / vol,
        "Reversal_3m": -r.rolling(3, min_periods=3).sum() / sd,
        "LongReversal_36_12": -r.shift(12).rolling(24, min_periods=24).sum() / sd,
        "NegativeSkew_12m": -roll.skew(),
        "LowKurtosis_12m": -roll.kurt(),
        "LowMaxReturn_12m": -roll.max(),
        "MildWorstReturn_12m": roll.min(),
        "LowTailLoss_12m": roll.quantile(.1),
        "LowUpsideRisk_12m": -r.clip(lower=0).pow(2).rolling(12, min_periods=12).mean().pow(.5),
        "RiskAsymmetry_12m": (r.clip(lower=0).pow(2).rolling(12, min_periods=12).mean() -
                                r.clip(upper=0).pow(2).rolling(12, min_periods=12).mean()) / sd.pow(2),
        "VolCompression_3_12": -r.rolling(3, min_periods=3).std() / sd,
        "LowVolOfVol_12m": -sd.rolling(12, min_periods=12).std() / sd.rolling(12, min_periods=12).mean(),
        "ReturnPersistence_12m": roll.apply(persistence, raw=True),
        "Seasonality_5y": sum(r.shift(lag) for lag in (11, 23, 35, 47, 59)) / 5,
        "TrendEfficiency_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "efficiency"), raw=True),
        "TrendAcceleration_3m": (r.rolling(3, min_periods=3).sum() -
                                    r.shift(3).rolling(3, min_periods=3).sum()) / sd,
        "MeanToVol_12m": roll.mean() / sd,
        "NearWealthHigh_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "high"), raw=True),
        "ShallowDrawdown_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "drawdown"), raw=True),
        "PositiveMonthShare_12m": positive.rolling(12, min_periods=12).mean(),
        "MedianReturn_12m": roll.median() / sd,
    }
    return {name: value.replace([np.inf, -np.inf], np.nan) for name, value in signals.items()}


def peer_features(r, classes):
    names = ["LowPeerBeta_36m", "LowPeerCorrelation_36m", "LowResidualVol_12m",
             "ResidualMomentum_12m", "PeerRelativeReversal_1m", "PeerRelativeMomentum_12m"]
    output = {name: pd.DataFrame(np.nan, index=r.index, columns=r.columns) for name in names}
    for _, members in classes.groupby(classes):
        block = r[members.index]
        count = block.notna().sum(axis=1)
        for col in block:
            own = block[col]
            n = count - own.notna().astype(int)
            peer = (block.sum(axis=1, min_count=1) - own.fillna(0)).div(n.replace(0, np.nan)).where(n.ge(3))
            peer = peer.where(own.notna())
            beta = own.rolling(36, min_periods=24).cov(peer).div(peer.rolling(36, min_periods=24).var().replace(0, np.nan))
            residual = own - beta * peer
            residual_vol = residual.rolling(12, min_periods=12).std().replace(0, np.nan)
            relative = own - peer
            output[names[0]][col] = -beta
            output[names[1]][col] = -own.rolling(36, min_periods=24).corr(peer)
            output[names[2]][col] = -residual_vol
            output[names[3]][col] = residual.rolling(12, min_periods=12).sum() / residual_vol
            output[names[4]][col] = -relative
            output[names[5]][col] = relative.shift(1).rolling(11, min_periods=11).sum() / own.rolling(12, min_periods=12).std().replace(0, np.nan)
    return {name: value.replace([np.inf, -np.inf], np.nan) for name, value in output.items()}


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
