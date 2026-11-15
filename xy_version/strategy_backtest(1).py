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
    """Cumulative sum of monthly returns, matching the lecture charts."""
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for result in results:
        ax.plot(result["returns"].index, result["returns"].cumsum(), label=result["name"], linewidth=1.8)
    ax.axhline(0.0, color="#666666", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("Cumulative return (sum of monthly returns)")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
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


# ---------------------------------------------------------------- strategy sets


def build_baseline(returns: pd.DataFrame, asset_map: pd.DataFrame) -> tuple[dict, dict]:
    vol = expanding_volatility(returns)
    signal = momentum_signal(returns, BASELINE_LOOKBACK)
    tsmom = backtest_strategy(returns, tsmom_weights(signal, vol, asset_map), TSMOM_NAME)
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
    return [
        backtest_strategy(returns, tsmom_weights(signal, vol, asset_map, allocation), name)
        for name, signal, vol, allocation in specs
    ]


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
    experiment_summary = summary_table([tsmom] + experiments + [static], static)
    experiment_summary["Correl(Baseline)"] = [
        res["returns"].corr(tsmom["returns"]) for res in [tsmom] + experiments + [static]
    ]
    experiment_summary.to_csv(OUT_DIR / "experiment_summary.csv", index=False, float_format="%.6g")
    for res in experiments:
        monthly[res["name"]] = res["returns"]
    monthly.to_csv(OUT_DIR / "monthly_returns.csv", float_format="%.10g")

    plot_cumulative([tsmom, static], "cumulative_tsmom_vs_static.png",
                    "Cumulative Returns: TSMOM Baseline vs Static Benchmark (1976-2014)")
    plot_cumulative(lookbacks + [static], "cumulative_lookbacks.png",
                    "Cumulative Returns: Different Lookbacks (1976-2014)")
    plot_cumulative([tsmom] + experiments + [static], "cumulative_experiments.png",
                    "Cumulative Returns: Baseline vs Experiments (1976-2014)")
    plot_asset_class_alpha(asset_class_corr)

    print(f"Wrote strategy outputs to {OUT_DIR}")
    if plt is None:
        print("matplotlib is not installed, so plot files were skipped.")
    cols = ["strategy", "Avg", "Std", "SR", "Correl(Static)", "max_drawdown", "avg_monthly_turnover"]
    print("\nLookbacks (slide 31):")
    print(lookback_summary[cols].round(3).to_string(index=False))
    print("\nExperiments:")
    print(experiment_summary[cols + ["Correl(Baseline)"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
