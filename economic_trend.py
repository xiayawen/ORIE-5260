from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_backtest_adj import ROOT, read_asset_map, read_returns

# ---------------------------------------------------------------- configuration

TARGET_VOL = 0.10
VOL_WINDOW = 12
VOL_FLOOR = 0.01              # annualized; stops 1/vol blowing up on near-zero-vol rate futures
SCALE_WINDOW = 36
TCOST_BPS = 2.0
ROLLS_PER_YEAR = 4
EVAL_START = "1980-01-01"     # all five themes available (GS2 starts mid-1976)
IS_END = "2014-12-31"
OUT = ROOT / "outputs" / "economic_trend_output"
MACRO_DIR = ROOT / "macro_data"

SIGNS = pd.DataFrame(
    {"EQ": [1, -1, 1, -1, 1], "FI": [-1, -1, -1, -1, -1],
     "FX": [1, 1, -1, 1, 1], "COMM": [1, 1, 1, -1, 1]},
    index=["growth", "inflation", "trade", "monetary", "risk_aversion"],
)
FX_HOME_FLIP = -1                    # FX futures are foreign currency vs USD
EQUITY_PROXY = ["SP", "ND", "RL", "ZD", "MD"]   # US equity index futures
NON_US_USD_LISTED = {"NK", "XX"}     # USD-listed contracts on foreign equity indices
RATE_FUTURES_IN_FX = {"EC"}          # Eurodollar is a US rate future -> FI

SIGNAL_MODE = "sign"     # "sign" = +/-1; "zscore" = change / expanding std, capped (variant)
Z_CAP = 2.0
Z_MIN_HIST = 36
SMOOTH_MONTHS = 3        # trailing mean of the last k monthly signals (chosen on 1980-1997)
US_ONLY = True           # False reproduces v1 (US macro applied to every market)
CLASS_BALANCE = False    # variant: equal risk per asset class (rejected on 1980-1997)
ENHANCED_WEIGHT = 0.20   # share of the economic sleeve (chosen on 1980-1997)
BLEND_WEIGHTS = (0.1, 0.2, 0.25, 0.3, 0.4, 0.5)


# ---------------------------------------------------------------- data


def _to_month_end(index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).to_period("M").to_timestamp("M")


def read_table(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path) if path.suffix.lower() in (".xls", ".xlsx") else pd.read_csv(path)
    frame = frame.rename(columns={frame.columns[0]: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"]).set_index("Date").sort_index()
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)


def to_monthly_returns(frame: pd.DataFrame) -> pd.DataFrame:
    """Accept monthly returns, daily returns or daily prices; return monthly returns."""
    spacing = pd.Series(frame.index).diff().dt.days.median()
    if spacing >= 20:                                   # already monthly
        out = frame.copy()
        out.index = _to_month_end(out.index)
        return out.groupby(level=0).last()
    is_price = (frame.dropna(how="all").abs().median() > 0.5).mean() > 0.5
    daily = frame.pct_change(fill_method=None) if is_price else frame
    monthly = (1 + daily).resample("ME").prod(min_count=1) - 1
    monthly.index = _to_month_end(monthly.index)
    return monthly


def load_returns(new_data: Path | None = None) -> pd.DataFrame:
    """MonthlyReturns.csv up to IS_END, then the new data (if any) after IS_END.

    History is kept so 12-month signals, 12-month vol and 36-month scaling are
    warmed up at the start of the out-of-sample period.
    """
    hist = read_returns()
    hist.index = _to_month_end(hist.index)
    if new_data is None:
        return hist
    new = to_monthly_returns(read_table(Path(new_data)))
    known = set(read_asset_map()["ID"])
    unknown = [c for c in new.columns if c not in known]
    if unknown:
        print(f"[load_returns] ignoring columns not in AssetMapCsv.csv: {unknown}")
    new = new[[c for c in new.columns if c in known]]
    after = new.loc[new.index > pd.Timestamp(IS_END)]
    print(f"[load_returns] new data: {after.index.min():%Y-%m} to {after.index.max():%Y-%m}, "
          f"{after.notna().any().sum()} instruments")
    combined = pd.concat([hist.loc[:IS_END], after]).sort_index()
    return combined.reindex(columns=sorted(set(hist.columns) | set(after.columns)))


def read_fred(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0]).dt.to_period("M")
    return s.groupby(level=0).mean().dropna()      # daily -> monthly average when needed


def lag_one_month(s: pd.Series) -> pd.Series:
    """Value for month m becomes usable at the end of month m+1."""
    out = s.copy()
    out.index = out.index + 1
    return out


