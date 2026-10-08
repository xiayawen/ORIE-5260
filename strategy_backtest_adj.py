"""Baseline TSMOM strategy (Lecture 6 replication) plus three supplementary experiments.

Lecture baseline (slides 25-28):
- Signal: sign of the trailing 12-month return (+1 long / -1 short).
- Risk model: expanding-window realized volatility per instrument, using only data
  through month t; an instrument needs at least 36 valid months to enter.
- Position: signal * 40% / vol, then divided by the number of instruments in the universe.
- Rebalance monthly; positions formed at month t earn the month t+1 return.
- Static benchmark: same vol-scaled instruments, always long.
- Statistics are reported from 1976-01 onward (as in the lecture charts).

Experiments (each changes one thing vs the baseline):
- E1 EWMA vol: exponentially weighted volatility (half-life 6 months) instead of expanding.
- E2 Asset-class risk budget: equal weight across asset classes, 1/N within each class.
- E3 Multi-lookback: average of 1, 3, 6 and 12-month signals.
- E4 Combined: E1 + E2 + E3.
"""

from pathlib import Path

import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
except ModuleNotFoundError:
    plt = None


TRADING_MONTHS = 12
LECTURE_VOL_TARGET = 0.40
VOL_MIN_MONTHS = 36
BASELINE_LOOKBACK = 12
MULTI_LOOKBACKS = (1, 3, 6, 12)
EWMA_HALFLIFE = 6
EVAL_START = "1976-01-01"

TSMOM_NAME = "TSMOM_Baseline"
STATIC_NAME = "Static_Bmk"

# Lecture 6 numbers used to check the replication (slides 28 and 31).
LECTURE_TARGETS = {
    "TSMOM_12m": {"Avg": 0.111, "Std": 0.111, "SR": 1.00, "Correl(Static)": 0.08},
    "TSMOM_6m": {"Avg": 0.090, "Std": 0.114, "SR": 0.79, "Correl(Static)": -0.01},
    "TSMOM_3m": {"Avg": 0.096, "Std": 0.118, "SR": 0.81, "Correl(Static)": -0.09},
    "TSMOM_1m": {"Avg": 0.081, "Std": 0.112, "SR": 0.72, "Correl(Static)": -0.11},
    "Static_Bmk": {"Avg": 0.069, "Std": 0.145, "SR": 0.47, "Correl(Static)": 1.00},
}


def find_project_root() -> Path:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    for candidate in (start, *start.parents):
        if (candidate / "MonthlyReturns.csv").exists() and (candidate / "AssetMapCsv.csv").exists():
            return candidate
    raise FileNotFoundError("Could not find MonthlyReturns.csv and AssetMapCsv.csv.")


ROOT = find_project_root()
OUT_DIR = ROOT / "outputs" / "strategy"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- data


def read_returns() -> pd.DataFrame:
    returns = pd.read_csv(ROOT / "MonthlyReturns.csv")
    date_col = returns.columns[0]
    returns = returns.rename(columns={date_col: "Date"})
    returns["Date"] = pd.to_datetime(returns["Date"], errors="coerce")
    returns = returns.dropna(subset=["Date"]).set_index("Date").sort_index()
    returns = returns.apply(pd.to_numeric, errors="coerce")
    returns = returns.replace([np.inf, -np.inf], np.nan)
    return returns


def read_asset_map() -> pd.DataFrame:
    asset_map = pd.read_csv(ROOT / "AssetMapCsv.csv")
    asset_map["ID"] = asset_map["ID"].astype(str).str.strip()
    return asset_map


# ---------------------------------------------------------------- signals


