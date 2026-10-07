from pathlib import Path

import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None


TRADING_MONTHS = 12
LECTURE_VOL_TARGET = 0.40
TSMOM_NAME = "lecture_baseline_tsmom_12m_full_sample_40pct_vol"
STATIC_NAME = "lecture_static_benchmark_full_sample_40pct_vol"


def find_project_root() -> Path:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    for candidate in (start, *start.parents):
        if (candidate / "MonthlyReturns.csv").exists() and (candidate / "AssetMapCsv.csv").exists():
            return candidate
    raise FileNotFoundError("Could not find MonthlyReturns.csv and AssetMapCsv.csv.")


ROOT = find_project_root()
OUT_DIR = ROOT / "outputs" / "strategy"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def momentum_signal(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    trailing_return = (1.0 + returns).rolling(lookback, min_periods=lookback).apply(np.prod, raw=True) - 1.0
    signal = np.sign(trailing_return)
    return signal.where(returns.notna())


def full_sample_volatility(returns: pd.DataFrame) -> pd.Series:
    return returns.std() * np.sqrt(TRADING_MONTHS)


def lecture_tsmom_weights(signal: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    full_sample_vol = full_sample_volatility(returns)
    scaled_position = LECTURE_VOL_TARGET / full_sample_vol.replace(0.0, np.nan)
    weights = signal.mul(scaled_position, axis=1)
    active_count = signal.notna().sum(axis=1).replace(0.0, np.nan)
    return weights.div(active_count, axis=0)


def lecture_static_weights(returns: pd.DataFrame) -> pd.DataFrame:
    full_sample_vol = full_sample_volatility(returns)
    scaled_position = LECTURE_VOL_TARGET / full_sample_vol.replace(0.0, np.nan)
    active = returns.notna()
    active_count = active.sum(axis=1).replace(0.0, np.nan)
    weights = pd.DataFrame(1.0, index=returns.index, columns=returns.columns)
    weights = weights.where(active).mul(scaled_position, axis=1)
    return weights.div(active_count, axis=0)


def backtest_strategy(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    name: str,
) -> dict:
    tradable = returns.notna() & weights.notna()
    clean_weights = weights.where(tradable).fillna(0.0)

    execution_weights = clean_weights.shift(1).fillna(0.0)
    instrument_returns = execution_weights * returns.fillna(0.0)
    portfolio_returns = instrument_returns.sum(axis=1)
    turnover = execution_weights.diff().abs().sum(axis=1).fillna(0.0)

    return {
        "name": name,
        "returns": portfolio_returns,
        "weights": clean_weights,
        "execution_weights": execution_weights,
        "instrument_returns": instrument_returns,
        "turnover": turnover,
    }


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


def performance_summary(result: dict) -> dict:
    r = result["returns"].dropna()
    if r.empty:
        return {"strategy": result["name"]}

    ann_return = (1.0 + r).prod() ** (TRADING_MONTHS / len(r)) - 1.0
    ann_vol = r.std() * np.sqrt(TRADING_MONTHS)
    sharpe = ann_return / ann_vol if ann_vol and not np.isnan(ann_vol) else np.nan

    return {
        "strategy": result["name"],
        "start": r.index.min().date(),
        "end": r.index.max().date(),
        "months": len(r),
        "annual_return": ann_return,
        "annual_volatility": ann_vol,
        "sharpe_0rf": sharpe,
        "max_drawdown": max_drawdown(r),
        "monthly_mean": r.mean(),
        "monthly_volatility": r.std(),
        "skew": r.skew(),
        "kurtosis": r.kurt(),
        "var_95": r.quantile(0.05),
        "cvar_95": cvar_95(r),
        "average_monthly_turnover": result["turnover"].mean(),
    }


def summarize_alpha(tsmom: dict, static: dict) -> pd.DataFrame:
    alpha = tsmom["returns"] - static["returns"]
    rows = [
        performance_summary(tsmom),
        performance_summary(static),
        {
            "strategy": "alpha_tsmom_minus_static",
            "start": alpha.index.min().date(),
            "end": alpha.index.max().date(),
            "months": alpha.dropna().shape[0],
            "annual_return": alpha.mean() * TRADING_MONTHS,
            "annual_volatility": alpha.std() * np.sqrt(TRADING_MONTHS),
            "sharpe_0rf": (alpha.mean() * TRADING_MONTHS) / (alpha.std() * np.sqrt(TRADING_MONTHS)),
            "max_drawdown": max_drawdown(alpha),
            "monthly_mean": alpha.mean(),
            "monthly_volatility": alpha.std(),
            "skew": alpha.skew(),
            "kurtosis": alpha.kurt(),
            "var_95": alpha.quantile(0.05),
            "cvar_95": cvar_95(alpha),
            "average_monthly_turnover": np.nan,
        },
    ]
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
        paired = pd.concat([tsmom["instrument_returns"][instrument], static["instrument_returns"][instrument]], axis=1).dropna()
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


def plot_cumulative_returns(results: list[dict]) -> None:
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(12, 7))
    for result in results:
        equity = (1.0 + result["returns"].fillna(0.0)).cumprod()
        ax.plot(equity.index, equity, label=result["name"], linewidth=1.8)
    ax.axhline(1.0, color="#666666", linewidth=0.8)
    ax.set_title("TSMOM vs Static Benchmark: Cumulative Growth of $1")
    ax.set_ylabel("Growth of $1")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cumulative_tsmom_vs_static.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_cumulative_alpha(tsmom: dict, static: dict) -> None:
    if plt is None:
        return
    alpha = tsmom["returns"] - static["returns"]
    cumulative_alpha = alpha.cumsum()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(cumulative_alpha.index, cumulative_alpha, color="#4C78A8", linewidth=2.0)
    ax.axhline(0.0, color="#666666", linewidth=0.8)
    ax.set_title("Cumulative Alpha: TSMOM Monthly Return Minus Static Monthly Return")
    ax.set_ylabel("Cumulative arithmetic alpha")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cumulative_alpha_tsmom_minus_static.png", dpi=200, bbox_inches="tight")
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
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "asset_class_alpha_contribution.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_strategy_set(returns: pd.DataFrame) -> list[dict]:
    signal_12 = momentum_signal(returns, lookback=12)
    weights_lecture_tsmom = lecture_tsmom_weights(signal_12, returns)
    weights_lecture_static = lecture_static_weights(returns)
    return [
        backtest_strategy(returns, weights_lecture_tsmom, TSMOM_NAME),
        backtest_strategy(returns, weights_lecture_static, STATIC_NAME),
    ]


def write_methodology_note() -> None:
    lines = [
        "# TSMOM Baseline vs Static Benchmark",
        "",
        "## Baseline",
        "- TSMOM baseline: 12-month time-series momentum for each futures underlying.",
        "- TSMOM position: long if trailing 12-month return is positive, short if negative.",
        "- Sizing: each instrument is scaled to 40% annualized volatility using full-sample realized volatility, then averaged across active instruments.",
        "- Timing: signals are computed using information through month t and traded in month t+1.",
        "- Static benchmark: same volatility-scaled instruments, but always long and equally averaged.",
        "- Full-sample volatility contains future information; this is a retrospective classroom baseline, not an out-of-sample backtest.",
        "- No transaction costs, slippage, financing costs, or cash interest are included.",
        "",
        "## Alpha illustration",
        "- Portfolio alpha is measured as monthly TSMOM return minus monthly Static benchmark return.",
        "- Asset-class and instrument tables compare TSMOM and Static contribution streams.",
        "- Alpha here is a return difference, not a factor-regression intercept. Low correlation alone does not establish added value.",
        "- TSMOM requires 12 valid months while Static starts earlier, so their active universes can differ.",
    ]
    (OUT_DIR / "strategy_methodology.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def portfolio_correlations(tsmom: dict, static: dict) -> pd.DataFrame:
    paired = pd.DataFrame({"tsmom": tsmom["returns"], "static": static["returns"]})
    active = tsmom["execution_weights"].abs().sum(axis=1) > 0
    rows = []
    for label, sample in [("full_sample", paired), ("tsmom_active_months", paired.loc[active])]:
        rows.append({"sample": label, "start": sample.index.min().date(),
                     "end": sample.index.max().date(), "months": len(sample),
                     "correlation_tsmom_static": sample["tsmom"].corr(sample["static"])})
    return pd.DataFrame(rows)


def write_group_report(summary: pd.DataFrame, correlations: pd.DataFrame,
                       asset_class_corr: pd.DataFrame) -> None:
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    rows = []
    for label, row in zip(["12-month TSMOM", "Always-long static", "Return difference"],
                          summary.to_dict("records")):
        rows.append(f"| {label} | {row['annual_return']:.2%} | {row['annual_volatility']:.2%} | "
                    f"{row['sharpe_0rf']:.3f} | {row['max_drawdown']:.2%} |")
    corr_text = "\n".join(
        f"- {row['sample']}: correlation **{row['correlation_tsmom_static']:.3f}**, "
        f"{row['months']} months ({row['start']} to {row['end']})."
        for row in correlations.to_dict("records"))
    class_text = "\n".join(
        f"| {row['asset_class']} | {row['correlation_tsmom_static']:.3f} | "
        f"{row['alpha_annualized_contribution']:.2%} |"
        for row in asset_class_corr.to_dict("records"))
    text = f"""# ORIE 5260 — Group Update, October 6, 2026

## This week's progress
Implemented and documented a 12-month time-series momentum baseline, compared it
with an always-long static benchmark, calculated portfolio, asset-class and
instrument correlations, and generated performance and alpha illustrations.
No earlier baseline specification is available in the repository, so a change
relative to a previous version or exact agreement with the lecture cannot be established.

## Data
- `MonthlyReturns.csv`: 58 futures series, 552 monthly observations, January 1969–December 2014.
- Universe: 26 commodity, 14 equity, 10 fixed-income and 8 FX series.
- `FuturesUnderlyingData/`: 62 daily OHLC/volume/open-interest files. Not used by this backtest.
- `Lecture3_livedata.xlsx`: 180 monthly observations, 2000–2014, for SG Trend, GSCI, factors and RF. Not used by this backtest.
- Histories start at different dates; the first monthly row has no valid returns.

## Baseline and benchmark
At month t, the signal is the sign of compounded returns over the latest 12
valid consecutive months. Positive signals are long, negative signals are short,
and zero signals have zero exposure. Instruments without sufficient history are excluded.
Each signal is multiplied by 0.40 / full-sample annualized instrument volatility
and divided by the number of instruments with valid signals. Positions formed
at t earn returns at t+1. Rebalancing is monthly.
The static benchmark uses the same volatility scaling, always holds long positions,
and averages across instruments with available returns. The 40% parameter is
instrument-level scaling; it does not imply 40% portfolio volatility.

## Performance
Full sample: January 1969–December 2014, including initial zero-exposure months.

| Strategy | Annual return | Annual volatility | Return / volatility | Max drawdown |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

Strategy annual returns are compounded annual growth rates. The return-difference
row annualizes the monthly mean arithmetically, so it is not the difference of
the two strategy CAGRs. The code's `sharpe_0rf` uses CAGR / annual volatility
for the strategies, rather than the conventional annualized mean-excess-return Sharpe.

## Correlations
{corr_text}
The active-month sample excludes TSMOM's initial zero-exposure months; it does
not force the two strategies to use identical instrument universes.

| Asset class | TSMOM–static contribution correlation | Annualized return-difference contribution |
|---|---:|---:|
{class_text}

## Alpha illustration and interpretation
Alpha is defined here as TSMOM monthly return minus static monthly return.
It is a descriptive return difference, not a regression alpha or evidence of
statistical significance. The asset-class contributions sum to the portfolio's
annualized mean return difference. Positive contributions show where TSMOM
outperformed the static exposure in this sample; low correlation measures different
return behavior, and alone does not imply superior performance.

![Growth of one dollar](../outputs/strategy/cumulative_tsmom_vs_static.png)

![Cumulative arithmetic return difference](../outputs/strategy/cumulative_alpha_tsmom_minus_static.png)

The alpha curve sums monthly differences; it is not compounded investment wealth.

![Alpha contribution by asset class](../outputs/strategy/asset_class_alpha_contribution.png)

## Limitations and next steps
- Full-sample volatility includes future observations, creating look-ahead bias. Retain this result as the classroom baseline and compare a rolling, historically available volatility estimate next.
- The benchmarks have different availability rules: TSMOM requires 12 months of history, Static does not. Add a comparison using the same eligible universe.
- Missing realized returns are filled with zero; examine delisted or discontinued series before interpreting results.
- Transaction costs, slippage, financing and cash interest are omitted.
- Confirm the lecture's intended baseline and alpha definition. If regression alpha is required, use aligned monthly benchmark/factor data and report inference separately.
- Verify continuous-futures construction and price adjustments before interpreting the source returns economically.

## Reproduce
From the project directory, run `python3 strategy_backtest.py` with numpy,
pandas and matplotlib installed. Tables, figures and methodology are written
to `outputs/strategy/`; this dated report is regenerated from the results.

## Future weekly updates
Create a new dated report for each week using [the weekly template](weekly_update_template.md).
Keep previous dated reports and describe each change, its evidence and remaining limitations.
"""
    (report_dir / "group_update_2026-10-06.md").write_text(text, encoding="utf-8")


def main() -> None:
    returns = read_returns()
    asset_map = read_asset_map()

    results = build_strategy_set(returns)
    tsmom, static = results

    summary = summarize_alpha(tsmom, static)
    summary.to_csv(OUT_DIR / "tsmom_static_comparison_summary.csv", index=False, float_format="%.10g")

    return_table = pd.DataFrame({result["name"]: result["returns"] for result in results})
    return_table["alpha_tsmom_minus_static"] = tsmom["returns"] - static["returns"]
    return_table.to_csv(OUT_DIR / "tsmom_static_monthly_returns.csv", float_format="%.10g")

    asset_class_corr = correlation_by_asset_class(tsmom, static, asset_map)
    asset_class_corr.to_csv(OUT_DIR / "correlation_alpha_by_asset_class.csv", index=False, float_format="%.10g")

    instrument_corr = correlation_by_instrument(tsmom, static, asset_map)
    instrument_corr.to_csv(OUT_DIR / "correlation_alpha_by_instrument.csv", index=False, float_format="%.10g")

    portfolio_corr = portfolio_correlations(tsmom, static)
    portfolio_corr.to_csv(OUT_DIR / "correlation_alpha_by_portfolio.csv", index=False, float_format="%.10g")

    plot_cumulative_returns(results)
    plot_cumulative_alpha(tsmom, static)
    plot_asset_class_alpha(asset_class_corr)
    write_methodology_note()
    write_group_report(summary, portfolio_corr, asset_class_corr)

    print(f"Wrote strategy outputs to {OUT_DIR}")
    if plt is None:
        print("matplotlib is not installed, so plot files were skipped.")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