# ---------------------------------------------------------------- signals


def to_signal(x: pd.Series) -> pd.Series:
    """sign: +1/-1.  zscore: x / expanding std (>= Z_MIN_HIST obs), clipped, in [-1, 1]."""
    if SIGNAL_MODE == "sign":
        return np.sign(x)
    scale = x.expanding(min_periods=Z_MIN_HIST).std()
    return (x / scale).clip(-Z_CAP, Z_CAP) / Z_CAP


def macro_signals(returns: pd.DataFrame, macro_dir: Path = MACRO_DIR) -> pd.DataFrame:
    """One column per theme, indexed like `returns`, using only data known at each month-end."""
    periods = returns.index.to_period("M")
    out = pd.DataFrame(index=periods)

    indpro = lag_one_month(read_fred(macro_dir / "INDPRO.csv"))      # publication lag
    out["growth"] = to_signal(np.log(indpro).diff(12).diff(12)).reindex(periods)

    cpi = lag_one_month(read_fred(macro_dir / "CPIAUCSL.csv"))       # publication lag
    out["inflation"] = to_signal(np.log(cpi).diff(12).diff(12)).reindex(periods)

    gs2 = read_fred(macro_dir / "GS2.csv")
    out["monetary"] = to_signal(gs2.diff(12)).reindex(periods)

    asset_class = read_asset_map().set_index("ID")["AssetClass"]
    r = returns.copy()
    r.index = periods
    fx = [c for c in r.columns if asset_class.get(c) == "FX" and c not in RATE_FUTURES_IN_FX]
    fx_12m = r[fx].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True)
    out["trade"] = to_signal(fx_12m)                        # foreign FX up = USD depreciation

    eq = [c for c in EQUITY_PROXY if c in r.columns]
    risk = to_signal(r[eq].rolling(12, min_periods=12).sum().mean(axis=1, skipna=True))
    baa = macro_dir / "BAA10Y.csv"
    if baa.exists():
        credit = -to_signal(read_fred(baa).diff(12)).reindex(periods)   # narrowing = risk-on
        both = pd.concat([risk, credit], axis=1)
        combined = both.mean(axis=1, skipna=True)
        risk = (np.sign(combined) if SIGNAL_MODE == "sign" else combined).where(both.notna().any(axis=1))
    out["risk_aversion"] = risk

    last_needed = periods.max()
    for name, series in {"INDPRO": indpro, "CPI": cpi, "GS2": gs2}.items():
        if series.index.max() < last_needed:
            print(f"[macro_signals] warning: {name} ends {series.index.max()}, returns end {last_needed}; "
                  "update macro_data/ from FRED")
    out.index = returns.index
    return out[SIGNS.index]


# ---------------------------------------------------------------- portfolios


def instrument_vol(returns: pd.DataFrame) -> pd.DataFrame:
    """Trailing 12-month vol, floored at VOL_FLOOR (applied to baseline and enhanced alike).

    Without the floor, Eurodollar (EC) and short-sterling vol fell to ~0.1% a year at the
    zero lower bound and 1/vol sizing pushed gross leverage to 28x (2014). The floor leaves
    in-sample Sharpe ratios unchanged and caps the extreme leverage.
    """
    vol = returns.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * np.sqrt(12)
    return vol.clip(lower=VOL_FLOOR) if VOL_FLOOR else vol


