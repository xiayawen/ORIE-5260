from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_backtest_adj import ROOT, read_asset_map, read_returns

TARGET_VOL = 0.10
VOL_WINDOW = 12
SCALE_WINDOW = 36
TCOST_BPS = 2.0
ROLLS_PER_YEAR = 4
EVAL_START = "1980-01-01"     # all five themes available (GS2 starts mid-1976)
IS_END = "2014-12-31"
OUT = ROOT / "outputs" / "economic_trend_output"

SIGNS = pd.DataFrame(
    {"EQ": [1, -1, 1, -1, 1], "FI": [-1, -1, -1, -1, -1],
     "FX": [1, 1, -1, 1, 1], "COMM": [1, 1, 1, -1, 1]},
    index=["growth", "inflation", "trade", "monetary", "risk_aversion"],
)
FX_HOME_FLIP = -1            # FX futures are foreign currency vs USD
# Trade/COMM is +1 (slide shows -1): our commodities are USD-priced, and a weaker
# USD (our trade signal) historically lifts USD commodity prices.
SIGNAL_MODE = "sign"         # "sign" = +/-1 (v2); "zscore" = change / trailing std, capped
Z_CAP = 2.0                  # fixed a priori, not tuned
Z_MIN_HIST = 36              # months of history before a z-score is used
SMOOTH_MONTHS = 3            # average the last k monthly theme signals (1 = none; 3 picked on 1980-1997)
CLASS_BALANCE = False        # True: each asset class gets an equal share of a theme's risk
US_ONLY = True               # macro is US data -> only trade assets the US economy drives
NON_US_USD_LISTED = {"NK", "XX"}   # USD-listed contracts on foreign indices (Nikkei, etc.)
RATE_FUTURES_IN_FX = {"EC"}        # Eurodollar is a US rate future, treat as FI
EQUITY_PROXY = ["SP", "ND", "RL", "ZD", "MD"]   # US equity index futures available early


# ---------------------------------------------------------------- data


def read_fred(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0]).dt.to_period("M")
    return s.groupby(level=0).mean().dropna()   # daily -> monthly average when needed


def lag_one_month(s: pd.Series) -> pd.Series:
    """Value for month m becomes usable at the end of month m+1."""
    out = s.copy()
    out.index = out.index + 1
    return out


def month_end_index(returns: pd.DataFrame) -> pd.PeriodIndex:
    return returns.index.to_period("M")


def to_signal(x: pd.Series) -> pd.Series:
    """Turn a raw 12-month change into a position signal using only past data.

    sign  : +1 / -1
    zscore: x_t / std(x_1..x_t) (expanding, at least Z_MIN_HIST obs), clipped to +/-Z_CAP,
            divided by Z_CAP so the signal lies in [-1, 1]. No mean is removed, so the
            sign of the signal is the same as in the +/-1 version, only its size changes.
    """
    if SIGNAL_MODE == "sign":
        return np.sign(x)
    scale = x.expanding(min_periods=Z_MIN_HIST).std()
    return (x / scale).clip(-Z_CAP, Z_CAP) / Z_CAP


def macro_signals(returns: pd.DataFrame, macro_dir: Path) -> pd.DataFrame:
    """+1 / -1 / NaN per theme, indexed like `returns`, using only data known at each month-end."""
    periods = month_end_index(returns)
    out = pd.DataFrame(index=periods)

    indpro = lag_one_month(read_fred(macro_dir / "INDPRO.csv"))      # publication lag
    growth_yoy = np.log(indpro).diff(12)
    out["growth"] = to_signal(growth_yoy.diff(12)).reindex(periods)

    cpi = lag_one_month(read_fred(macro_dir / "CPIAUCSL.csv"))       # publication lag
    infl_yoy = np.log(cpi).diff(12)
    out["inflation"] = to_signal(infl_yoy.diff(12)).reindex(periods)

    gs2 = read_fred(macro_dir / "GS2.csv")
    out["monetary"] = to_signal(gs2.diff(12)).reindex(periods)

    asset_class = read_asset_map().set_index("ID")["AssetClass"]
    fx = [c for c in returns.columns if asset_class.get(c) == "FX" and c != "EC"]  # EC is a rate future
    r = returns.copy()
    r.index = periods
    fx_12m = r[fx].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True)
    out["trade"] = to_signal(fx_12m)                 # foreign FX up = USD depreciation

    eq = [c for c in EQUITY_PROXY if c in r.columns]
    eq_12m = r[eq].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True)
    risk = to_signal(eq_12m)
    baa = macro_dir / "BAA10Y.csv"
    if baa.exists():
        spread = read_fred(baa)
        credit = -to_signal(spread.diff(12)).reindex(periods)            # narrowing = risk-on
        both = pd.concat([risk, credit], axis=1)
        combined = both.mean(axis=1, skipna=True)
        risk = (np.sign(combined) if SIGNAL_MODE == "sign" else combined).where(both.notna().any(axis=1))
    out["risk_aversion"] = risk

    out.index = returns.index
    return out[SIGNS.index]


