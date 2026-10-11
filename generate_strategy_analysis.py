"""Generate asset-class statistics and an SG Trend comparison.

The script uses the adjusted TSMOM baseline in ``strategy_backtest_adj.py``.
It loads saved adjusted-strategy returns from
``outputs/strategy_backtest_adj_output/monthly_returns.csv``
when available. On a clean checkout, it rebuilds the baseline from the same source
functions so the analysis can still be reproduced.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from strategy_backtest_adj import (
    STATIC_NAME,
    TSMOM_NAME,
    build_baseline,
    build_experiments,
    read_asset_map,
    read_returns,
)


TRADING_MONTHS = 12
ROLLING_CORRELATION_MONTHS = 36
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "strategy_analysis_output"
SAVED_STRATEGY_RETURNS = (
    ROOT / "outputs" / "strategy_backtest_adj_output" / "monthly_returns.csv"
)
LECTURE_DATA = ROOT / "Lecture3_livedata.xlsx"

STRATEGY_ORDER = [
    TSMOM_NAME,
    "E1_EWMA_Vol",
    "E2_AssetClass_Budget",
    "E3_Multi_Lookback",
    "E4_Combined",
    STATIC_NAME,
]
STRATEGY_LABELS = {
    TSMOM_NAME: "Baseline",
    "E1_EWMA_Vol": "E1 EWMA vol",
    "E2_AssetClass_Budget": "E2 class budget",
    "E3_Multi_Lookback": "E3 multi-lookback",
    "E4_Combined": "E4 combined",
    STATIC_NAME: "Static benchmark",
}


def annualized_statistics(returns: pd.Series) -> dict[str, float]:
    """Calculate consistent monthly-return statistics using a zero risk-free rate."""
    clean = returns.dropna()
    annual_mean = clean.mean() * TRADING_MONTHS
    annual_vol = clean.std() * np.sqrt(TRADING_MONTHS)
    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1.0) - 1.0
    return {
        "annual_mean_return": annual_mean,
        "cagr": (1.0 + clean).prod() ** (TRADING_MONTHS / len(clean)) - 1.0,
        "annual_volatility": annual_vol,
        "sharpe_0rf": annual_mean / annual_vol if annual_vol > 0 else np.nan,
        "max_drawdown": drawdown.min(),
        "skew": clean.skew(),
        "kurtosis": clean.kurt(),
        "minimum_monthly_return": clean.min(),
        "maximum_monthly_return": clean.max(),
        "lag1_autocorrelation": clean.autocorr(1),
    }


def load_adjusted_strategy_returns(
    returns: pd.DataFrame, asset_map: pd.DataFrame
) -> tuple[pd.DataFrame, str]:
    """Load saved adjusted returns, rebuilding them if the saved file is absent."""
    if SAVED_STRATEGY_RETURNS.exists():
        saved = pd.read_csv(SAVED_STRATEGY_RETURNS, index_col=0, parse_dates=True)
        required = {TSMOM_NAME, STATIC_NAME}
        if required.issubset(saved.columns):
            columns = [name for name in STRATEGY_ORDER if name in saved.columns]
            return saved[columns].sort_index(), str(SAVED_STRATEGY_RETURNS)

    tsmom, static = build_baseline(returns, asset_map)
    experiments = build_experiments(returns, asset_map)
    results = [tsmom, *experiments, static]
    rebuilt = pd.DataFrame({result["name"]: result["returns"] for result in results})
    return rebuilt, "rebuilt from strategy_backtest_adj.py"


def overall_strategy_statistics(strategy_returns: pd.DataFrame) -> pd.DataFrame:
    """Summarize all available adjusted strategies over one common sample."""
    available = [name for name in STRATEGY_ORDER if name in strategy_returns.columns]
    common = strategy_returns[available].dropna()
    rows = []
    for name in available:
        row = {
            "strategy": name,
            "label": STRATEGY_LABELS[name],
            "start": common.index.min().date(),
            "end": common.index.max().date(),
            "months": len(common),
        }
        row.update(annualized_statistics(common[name]))
        rows.append(row)
    return pd.DataFrame(rows)


def plot_overall_cumulative_returns(strategy_returns: pd.DataFrame) -> None:
    """Plot uncompensated, compounded performance over the common backtest period."""
    available = [name for name in STRATEGY_ORDER if name in strategy_returns.columns]
    common = strategy_returns[available].dropna()
    wealth = (1.0 + common).cumprod()

    fig, ax = plt.subplots(figsize=(12, 7))
    for name in available:
        linewidth = 2.3 if name == TSMOM_NAME else 1.6
        linestyle = "--" if name == STATIC_NAME else "-"
        ax.plot(
            wealth.index,
            wealth[name],
            label=STRATEGY_LABELS[name],
            linewidth=linewidth,
            linestyle=linestyle,
        )
    ax.set_yscale("log")
    ax.set_title("Unscaled strategy performance over the common backtest period")
    ax.set_ylabel("Growth of 1 (compounded, log scale)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(
        OUT_DIR / "overall_cumulative_returns.png", dpi=180, bbox_inches="tight"
    )
    plt.close(fig)


def plot_overall_sharpe_ratios(summary: pd.DataFrame) -> None:
    """Compare zero-risk-free-rate Sharpe ratios on the common sample."""
    colors = [
        "#1f4e79" if name == TSMOM_NAME else "#9a9a9a" if name == STATIC_NAME else "#e07b00"
        for name in summary["strategy"]
    ]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(summary["label"], summary["sharpe_0rf"], color=colors)
    for bar, value in zip(bars, summary["sharpe_0rf"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.02,
            f"{value:.2f}",
            ha="center",
            va="bottom",
        )
    ax.set_title("Annualized Sharpe ratios over the common backtest period")
    ax.set_ylabel("Annual mean return / annual volatility (RF = 0)")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        OUT_DIR / "overall_sharpe_ratios.png", dpi=180, bbox_inches="tight"
    )
    plt.close(fig)


def instrument_statistics(
    returns: pd.DataFrame, asset_map: pd.DataFrame
) -> pd.DataFrame:
    metadata = asset_map.set_index("ID")
    rows = []
    for instrument in returns.columns:
        clean = returns[instrument].dropna()
        row = {
            "ID": instrument,
            "Name": metadata.at[instrument, "Name"] if instrument in metadata.index else np.nan,
            "AssetClass": metadata.at[instrument, "AssetClass"] if instrument in metadata.index else np.nan,
            "Ccy": metadata.at[instrument, "Ccy"] if instrument in metadata.index else np.nan,
            "first_return": clean.index.min().date(),
            "last_return": clean.index.max().date(),
            "observations": len(clean),
        }
        row.update(annualized_statistics(clean))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["AssetClass", "ID"])


def asset_class_statistics(
    returns: pd.DataFrame, asset_map: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize equal-weighted asset-class return series and their constituents."""
    class_lookup = asset_map.set_index("ID")["AssetClass"]
    class_returns = {}
    rows = []

    for asset_class in sorted(asset_map["AssetClass"].dropna().unique()):
        instruments = [
            col for col in returns.columns if class_lookup.get(col) == asset_class
        ]
        subset = returns[instruments]
        equal_weighted = subset.mean(axis=1, skipna=True).dropna()
        class_returns[asset_class] = equal_weighted

        correlation = subset.corr(min_periods=24)
        upper_triangle = correlation.where(
            np.triu(np.ones(correlation.shape), k=1).astype(bool)
        )
        pairwise = upper_triangle.stack()

        row = {
            "asset_class": asset_class,
            "instruments": len(instruments),
            "instrument_month_observations": int(subset.count().sum()),
            "first_return": equal_weighted.index.min().date(),
            "last_return": equal_weighted.index.max().date(),
            "months": len(equal_weighted),
            "average_pairwise_correlation": pairwise.mean(),
            "average_instrument_lag1_autocorrelation": subset.apply(
                lambda series: series.dropna().autocorr(1)
            ).mean(),
        }
        row.update(annualized_statistics(equal_weighted))
        rows.append(row)

    monthly = pd.DataFrame(class_returns).sort_index()
    return pd.DataFrame(rows), monthly


