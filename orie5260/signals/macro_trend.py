"""Five causally dated economic themes for the 20% macro sleeve."""
import numpy as np
import pandas as pd
from orie5260.common.data import DATA, asset_map
from orie5260.portfolio.engine import risk_normalize
from orie5260.portfolio.risk_model import normalize_sleeve

SIGNS = pd.DataFrame(
    {"EQ": [1, -1, 1, -1, 1], "FI": [-1, -1, -1, -1, -1],
     "FX": [1, 1, -1, 1, 1], "COMM": [1, 1, 1, -1, 1]},
    index=["growth", "inflation", "trade", "monetary", "risk_aversion"])
EQUITY_PROXY = ["SP", "ND", "RL", "ZD", "MD"]
RATE_FUTURES_IN_FX = {"EC"}
NON_US_USD_LISTED = {"NK", "XX"}


def fred(name):
    frame = pd.read_csv(DATA / f"{name}.csv")
    series = pd.to_numeric(frame.iloc[:, 1], errors="coerce")
    series.index = pd.to_datetime(frame.iloc[:, 0]).dt.to_period("M")
    return series.groupby(level=0).mean().dropna()


def themes(returns):
    periods = returns.index.to_period("M")
    output = pd.DataFrame(index=periods)
    indpro = fred("INDPRO"); indpro.index += 1
    cpi = fred("CPIAUCSL"); cpi.index += 1
    output["growth"] = np.sign(np.log(indpro).diff(12).diff(12)).reindex(periods)
    output["inflation"] = np.sign(np.log(cpi).diff(12).diff(12)).reindex(periods)
    output["monetary"] = np.sign(fred("GS2").diff(12)).reindex(periods)
    classes = asset_map().set_index("ID")["AssetClass"]
    r = returns.copy(); r.index = periods
    fx = [c for c in r if classes.get(c) == "FX" and c not in RATE_FUTURES_IN_FX]
    output["trade"] = np.sign(r[fx].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True))
    eq = [c for c in EQUITY_PROXY if c in r]
    risk = np.sign(r[eq].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True))
    credit = -np.sign(fred("BAA10Y").diff(12)).reindex(periods)
    both = pd.concat([risk, credit], axis=1)
    output["risk_aversion"] = np.sign(both.mean(axis=1, skipna=True)).where(both.notna().any(axis=1))
    output.index = returns.index
    return output[SIGNS.index]


def macro_sleeve(returns, classes, monthly_vol, covariance, eligible):
    mapped_classes = classes.copy()
    mapped_classes.loc[mapped_classes.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    amap = asset_map().set_index("ID")
    universe = [c for c in returns if c in amap.index and
                (amap.loc[c, "AssetClass"] in ("COMM", "FX") or
                 (amap.loc[c, "Ccy"] == "USD" and c not in NON_US_USD_LISTED))]
    signals = themes(returns).rolling(3, min_periods=1).mean()
    parts = []
    for theme in SIGNS.index:
        direction = pd.DataFrame(np.outer(signals[theme].fillna(0),
                [SIGNS.loc[theme, mapped_classes[c]] * (-1 if mapped_classes[c] == "FX" else 1)
                 for c in returns]), index=returns.index, columns=returns.columns)
        direction.loc[:, ~direction.columns.isin(universe)] = 0
        raw = direction.div(monthly_vol)
        valid = raw.notna() & direction.ne(0)
        raw = raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0)
        parts.append(normalize_sleeve(raw, eligible, covariance))
    return risk_normalize(sum(parts) / len(parts), covariance)