# ---------------------------------------------------------------- portfolios


def instrument_vol(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * np.sqrt(12)


def risk_weights(direction: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """direction x 1/vol / N over instruments with a valid vol and direction."""
    raw = direction / vol
    valid = raw.notna() & (direction != 0)
    n = valid.sum(axis=1).replace(0, np.nan)
    return raw.where(valid).div(n, axis=0).fillna(0.0)


def class_balanced_weights(direction: pd.DataFrame, vol: pd.DataFrame, asset_class: pd.Series) -> pd.DataFrame:
    """direction x 1/vol / N_class / N_active_classes: every active asset class gets the same budget,
    so a class with many contracts (e.g. bonds, all -1 in the sign table) cannot dominate a theme."""
    raw = direction / vol
    valid = raw.notna() & (direction != 0)
    cls = asset_class.reindex(direction.columns)
    out = pd.DataFrame(0.0, index=direction.index, columns=direction.columns)
    n_classes = pd.Series(0, index=direction.index)
    for c in cls.unique():
        cols = cls[cls == c].index
        n_c = valid[cols].sum(axis=1)
        out[cols] = raw[cols].where(valid[cols]).div(n_c.replace(0, np.nan), axis=0).fillna(0.0)
        n_classes += (n_c > 0).astype(int)
    return out.div(n_classes.replace(0, np.nan), axis=0).fillna(0.0)


def theme_direction(theme_signal: pd.Series, theme: str, columns, asset_class: pd.Series) -> pd.DataFrame:
    sign_by_col = pd.Series({c: SIGNS.loc[theme, asset_class[c]] * (FX_HOME_FLIP if asset_class[c] == "FX" else 1)
                             for c in columns})
    return pd.DataFrame(np.outer(theme_signal.fillna(0), sign_by_col), index=theme_signal.index, columns=columns)


def scale_to_target(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Scale formation weights so trailing realized vol of the unscaled strategy hits TARGET_VOL."""
    unscaled = (weights.shift(1) * returns.fillna(0)).sum(axis=1)
    realized = unscaled.rolling(SCALE_WINDOW, min_periods=24).std() * np.sqrt(12)   # known at t
    scale = (TARGET_VOL / realized).replace([np.inf, -np.inf], np.nan)
    return weights.mul(scale, axis=0).fillna(0.0)


def backtest(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    executed = weights.shift(1).fillna(0.0)
    gross = (executed * returns.fillna(0)).sum(axis=1)
    turnover = executed.diff().fillna(executed).abs().sum(axis=1)
    trade_cost = turnover * TCOST_BPS / 1e4
    roll_cost = executed.abs().sum(axis=1) * ROLLS_PER_YEAR / 12 * TCOST_BPS / 1e4
    return pd.DataFrame({"gross": gross, "net": gross - trade_cost - roll_cost, "turnover": turnover,
                         "tcost": trade_cost + roll_cost, "leverage": executed.abs().sum(axis=1),
                         "imbalance": executed.sum(axis=1), "names": (executed != 0).sum(axis=1)})


def stats(bt: pd.DataFrame, start=EVAL_START, end=IS_END) -> dict:
    b = bt.loc[start:end]
    r = b.net
    return {"avg_net_ret": r.mean() * 12, "std": r.std() * np.sqrt(12),
            "sharpe": r.mean() / r.std() * np.sqrt(12),
            "max_dd": ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min(),
            "turnover": b.turnover.mean() * 12, "tcost": b.tcost.mean() * 12,
            "leverage": b.leverage.mean(), "imbalance": b.imbalance.mean(), "names": b.names.mean()}


def macro_universe(columns) -> pd.Index:
    """US-relevant instruments: commodities, USD FX pairs, US equity indices and US rates."""
    amap = read_asset_map().set_index("ID")
    keep = [c for c in columns if c in amap.index and (
        amap.loc[c, "AssetClass"] in ("COMM", "FX")
        or (amap.loc[c, "Ccy"] == "USD" and c not in NON_US_USD_LISTED))]
    return pd.Index(keep)


BLEND_WEIGHTS = (0.1, 0.2, 0.25, 0.3, 0.4, 0.5)


def build(returns: pd.DataFrame, macro_dir: Path):
    asset_class = read_asset_map().set_index("ID")["AssetClass"].reindex(returns.columns).fillna("COMM")
    asset_class[asset_class.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    universe = macro_universe(returns.columns) if US_ONLY else returns.columns
    vol = instrument_vol(returns)
    signals = macro_signals(returns, macro_dir)
    if SMOOTH_MONTHS > 1:   # trailing mean of past signals only
        signals = signals.rolling(SMOOTH_MONTHS, min_periods=1).mean()

    strategies = {}
    price_dir = np.sign(returns.rolling(12, min_periods=12).sum())
    strategies["price_trend"] = scale_to_target(risk_weights(price_dir, vol), returns)
    theme_weights = {}
    for theme in SIGNS.index:
        d = theme_direction(signals[theme], theme, returns.columns, asset_class)
        d.loc[:, ~d.columns.isin(universe)] = 0.0
        w = class_balanced_weights(d, vol, asset_class) if CLASS_BALANCE else risk_weights(d, vol)
        theme_weights[theme] = scale_to_target(w, returns)
        strategies[f"theme_{theme}"] = theme_weights[theme]
    econ = sum(theme_weights.values()) / len(theme_weights)
    strategies["economic_trend"] = scale_to_target(econ, returns)
    for w in BLEND_WEIGHTS:
        mix = (1 - w) * strategies["price_trend"] + w * strategies["economic_trend"]
        strategies[f"blend_{int(round(w*100))}"] = scale_to_target(mix, returns)
    return strategies, signals


def main() -> None:
    global US_ONLY, SIGNAL_MODE
    parser = argparse.ArgumentParser()
    parser.add_argument("--macro-dir", default=str(ROOT / "macro_data"))
    parser.add_argument("--all-assets", action="store_true", help="apply US macro to every market (v1)")
    parser.add_argument("--signal", choices=["sign", "zscore"], default=SIGNAL_MODE)
    args = parser.parse_args()
    US_ONLY = not args.all_assets
    SIGNAL_MODE = args.signal
    OUT.mkdir(parents=True, exist_ok=True)

    returns = read_returns()
    strategies, signals = build(returns, Path(args.macro_dir))
    results = {name: backtest(w, returns) for name, w in strategies.items()}

    table = pd.DataFrame({name: stats(bt) for name, bt in results.items()}).T
    net = pd.DataFrame({name: bt.net for name, bt in results.items()}).loc[EVAL_START:IS_END]
    table["corr_price_trend"] = net.corr()["price_trend"]
    table.to_csv(OUT / "summary_in_sample.csv")
    net.corr().to_csv(OUT / "correlations_in_sample.csv")
    signals.to_csv(OUT / "theme_signals.csv")
    pd.DataFrame({n: bt.net for n, bt in results.items()}).to_csv(OUT / "monthly_net_returns.csv")
    decades = net.groupby((net.index.year // 10) * 10).apply(lambda x: x.mean() / x.std() * np.sqrt(12))
    decades.to_csv(OUT / "sharpe_by_decade.csv")

    print(table.round(3).to_string())
    print("\nSharpe by decade\n", decades[["price_trend", "economic_trend", "blend_20", "blend_50"]].round(2).to_string())


if __name__ == "__main__":
    main()