def risk_weights(direction: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """direction x 1/vol / N over instruments with a valid vol and a non-zero direction."""
    raw = direction / vol
    valid = raw.notna() & (direction != 0)
    n = valid.sum(axis=1).replace(0, np.nan)
    return raw.where(valid).div(n, axis=0).fillna(0.0)


def class_balanced_weights(direction: pd.DataFrame, vol: pd.DataFrame, asset_class: pd.Series) -> pd.DataFrame:
    """Variant: every active asset class gets the same budget inside a theme."""
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


def macro_universe(columns) -> pd.Index:
    """US-relevant instruments: commodities, USD FX pairs, US equity indices and US rates."""
    amap = read_asset_map().set_index("ID")
    return pd.Index([c for c in columns if c in amap.index and (
        amap.loc[c, "AssetClass"] in ("COMM", "FX")
        or (amap.loc[c, "Ccy"] == "USD" and c not in NON_US_USD_LISTED))])


def theme_direction(theme_signal: pd.Series, theme: str, columns, asset_class: pd.Series) -> pd.DataFrame:
    sign_by_col = pd.Series({c: SIGNS.loc[theme, asset_class[c]] * (FX_HOME_FLIP if asset_class[c] == "FX" else 1)
                             for c in columns})
    return pd.DataFrame(np.outer(theme_signal.fillna(0), sign_by_col), index=theme_signal.index, columns=columns)


def scale_to_target(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Scale formation weights so the trailing realized vol of the unscaled strategy hits TARGET_VOL."""
    unscaled = (weights.shift(1) * returns.fillna(0)).sum(axis=1)
    realized = unscaled.rolling(SCALE_WINDOW, min_periods=24).std() * np.sqrt(12)   # known at t
    scale = (TARGET_VOL / realized).replace([np.inf, -np.inf], np.nan)
    return weights.mul(scale, axis=0).fillna(0.0)


def blend_name(w: float) -> str:
    return f"blend_{int(round(w * 100))}"


def price_trend_weights(returns: pd.DataFrame, vol: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the price-only baseline without loading macro data."""
    if vol is None:
        vol = instrument_vol(returns)
    direction = np.sign(returns.rolling(12, min_periods=12).sum())
    return scale_to_target(risk_weights(direction, vol), returns)


def build(returns: pd.DataFrame, macro_dir: Path = MACRO_DIR):
    """Formation weights (month-end t) for the baseline, each theme, the sleeve and the blends."""
    asset_class = read_asset_map().set_index("ID")["AssetClass"].reindex(returns.columns).fillna("COMM")
    asset_class[asset_class.index.isin(RATE_FUTURES_IN_FX)] = "FI"
    universe = macro_universe(returns.columns) if US_ONLY else returns.columns
    vol = instrument_vol(returns)
    signals = macro_signals(returns, macro_dir)
    if SMOOTH_MONTHS > 1:                         # trailing mean of past signals only
        signals = signals.rolling(SMOOTH_MONTHS, min_periods=1).mean()

    strategies = {"price_trend": price_trend_weights(returns, vol)}
    themes = {}
    for theme in SIGNS.index:
        d = theme_direction(signals[theme], theme, returns.columns, asset_class)
        d.loc[:, ~d.columns.isin(universe)] = 0.0
        w = class_balanced_weights(d, vol, asset_class) if CLASS_BALANCE else risk_weights(d, vol)
        themes[theme] = scale_to_target(w, returns)
        strategies[f"theme_{theme}"] = themes[theme]
    strategies["economic_trend"] = scale_to_target(sum(themes.values()) / len(themes), returns)
    for w in sorted(set(BLEND_WEIGHTS) | {ENHANCED_WEIGHT}):
        mix = (1 - w) * strategies["price_trend"] + w * strategies["economic_trend"]
        strategies[blend_name(w)] = scale_to_target(mix, returns)
    strategies["enhanced"] = strategies[blend_name(ENHANCED_WEIGHT)]
    return strategies, signals


# ---------------------------------------------------------------- evaluation


def backtest(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    executed = weights.shift(1).fillna(0.0)
    gross = (executed * returns.fillna(0)).sum(axis=1)
    turnover = executed.diff().fillna(executed).abs().sum(axis=1)
    trade_cost = turnover * TCOST_BPS / 1e4
    roll_cost = executed.abs().sum(axis=1) * ROLLS_PER_YEAR / 12 * TCOST_BPS / 1e4
    return pd.DataFrame({"gross": gross, "net": gross - trade_cost - roll_cost, "turnover": turnover,
                         "tcost": trade_cost + roll_cost, "leverage": executed.abs().sum(axis=1),
                         "imbalance": executed.sum(axis=1), "names": (executed != 0).sum(axis=1)})


def stats(bt: pd.DataFrame, start: str, end: str | None) -> dict:
    b = bt.loc[start:end]
    r = b.net
    wealth = (1 + r).cumprod()
    return {"start": f"{b.index.min():%Y-%m}", "end": f"{b.index.max():%Y-%m}",
            "avg_net_ret": r.mean() * 12, "vol": r.std() * np.sqrt(12),
            "sharpe": r.mean() / r.std() * np.sqrt(12), "t_stat": r.mean() / r.std() * np.sqrt(len(r)),
            "max_dd": (wealth / wealth.cummax() - 1).min(),
            "turnover": b.turnover.mean() * 12, "tcost": b.tcost.mean() * 12,
            "leverage": b.leverage.mean(), "imbalance": b.imbalance.mean(), "names": b.names.mean()}


def summary(results: dict, start: str, end: str | None) -> pd.DataFrame:
    table = pd.DataFrame({name: stats(bt, start, end) for name, bt in results.items()}).T
    net = pd.DataFrame({n: bt.net for n, bt in results.items()}).loc[start:end]
    table["corr_baseline"] = net.corr()["price_trend"]
    return table


def smile(net: pd.DataFrame, market: pd.Series) -> pd.DataFrame:
    """Average strategy return by decile of the same month's S&P 500 futures return."""
    data = net.join(market.rename("market"), how="inner").dropna(subset=["market"])
    data["decile"] = pd.qcut(data["market"], 10, labels=range(1, 11))
    return data.groupby("decile", observed=True).mean() * 100      # % per month


def plot_outputs(net: pd.DataFrame, smiles: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {"price_trend": "Baseline (price trend)", "economic_trend": "Economic trend sleeve",
              "enhanced": f"Enhanced ({1 - ENHANCED_WEIGHT:.0%}/{ENHANCED_WEIGHT:.0%} blend)"}
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for col, label in labels.items():
        ax.plot(np.log((1 + net[col]).cumprod()), label=label)
    ax.axvline(pd.Timestamp(IS_END), color="grey", ls="--", lw=1)
    ax.set_ylabel("log cumulative net return")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "cumulative_net_returns.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(smiles), figsize=(5 * len(smiles), 4), squeeze=False)
    for ax, (period, table) in zip(axes[0], smiles.items()):
        x = np.arange(1, 11)
        ax.bar(x - 0.2, table["price_trend"], 0.4, label="Baseline")
        ax.bar(x + 0.2, table["enhanced"], 0.4, label="Enhanced")
        ax.set_title(f"S&P 500 decile smile, {period.replace('_', '-')}")
        ax.set_xlabel("S&P 500 monthly return decile")
        ax.set_ylabel("avg net return, % per month")
        ax.set_xticks(x)
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "sp500_smile.png", dpi=150)
    plt.close(fig)


def main() -> None:
    global US_ONLY, SIGNAL_MODE
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--new-data", help="new futures data for the out-of-sample test")
    parser.add_argument("--macro-dir", default=str(MACRO_DIR))
    parser.add_argument("--signal", choices=["sign", "zscore"], default=SIGNAL_MODE)
    parser.add_argument("--all-assets", action="store_true", help="apply US macro to every market (v1)")
    args = parser.parse_args()
    US_ONLY, SIGNAL_MODE = not args.all_assets, args.signal
    OUT.mkdir(parents=True, exist_ok=True)

    returns = load_returns(args.new_data)
    strategies, signals = build(returns, Path(args.macro_dir))
    results = {name: backtest(w, returns) for name, w in strategies.items()}
    net = pd.DataFrame({n: bt.net for n, bt in results.items()})
    net.to_csv(OUT / "monthly_net_returns.csv")
    signals.to_csv(OUT / "theme_signals.csv")

    main_rows = ["price_trend", "economic_trend", "enhanced"]
    periods = {"in_sample": (EVAL_START, IS_END)}
    oos_start = (pd.Timestamp(IS_END) + pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")
    if net.index.max() > pd.Timestamp(IS_END):
        periods["out_of_sample"] = (oos_start, None)

    smiles = {}
    for label, (start, end) in periods.items():
        table = summary(results, start, end)
        table.to_csv(OUT / f"summary_{label}.csv")
        net.loc[start:end].corr().to_csv(OUT / f"correlations_{label}.csv")
        smiles[label] = smile(net.loc[start:end, main_rows], returns["SP"])
        smiles[label].to_csv(OUT / f"sp500_smile_{label}.csv")
        print(f"\n== {label}: {table.loc['price_trend', 'start']} to {table.loc['price_trend', 'end']} ==")
        cols = ["sharpe", "avg_net_ret", "vol", "max_dd", "turnover", "tcost", "leverage", "imbalance",
                "names", "corr_baseline"]
        print(table.loc[main_rows + [f"theme_{t}" for t in SIGNS.index], cols].astype(float).round(2).to_string())

    ev = net.loc[EVAL_START:]
    decades = ev.groupby((ev.index.year // 10) * 10).apply(lambda x: x.mean() / x.std() * np.sqrt(12))
    decades.to_csv(OUT / "sharpe_by_decade.csv")
    print("\nSharpe by decade\n", decades[main_rows].round(2).to_string())
    plot_outputs(ev, smiles, OUT)
    print(f"\noutputs written to {OUT}")


if __name__ == "__main__":
    main()