def momentum_signal(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """+1 / -1 by the sign of the summed past `lookback` monthly returns (through month t)."""
    trailing_return = returns.rolling(lookback, min_periods=lookback).sum()
    return np.sign(trailing_return)


def multi_lookback_signal(returns: pd.DataFrame, lookbacks=MULTI_LOOKBACKS) -> pd.DataFrame:
    """Equal-weighted average of several +1/-1 signals; values in [-1, 1]."""
    signals = [momentum_signal(returns, lb) for lb in lookbacks]
    return sum(signals) / len(signals)


# ---------------------------------------------------------------- risk model


def expanding_volatility(returns: pd.DataFrame, min_months: int = VOL_MIN_MONTHS) -> pd.DataFrame:
    """Annualized vol using all history through month t; NaN until `min_months` valid obs."""
    return returns.expanding(min_periods=min_months).std() * np.sqrt(TRADING_MONTHS)


def ewma_volatility(
    returns: pd.DataFrame,
    halflife: float = EWMA_HALFLIFE,
    min_months: int = VOL_MIN_MONTHS,
) -> pd.DataFrame:
    """Exponentially weighted annualized vol; same entry threshold as the expanding model."""
    vol = returns.ewm(halflife=halflife, min_periods=min_months, ignore_na=True).std()
    vol = vol.where(returns.notna().cumsum() >= min_months)
    return vol * np.sqrt(TRADING_MONTHS)


# ---------------------------------------------------------------- portfolio construction


def allocation_divisor(universe: pd.DataFrame, allocation: str, asset_map: pd.DataFrame) -> pd.DataFrame:
    """Per-instrument divisor: N_t for 1/N, or (#classes_t x #instruments in class_t) for class budgets."""
    if allocation == "instrument":
        count = universe.sum(axis=1).replace(0, np.nan)
        return pd.DataFrame({col: count for col in universe.columns}, index=universe.index)

    if allocation == "asset_class":
        class_lookup = asset_map.set_index("ID")["AssetClass"]
        classes = universe.columns.map(class_lookup)
        per_class = universe.T.groupby(classes).sum().T
        n_classes = (per_class > 0).sum(axis=1).replace(0, np.nan)
        divisor = per_class[classes].copy()
        divisor.columns = universe.columns
        return divisor.replace(0, np.nan).mul(n_classes, axis=0)

    raise ValueError(f"Unknown allocation: {allocation}")


def tsmom_weights(
    signal: pd.DataFrame,
    vol: pd.DataFrame,
    asset_map: pd.DataFrame,
    allocation: str = "instrument",
) -> pd.DataFrame:
    universe = vol.notna()
    scaled_position = signal.fillna(0.0) * LECTURE_VOL_TARGET / vol
    return scaled_position.where(universe) / allocation_divisor(universe, allocation, asset_map)


def static_weights(vol: pd.DataFrame, asset_map: pd.DataFrame, allocation: str = "instrument") -> pd.DataFrame:
    universe = vol.notna()
    scaled_position = LECTURE_VOL_TARGET / vol
    return scaled_position.where(universe) / allocation_divisor(universe, allocation, asset_map)


# ---------------------------------------------------------------- backtest


def backtest_strategy(returns: pd.DataFrame, weights: pd.DataFrame, name: str) -> dict:
    """Weights formed at month t are applied to month t+1 returns."""
    clean_weights = weights.fillna(0.0)
    execution_weights = clean_weights.shift(1).fillna(0.0)
    instrument_returns = execution_weights * returns.fillna(0.0)
    portfolio_returns = instrument_returns.sum(axis=1)
    turnover = execution_weights.diff().abs().sum(axis=1).fillna(0.0)

    return {
        "name": name,
        "returns": portfolio_returns.loc[EVAL_START:],
        "weights": clean_weights,
        "execution_weights": execution_weights,
        "instrument_returns": instrument_returns.loc[EVAL_START:],
        "turnover": turnover.loc[EVAL_START:],
    }


# ---------------------------------------------------------------- statistics


def max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return drawdown.min()


def cvar_95(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return np.nan
    var = clean.quantile(0.05)
    return clean[clean <= var].mean()


def performance_summary(result: dict, static_returns: pd.Series) -> dict:
    """Lecture-style statistics: arithmetic Avg x12, Std x sqrt(12), SR = Avg/Std (rf = 0)."""
    r = result["returns"].dropna()
    avg = r.mean() * TRADING_MONTHS
    std = r.std() * np.sqrt(TRADING_MONTHS)
    return {
        "strategy": result["name"],
        "start": r.index.min().date(),
        "end": r.index.max().date(),
        "months": len(r),
        "Avg": avg,
        "Std": std,
        "SR": avg / std,
        "Correl(Static)": r.corr(static_returns),
        "geometric_return": (1.0 + r).prod() ** (TRADING_MONTHS / len(r)) - 1.0,
        "max_drawdown": max_drawdown(r),
        "skew": r.skew(),
        "kurtosis": r.kurt(),
        "var_95": r.quantile(0.05),
        "cvar_95": cvar_95(r),
        "hit_rate": (r > 0).mean(),
        "avg_monthly_turnover": result["turnover"].mean(),
    }


def summary_table(results: list[dict], static: dict) -> pd.DataFrame:
    return pd.DataFrame([performance_summary(res, static["returns"]) for res in results])


def vol_matched_returns(returns: pd.Series, target_std: float) -> pd.Series:
    """Rescale a return series to a given annualized vol. Presentation only: the scale factor
    uses full-sample vol, so it is not tradable, but it leaves the Sharpe ratio unchanged and
    lets strategies with different risk levels be compared on CAGR, drawdown and growth of $1."""
    return returns * target_std / (returns.std() * np.sqrt(TRADING_MONTHS))


def experiment_table(results: list[dict], baseline: dict, static: dict) -> pd.DataFrame:
    table = summary_table(results, static)
    target_std = baseline["returns"].std() * np.sqrt(TRADING_MONTHS)
    scaled = [vol_matched_returns(res["returns"], target_std) for res in results]
    table["Correl(Baseline)"] = [res["returns"].corr(baseline["returns"]) for res in results]
    table["CAGR@BaselineVol"] = [(1.0 + r).prod() ** (TRADING_MONTHS / len(r)) - 1.0 for r in scaled]
    table["MaxDD@BaselineVol"] = [max_drawdown(r) for r in scaled]
    return table


def replication_check(lookback_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in lookback_table.iterrows():
        target = LECTURE_TARGETS.get(row["strategy"])
        if target is None:
            continue
        for metric, lecture_value in target.items():
            rows.append(
                {
                    "strategy": row["strategy"],
                    "metric": metric,
                    "ours": row[metric],
                    "lecture": lecture_value,
                    "difference": row[metric] - lecture_value,
                }
            )
    return pd.DataFrame(rows)


def asset_class_returns(result: dict, asset_map: pd.DataFrame) -> pd.DataFrame:
    class_lookup = asset_map.set_index("ID")["AssetClass"].to_dict()
    contribution = result["instrument_returns"]
    class_returns = {}
    for asset_class in sorted(asset_map["AssetClass"].dropna().unique()):
        cols = [col for col in contribution.columns if class_lookup.get(col) == asset_class]
        class_returns[asset_class] = contribution[cols].sum(axis=1)
    return pd.DataFrame(class_returns)


def correlation_by_asset_class(tsmom: dict, static: dict, asset_map: pd.DataFrame) -> pd.DataFrame:
    tsmom_class = asset_class_returns(tsmom, asset_map)
    static_class = asset_class_returns(static, asset_map)
    rows = []
    for asset_class in tsmom_class.columns:
        paired = pd.concat([tsmom_class[asset_class], static_class[asset_class]], axis=1).dropna()
        paired.columns = ["tsmom", "static"]
        alpha = paired["tsmom"] - paired["static"]
        rows.append(
            {
                "asset_class": asset_class,
                "correlation_tsmom_static": paired["tsmom"].corr(paired["static"]),
                "tsmom_annualized_contribution": paired["tsmom"].mean() * TRADING_MONTHS,
                "static_annualized_contribution": paired["static"].mean() * TRADING_MONTHS,
                "alpha_annualized_contribution": alpha.mean() * TRADING_MONTHS,
                "alpha_monthly_volatility": alpha.std(),
            }
        )
    return pd.DataFrame(rows)


def correlation_by_instrument(tsmom: dict, static: dict, asset_map: pd.DataFrame) -> pd.DataFrame:
    lookup = asset_map.set_index("ID")[["Name", "AssetClass"]]
    rows = []
    for instrument in tsmom["instrument_returns"].columns:
        paired = pd.concat(
            [tsmom["instrument_returns"][instrument], static["instrument_returns"][instrument]], axis=1
        ).dropna()
        paired.columns = ["tsmom", "static"]
        alpha = paired["tsmom"] - paired["static"]
        meta = lookup.loc[instrument] if instrument in lookup.index else pd.Series({"Name": np.nan, "AssetClass": np.nan})
        rows.append(
            {
                "ID": instrument,
                "Name": meta["Name"],
                "AssetClass": meta["AssetClass"],
                "correlation_tsmom_static": paired["tsmom"].corr(paired["static"]),
                "tsmom_annualized_contribution": paired["tsmom"].mean() * TRADING_MONTHS,
                "static_annualized_contribution": paired["static"].mean() * TRADING_MONTHS,
                "alpha_annualized_contribution": alpha.mean() * TRADING_MONTHS,
                "alpha_monthly_volatility": alpha.std(),
            }
        )
    return pd.DataFrame(rows).sort_values("alpha_annualized_contribution", ascending=False)


# ---------------------------------------------------------------- plots


def plot_cumulative(results: list[dict], filename: str, title: str) -> None:
    """Compounded growth of $1 on a log scale (the lecture charts sum monthly returns instead)."""
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for result in results:
        equity = (1.0 + result["returns"]).cumprod()
        ax.plot(equity.index, equity, label=result["name"], linewidth=1.8)
    ax.axhline(1.0, color="#666666", linewidth=0.8)
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_ylabel("Growth of $1 (compounded, log scale)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"${y:g}"))
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_asset_class_alpha(asset_class_corr: pd.DataFrame) -> None:
    if plt is None:
        return
    ordered = asset_class_corr.sort_values("alpha_annualized_contribution", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(ordered["asset_class"], ordered["alpha_annualized_contribution"], color="#59A14F")
    ax.axvline(0.0, color="#666666", linewidth=0.8)
    ax.set_title("Annualized Alpha Contribution by Asset Class")
    ax.set_xlabel("TSMOM contribution minus Static contribution")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "asset_class_alpha_contribution.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


BASELINE_COLOR = "#1f4e79"
EXPERIMENT_COLOR = "#e07b00"
STATIC_COLOR = "#9a9a9a"
ROLLING_MONTHS = 36

EXPERIMENT_TITLES = {
    "E1_EWMA_Vol": "E1: EWMA volatility (half-life 6m) vs expanding window",
    "E2_AssetClass_Budget": "E2: Equal risk budget per asset class vs 1/N instruments",
    "E3_Multi_Lookback": "E3: Average of 1/3/6/12m signals vs 12m only",
    "E4_Combined": "E4: E1 + E2 + E3 combined",
}


def vol_matched_set(results: list[dict], baseline: dict) -> list[dict]:
    target_std = baseline["returns"].std() * np.sqrt(TRADING_MONTHS)
    return [{**res, "returns": vol_matched_returns(res["returns"], target_std)} for res in results]


def drawdown_series(returns: pd.Series) -> pd.Series:
    equity = (1.0 + returns).cumprod()
    return equity / equity.cummax() - 1.0


def risk_share_by_class(result: dict, asset_map: pd.DataFrame) -> pd.Series:
    """Average share of ex-ante risk (|w| x vol, diagonal model) held in each asset class."""
    risk = (result["weights"].abs() * result["vol"]).loc[EVAL_START:]
    class_lookup = asset_map.set_index("ID")["AssetClass"]
    by_class = risk.T.groupby(risk.columns.map(class_lookup)).sum().T
    return by_class.div(by_class.sum(axis=1), axis=0).mean()


def _mechanism_panel(ax, experiment, baseline, experiments, returns, asset_map, summary) -> None:
    name = experiment["name"]
    if name == "E1_EWMA_Vol":
        instrument = "ZU"  # crude oil: long history and clear volatility regimes
        realized = returns[instrument].rolling(12).std().shift(-11) * np.sqrt(TRADING_MONTHS)
        ax.plot(baseline["vol"][instrument].loc[EVAL_START:], color=BASELINE_COLOR, label="Expanding (baseline)")
        ax.plot(experiment["vol"][instrument].loc[EVAL_START:], color=EXPERIMENT_COLOR, label="EWMA (E1)")
        ax.plot(realized.loc[EVAL_START:], color=STATIC_COLOR, linewidth=1.0, label="Realized next 12m")
        ax.set_title("Vol estimate for Crude Oil: EWMA tracks realized risk")
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    elif name == "E3_Multi_Lookback":
        values = experiment["signal"].loc[EVAL_START:].where(experiment["vol"].loc[EVAL_START:].notna())
        shares = values.stack().round(2).value_counts(normalize=True).sort_index()
        shares = shares[shares > 0.005]  # drop rare ±0.25/±0.75 from exact-zero trailing sums
        ax.bar([f"{v:+.1f}" for v in shares.index], shares.values, color=EXPERIMENT_COLOR)
        ax.set_title("E3 signal values: weaker trends get smaller positions")
        ax.set_xlabel("Signal (average of four ±1 signals)")
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    elif name == "E2_AssetClass_Budget":
        base_share = risk_share_by_class(baseline, asset_map)
        exp_share = risk_share_by_class(experiment, asset_map).reindex(base_share.index)
        x = np.arange(len(base_share))
        ax.bar(x - 0.2, base_share.values, 0.4, color=BASELINE_COLOR, label="Baseline (1/N)")
        ax.bar(x + 0.2, exp_share.values, 0.4, color=EXPERIMENT_COLOR, label="E2")
        ax.set_xticks(x, base_share.index)
        ax.set_title("Average share of ex-ante risk by asset class")
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    else:
        rows = summary.set_index("strategy").loc[[baseline["name"]] + [e["name"] for e in experiments], "SR"]
        colors = [BASELINE_COLOR] + [EXPERIMENT_COLOR if n == name else "#f2c189" for n in rows.index[1:]]
        labels = ["Baseline"] + [n.split("_")[0] for n in rows.index[1:]]
        ax.bar(labels, rows.values, color=colors)
        for i, v in enumerate(rows.values):
            ax.text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=9)
        ax.set_title("Sharpe ratio: improvements are not additive")
        ax.set_ylim(0, rows.max() * 1.15)
    ax.grid(alpha=0.25)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(frameon=False, fontsize=8)


def plot_experiment(experiment, baseline, static, experiments, returns, asset_map, summary) -> None:
    """2x2 figure per experiment: vol-matched growth and drawdown, rolling risk, and the mechanism."""
    if plt is None:
        return
    base_s, exp_s, static_s = vol_matched_set([baseline, experiment, static], baseline)
    stats = summary.set_index("strategy")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    ax = axes[0, 0]
    for res, color in [(base_s, BASELINE_COLOR), (exp_s, EXPERIMENT_COLOR), (static_s, STATIC_COLOR)]:
        row = stats.loc[res["name"]]
        label = f"{res['name']} (SR {row['SR']:.2f}, CAGR {row['CAGR@BaselineVol']:.1%})"
        ax.plot((1.0 + res["returns"]).cumprod(), color=color, linewidth=1.6, label=label)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"${y:g}"))
    ax.set_title("Growth of $1, compounded (all scaled to baseline vol)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[0, 1]
    for res, color in [(base_s, BASELINE_COLOR), (exp_s, EXPERIMENT_COLOR)]:
        dd = drawdown_series(res["returns"])
        ax.plot(dd, color=color, linewidth=1.3, label=f"{res['name']} (max {dd.min():.0%})")
    ax.set_title("Drawdown, compounded (scaled to baseline vol)")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    for res, color in [(baseline, BASELINE_COLOR), (experiment, EXPERIMENT_COLOR)]:
        rolling = res["returns"].rolling(ROLLING_MONTHS).std() * np.sqrt(TRADING_MONTHS)
        ax.plot(rolling, color=color, linewidth=1.3,
                label=f"{res['name']} (turnover {stats.loc[res['name'], 'avg_monthly_turnover']:.2f}/month)")
    ax.set_title(f"Rolling {ROLLING_MONTHS}m realized vol (unscaled)")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25)

    _mechanism_panel(axes[1, 1], experiment, baseline, experiments, returns, asset_map, stats.reset_index())

    fig.suptitle(EXPERIMENT_TITLES.get(experiment["name"], experiment["name"]), fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"experiment_{experiment['name'].split('_')[0]}.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def plot_experiment_summary(summary: pd.DataFrame) -> None:
    if plt is None:
        return
    table = summary.set_index("strategy")
    labels = [n.split("_")[0] if n.startswith("E") else n.replace("TSMOM_", "") for n in table.index]
    colors = [STATIC_COLOR if "Static" in n else BASELINE_COLOR if "Baseline" in n else EXPERIMENT_COLOR
              for n in table.index]
    panels = [
        ("SR", "Sharpe ratio", "{:.2f}", False),
        ("CAGR@BaselineVol", "CAGR at baseline vol", "{:.1%}", True),
        ("MaxDD@BaselineVol", "Max drawdown at baseline vol", "{:.0%}", True),
        ("avg_monthly_turnover", "Average monthly turnover", "{:.2f}", False),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.8))
    for ax, (col, title, fmt, pct) in zip(axes, panels):
        values = table[col].values
        ax.bar(labels, values, color=colors)
        for i, v in enumerate(values):
            ax.text(i, v, fmt.format(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
        ax.set_title(title)
        ax.axhline(0.0, color="#666666", linewidth=0.8)
        if pct:
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.tick_params(axis="x", labelsize=9)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Baseline vs experiments (1976-2014); CAGR and drawdown use returns scaled to baseline vol",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "experiment_summary.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- strategy sets


def build_baseline(returns: pd.DataFrame, asset_map: pd.DataFrame) -> tuple[dict, dict]:
    vol = expanding_volatility(returns)
    signal = momentum_signal(returns, BASELINE_LOOKBACK)
    tsmom = backtest_strategy(returns, tsmom_weights(signal, vol, asset_map), TSMOM_NAME)
    tsmom.update({"signal": signal, "vol": vol, "allocation": "instrument"})
    static = backtest_strategy(returns, static_weights(vol, asset_map), STATIC_NAME)
    return tsmom, static


def build_lookback_set(returns: pd.DataFrame, asset_map: pd.DataFrame) -> list[dict]:
    vol = expanding_volatility(returns)
    return [
        backtest_strategy(returns, tsmom_weights(momentum_signal(returns, lb), vol, asset_map), f"TSMOM_{lb}m")
        for lb in MULTI_LOOKBACKS
    ]


def build_experiments(returns: pd.DataFrame, asset_map: pd.DataFrame) -> list[dict]:
    exp_vol = expanding_volatility(returns)
    ewma_vol = ewma_volatility(returns)
    signal_12 = momentum_signal(returns, BASELINE_LOOKBACK)
    signal_multi = multi_lookback_signal(returns)

    specs = [
        ("E1_EWMA_Vol", signal_12, ewma_vol, "instrument"),
        ("E2_AssetClass_Budget", signal_12, exp_vol, "asset_class"),
        ("E3_Multi_Lookback", signal_multi, exp_vol, "instrument"),
        ("E4_Combined", signal_multi, ewma_vol, "asset_class"),
    ]
    results = []
    for name, signal, vol, allocation in specs:
        result = backtest_strategy(returns, tsmom_weights(signal, vol, asset_map, allocation), name)
        result.update({"signal": signal, "vol": vol, "allocation": allocation})
        results.append(result)
    return results


def main() -> None:
    returns = read_returns()
    asset_map = read_asset_map()

    tsmom, static = build_baseline(returns, asset_map)

    # 1. Lecture replication: baseline vs static, and the lookback table from slide 31.
    baseline_summary = summary_table([tsmom, static], static)
    baseline_summary.to_csv(OUT_DIR / "baseline_summary.csv", index=False, float_format="%.6g")

    lookbacks = build_lookback_set(returns, asset_map)
    lookback_summary = summary_table(lookbacks + [static], static)
    lookback_summary.to_csv(OUT_DIR / "lookback_summary.csv", index=False, float_format="%.6g")
    replication_check(lookback_summary).to_csv(OUT_DIR / "replication_check.csv", index=False, float_format="%.4f")

    monthly = pd.DataFrame({tsmom["name"]: tsmom["returns"], static["name"]: static["returns"]})
    monthly["Alpha_TSMOM_minus_Static"] = monthly[TSMOM_NAME] - monthly[STATIC_NAME]

    asset_class_corr = correlation_by_asset_class(tsmom, static, asset_map)
    asset_class_corr.to_csv(OUT_DIR / "correlation_alpha_by_asset_class.csv", index=False, float_format="%.6g")
    correlation_by_instrument(tsmom, static, asset_map).to_csv(
        OUT_DIR / "correlation_alpha_by_instrument.csv", index=False, float_format="%.6g"
    )

    # 2. Supplementary experiments, each compared with the same baseline and static benchmark.
    experiments = build_experiments(returns, asset_map)
    experiment_summary = experiment_table([tsmom] + experiments + [static], tsmom, static)
    experiment_summary.to_csv(OUT_DIR / "experiment_summary.csv", index=False, float_format="%.6g")
    for res in experiments:
        monthly[res["name"]] = res["returns"]
    monthly.to_csv(OUT_DIR / "monthly_returns.csv", float_format="%.10g")

    plot_cumulative([tsmom, static], "cumulative_tsmom_vs_static.png",
                    "Cumulative Returns: TSMOM Baseline vs Static Benchmark (1976-2014)")
    plot_cumulative(lookbacks + [static], "cumulative_lookbacks.png",
                    "Cumulative Returns: Different Lookbacks (1976-2014)")
    plot_cumulative(vol_matched_set([tsmom] + experiments + [static], tsmom), "cumulative_experiments.png",
                    "Growth of $1: Baseline vs Experiments, all scaled to baseline vol (1976-2014)")
    for experiment in experiments:
        plot_experiment(experiment, tsmom, static, experiments, returns, asset_map, experiment_summary)
    plot_experiment_summary(experiment_summary)
    plot_asset_class_alpha(asset_class_corr)

    print(f"Wrote strategy outputs to {OUT_DIR}")
    if plt is None:
        print("matplotlib is not installed, so plot files were skipped.")
    cols = ["strategy", "Avg", "geometric_return", "Std", "SR", "Correl(Static)", "max_drawdown", "avg_monthly_turnover"]
    print("\nLookbacks (slide 31):")
    print(lookback_summary[cols].round(3).to_string(index=False))
    print("\nExperiments:")
    print(experiment_summary[cols + ["Correl(Baseline)", "CAGR@BaselineVol", "MaxDD@BaselineVol"]]
          .round(3).to_string(index=False))


if __name__ == "__main__":
    main()