def load_lecture_data() -> pd.DataFrame:
    lecture = pd.read_excel(LECTURE_DATA)
    lecture["Date"] = pd.to_datetime(lecture["Date"], errors="coerce")
    lecture = lecture.dropna(subset=["Date"]).set_index("Date").sort_index()
    return lecture[["SG Trend", "RF"]].apply(pd.to_numeric, errors="coerce")


def align_with_sg_trend(strategy_returns: pd.Series) -> pd.DataFrame:
    strategy = strategy_returns.rename("TSMOM").copy()
    strategy.index = pd.to_datetime(strategy.index).to_period("M")

    lecture = load_lecture_data()
    lecture.index = lecture.index.to_period("M")
    aligned = pd.concat([strategy, lecture], axis=1, join="inner").dropna()
    if aligned.empty:
        raise ValueError("No overlapping observations were found for TSMOM and SG Trend.")
    return aligned


def sg_trend_comparison(aligned: pd.DataFrame) -> pd.DataFrame:
    tsmom = annualized_statistics(aligned["TSMOM"])
    sg_trend = annualized_statistics(aligned["SG Trend"])
    difference = aligned["TSMOM"] - aligned["SG Trend"]
    tracking_error = difference.std() * np.sqrt(TRADING_MONTHS)

    row = {
        "start": str(aligned.index.min()),
        "end": str(aligned.index.max()),
        "months": len(aligned),
        "tsmom_annual_mean_return": tsmom["annual_mean_return"],
        "tsmom_cagr": tsmom["cagr"],
        "tsmom_annual_volatility": tsmom["annual_volatility"],
        "tsmom_sharpe_0rf": tsmom["sharpe_0rf"],
        "tsmom_max_drawdown": tsmom["max_drawdown"],
        "sg_trend_annual_mean_return": sg_trend["annual_mean_return"],
        "sg_trend_cagr": sg_trend["cagr"],
        "sg_trend_annual_volatility": sg_trend["annual_volatility"],
        "sg_trend_sharpe_0rf": sg_trend["sharpe_0rf"],
        "sg_trend_max_drawdown": sg_trend["max_drawdown"],
        "correlation": aligned["TSMOM"].corr(aligned["SG Trend"]),
        "annual_mean_difference": difference.mean() * TRADING_MONTHS,
        "tracking_error": tracking_error,
        "information_ratio": (
            difference.mean() * TRADING_MONTHS / tracking_error
            if tracking_error > 0
            else np.nan
        ),
    }
    return pd.DataFrame([row])


def hac_regression(
    dependent: pd.Series, benchmark: pd.Series, specification: str
) -> dict[str, float | int | str]:
    data = pd.concat(
        [dependent.rename("dependent"), benchmark.rename("benchmark")], axis=1
    ).dropna()
    fit = sm.OLS(data["dependent"], sm.add_constant(data[["benchmark"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3}
    )
    confidence_interval = fit.conf_int().loc["const"] * TRADING_MONTHS
    return {
        "specification": specification,
        "start": str(data.index.min()),
        "end": str(data.index.max()),
        "months": len(data),
        "alpha_annual_arithmetic": fit.params["const"] * TRADING_MONTHS,
        "alpha_hac_t": fit.tvalues["const"],
        "alpha_pvalue": fit.pvalues["const"],
        "alpha_ci_lower": confidence_interval.iloc[0],
        "alpha_ci_upper": confidence_interval.iloc[1],
        "beta_sg_trend": fit.params["benchmark"],
        "beta_hac_t": fit.tvalues["benchmark"],
        "r_squared": fit.rsquared,
    }


def sg_trend_regressions(aligned: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            hac_regression(
                aligned["TSMOM"], aligned["SG Trend"], "raw_returns_HAC3"
            ),
            hac_regression(
                aligned["TSMOM"] - aligned["RF"],
                aligned["SG Trend"] - aligned["RF"],
                "excess_returns_HAC3",
            ),
        ]
    )


def plot_cumulative_comparison(aligned: pd.DataFrame) -> None:
    dates = aligned.index.to_timestamp("M")
    wealth = (1.0 + aligned[["TSMOM", "SG Trend"]]).cumprod()
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(dates, wealth["TSMOM"], label="Adjusted TSMOM baseline", linewidth=1.8)
    ax.plot(dates, wealth["SG Trend"], label="SG Trend", linewidth=1.8)
    ax.set_yscale("log")
    ax.set_title("Adjusted TSMOM baseline vs SG Trend")
    ax.set_ylabel("Growth of 1 (log scale)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sg_trend_cumulative.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_rolling_correlation(aligned: pd.DataFrame) -> None:
    rolling = aligned["TSMOM"].rolling(ROLLING_CORRELATION_MONTHS).corr(
        aligned["SG Trend"]
    )
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(rolling.index.to_timestamp("M"), rolling, linewidth=1.8)
    ax.axhline(0.0, color="#666666", linewidth=0.8)
    ax.set_ylim(-1.0, 1.0)
    ax.set_title(
        f"TSMOM and SG Trend rolling {ROLLING_CORRELATION_MONTHS}-month correlation"
    )
    ax.set_ylabel("Correlation")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(
        OUT_DIR / "sg_trend_rolling_correlation.png", dpi=180, bbox_inches="tight"
    )
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    returns = read_returns()
    asset_map = read_asset_map()
    strategy_returns, strategy_source = load_adjusted_strategy_returns(
        returns, asset_map
    )

    instrument_summary = instrument_statistics(returns, asset_map)
    class_summary, class_monthly = asset_class_statistics(returns, asset_map)
    overall_summary = overall_strategy_statistics(strategy_returns)
    aligned = align_with_sg_trend(strategy_returns[TSMOM_NAME])
    comparison = sg_trend_comparison(aligned)
    regression = sg_trend_regressions(aligned)

    instrument_summary.to_csv(
        OUT_DIR / "asset_class_instrument_summary.csv", index=False, float_format="%.8g"
    )
    class_summary.to_csv(
        OUT_DIR / "asset_class_summary.csv", index=False, float_format="%.8g"
    )
    class_monthly.to_csv(
        OUT_DIR / "asset_class_monthly_returns.csv", index_label="Date", float_format="%.8g"
    )
    overall_summary.to_csv(
        OUT_DIR / "overall_strategy_summary.csv", index=False, float_format="%.8g"
    )
    aligned.to_csv(
        OUT_DIR / "sg_trend_aligned_monthly_returns.csv",
        index_label="Date",
        float_format="%.8g",
    )
    comparison.to_csv(
        OUT_DIR / "sg_trend_comparison.csv", index=False, float_format="%.8g"
    )
    regression.to_csv(
        OUT_DIR / "sg_trend_regression.csv", index=False, float_format="%.8g"
    )
    plot_cumulative_comparison(aligned)
    plot_rolling_correlation(aligned)
    plot_overall_cumulative_returns(strategy_returns)
    plot_overall_sharpe_ratios(overall_summary)

    print(f"Wrote analysis outputs to {OUT_DIR}")
    print(f"Strategy return source: {strategy_source}")
    print("\nAsset-class summary:")
    print(class_summary.to_string(index=False))
    print("\nOverall strategy summary:")
    print(overall_summary.to_string(index=False))
    print("\nSG Trend comparison:")
    print(comparison.to_string(index=False))
    print("\nSG Trend regressions:")
    print(regression.to_string(index=False))


if __name__ == "__main__":
    main()
