"""Generate asset-class statistics, benchmark comparisons, and factor analysis.

Baseline and static-benchmark returns come from the standardized item 3 outputs.
Saved adjusted-strategy results supply the separate enhancement experiments.
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

from baseline_output_loader import load_baseline_outputs
from strategy_backtest_adj import (
    STATIC_NAME,
    TSMOM_NAME,
    build_experiments,
    read_asset_map,
    read_returns,
)


TRADING_MONTHS = 12
ROLLING_CORRELATION_MONTHS = 36
ROLLING_FACTOR_MONTHS = 60
ROLLING_BENCHMARK_MONTHS = 36
FACTOR_COLUMNS = ("Mkt-RF", "SMB", "HML", "Mom", "RMW", "CMA")
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
    returns: pd.DataFrame,
    asset_map: pd.DataFrame,
    standardized_baseline: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    """Load experiments and replace shared series with standardized item 3 data."""
    if SAVED_STRATEGY_RETURNS.exists():
        saved = pd.read_csv(SAVED_STRATEGY_RETURNS, index_col=0, parse_dates=True)
        required = {TSMOM_NAME, STATIC_NAME}
        if required.issubset(saved.columns):
            columns = [name for name in STRATEGY_ORDER if name in saved.columns]
            combined = saved[columns].sort_index()
            source = str(SAVED_STRATEGY_RETURNS)
        else:
            combined = pd.DataFrame()
            source = ""
    else:
        combined = pd.DataFrame()
        source = ""

    if combined.empty:
        experiments = build_experiments(returns, asset_map)
        combined = pd.DataFrame(
            {result["name"]: result["returns"] for result in experiments}
        )
        source = "rebuilt experiments from strategy_backtest_adj.py"

    for name in (TSMOM_NAME, STATIC_NAME):
        if name in combined:
            shared = pd.concat(
                [
                    combined[name].rename("existing"),
                    standardized_baseline[name].rename("item3"),
                ],
                axis=1,
            ).dropna()
            error = (shared["existing"] - shared["item3"]).abs().max()
            if error > 1e-8:
                raise AssertionError(
                    f"{name} differs from the standardized item 3 series by {error:.3g}."
                )
        combined[name] = standardized_baseline[name].reindex(combined.index)

    return combined, f"{source}; baseline/static from item 3"


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
    columns = ["SG Trend", *FACTOR_COLUMNS, "RF"]
    return lecture[columns].apply(pd.to_numeric, errors="coerce")


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


def single_factor_regressions(
    aligned: pd.DataFrame, return_column: str, strategy_label: str
) -> pd.DataFrame:
    """Run one excess-return regression per factor with HAC(3) inference."""
    dependent = aligned[return_column] - aligned["RF"]
    rows = []
    for factor in FACTOR_COLUMNS:
        data = pd.concat(
            [dependent.rename("excess_return"), aligned[factor].rename("factor")],
            axis=1,
        ).dropna()
        fit = sm.OLS(
            data["excess_return"], sm.add_constant(data[["factor"]])
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        alpha_interval = fit.conf_int().loc["const"] * TRADING_MONTHS
        rows.append(
            {
                "strategy": strategy_label,
                "factor": factor,
                "start": str(data.index.min()),
                "end": str(data.index.max()),
                "months": len(data),
                "correlation": data["excess_return"].corr(data["factor"]),
                "beta": fit.params["factor"],
                "beta_hac_t": fit.tvalues["factor"],
                "beta_pvalue": fit.pvalues["factor"],
                "alpha_annual_arithmetic": fit.params["const"] * TRADING_MONTHS,
                "alpha_hac_t": fit.tvalues["const"],
                "alpha_pvalue": fit.pvalues["const"],
                "alpha_ci_lower": alpha_interval.iloc[0],
                "alpha_ci_upper": alpha_interval.iloc[1],
                "r_squared": fit.rsquared,
            }
        )
    return pd.DataFrame(rows)


def joint_factor_regression(
    aligned: pd.DataFrame, return_column: str, strategy_label: str
) -> pd.DataFrame:
    """Run the joint six-factor excess-return model with HAC(3) inference."""
    dependent = (aligned[return_column] - aligned["RF"]).rename("excess_return")
    data = pd.concat([dependent, aligned[list(FACTOR_COLUMNS)]], axis=1).dropna()
    fit = sm.OLS(
        data["excess_return"], sm.add_constant(data[list(FACTOR_COLUMNS)])
    ).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    factor_component = data[list(FACTOR_COLUMNS)].dot(
        fit.params[list(FACTOR_COLUMNS)]
    )
    residual = fit.resid
    alpha_interval = fit.conf_int().loc["const"] * TRADING_MONTHS
    row = {
        "strategy": strategy_label,
        "start": str(data.index.min()),
        "end": str(data.index.max()),
        "months": len(data),
        "alpha_annual_arithmetic": fit.params["const"] * TRADING_MONTHS,
        "alpha_hac_t": fit.tvalues["const"],
        "alpha_pvalue": fit.pvalues["const"],
        "alpha_ci_lower": alpha_interval.iloc[0],
        "alpha_ci_upper": alpha_interval.iloc[1],
        "systematic_annual_volatility": factor_component.std()
        * np.sqrt(TRADING_MONTHS),
        "residual_annual_volatility": residual.std() * np.sqrt(TRADING_MONTHS),
        "r_squared": fit.rsquared,
    }
    for factor in FACTOR_COLUMNS:
        safe_name = factor.lower().replace("-", "_")
        row[f"beta_{safe_name}"] = fit.params[factor]
        row[f"beta_{safe_name}_hac_t"] = fit.tvalues[factor]
        row[f"beta_{safe_name}_pvalue"] = fit.pvalues[factor]
    return pd.DataFrame([row])


def factor_comparison_table(single_factor: pd.DataFrame) -> pd.DataFrame:
    """Create a presentation table similar to the course factor example."""
    metric_labels = {
        "correlation": "Correlation",
        "beta": "Beta",
        "alpha_annual_arithmetic": "Annualized alpha",
        "alpha_hac_t": "Alpha HAC t-stat",
        "r_squared": "R-squared",
    }
    rows = []
    for strategy in single_factor["strategy"].unique():
        subset = single_factor[single_factor["strategy"] == strategy].set_index(
            "factor"
        )
        for metric, label in metric_labels.items():
            row = {"strategy": strategy, "metric": label}
            row.update(subset[metric].reindex(FACTOR_COLUMNS).to_dict())
            rows.append(row)
    return pd.DataFrame(rows)


def rolling_joint_factor_betas(aligned: pd.DataFrame) -> pd.DataFrame:
    """Estimate trailing 60-month joint-model betas for the baseline and SG Trend."""
    rows = []
    factor_data = aligned[list(FACTOR_COLUMNS)]
    for return_column, strategy_label in (("TSMOM", "Baseline"), ("SG Trend", "SG Trend")):
        dependent = aligned[return_column] - aligned["RF"]
        combined = pd.concat(
            [dependent.rename("excess_return"), factor_data], axis=1
        ).dropna()
        for end_position in range(ROLLING_FACTOR_MONTHS - 1, len(combined)):
            window = combined.iloc[
                end_position - ROLLING_FACTOR_MONTHS + 1 : end_position + 1
            ]
            design = sm.add_constant(window[list(FACTOR_COLUMNS)])
            fit = sm.OLS(window["excess_return"], design).fit()
            row = {
                "Date": str(window.index[-1]),
                "strategy": strategy_label,
                "window_months": ROLLING_FACTOR_MONTHS,
                "alpha_annual_arithmetic": fit.params["const"] * TRADING_MONTHS,
                "r_squared": fit.rsquared,
            }
            for factor in FACTOR_COLUMNS:
                row[f"beta_{factor.lower().replace('-', '_')}"] = fit.params[factor]
            rows.append(row)
    return pd.DataFrame(rows)


def plot_factor_betas(single_factor: pd.DataFrame) -> None:
    """Compare single-factor betas for the baseline and SG Trend."""
    pivot = single_factor.pivot(index="factor", columns="strategy", values="beta")
    pivot = pivot.reindex(FACTOR_COLUMNS)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    pivot.plot(kind="bar", ax=ax, color=["#1f4e79", "#e07b00"])
    ax.axhline(0.0, color="#666666", linewidth=0.8)
    ax.set_title("Single-factor betas: adjusted baseline and SG Trend")
    ax.set_xlabel("Factor")
    ax.set_ylabel("Beta")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "factor_beta_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_factor_alphas(single_factor: pd.DataFrame) -> None:
    """Compare annualized intercepts from the single-factor regressions."""
    pivot = single_factor.pivot(
        index="factor", columns="strategy", values="alpha_annual_arithmetic"
    ).reindex(FACTOR_COLUMNS)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    pivot.plot(kind="bar", ax=ax, color=["#1f4e79", "#e07b00"])
    ax.axhline(0.0, color="#666666", linewidth=0.8)
    ax.set_title("Annualized alpha from separate single-factor regressions")
    ax.set_xlabel("Factor")
    ax.set_ylabel("Annualized arithmetic alpha")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "factor_alpha_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


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


def benchmark_pair_outputs(
    baseline: pd.Series, benchmark: pd.Series, benchmark_name: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return raw/vol-matched summaries, monthly series, and rolling raw statistics."""
    pair = pd.concat(
        [baseline.rename("Baseline"), benchmark.rename(benchmark_name)], axis=1
    ).dropna()
    target_vol = pair["Baseline"].std() * np.sqrt(TRADING_MONTHS)
    benchmark_vol = pair[benchmark_name].std() * np.sqrt(TRADING_MONTHS)
    scale = target_vol / benchmark_vol if benchmark_vol > 0 else np.nan
    matched = pair.copy()
    matched[benchmark_name] = matched[benchmark_name] * scale

    rows = []
    for presentation, frame, scales in (
        ("raw", pair, {"Baseline": 1.0, benchmark_name: 1.0}),
        (
            "volatility_matched_to_baseline",
            matched,
            {"Baseline": 1.0, benchmark_name: scale},
        ),
    ):
        for series_name in frame:
            row = {
                "benchmark_comparison": benchmark_name,
                "presentation": presentation,
                "series": series_name,
                "scale_multiplier": scales[series_name],
                "start": str(frame.index.min()),
                "end": str(frame.index.max()),
                "months": len(frame),
            }
            row.update(annualized_statistics(frame[series_name]))
            rows.append(row)

    monthly = pd.concat(
        {
            f"{benchmark_name}_raw": pair,
            f"{benchmark_name}_volatility_matched": matched,
        },
        axis=1,
    )

    rolling_rows = []
    for series_name in pair:
        series = pair[series_name]
        rolling_mean = series.rolling(ROLLING_BENCHMARK_MONTHS).mean() * TRADING_MONTHS
        rolling_vol = series.rolling(ROLLING_BENCHMARK_MONTHS).std() * np.sqrt(
            TRADING_MONTHS
        )
        rolling_sharpe = rolling_mean / rolling_vol
        rolling_rows.append(
            pd.DataFrame(
                {
                    "benchmark_comparison": benchmark_name,
                    "series": series_name,
                    "rolling_annualized_return": rolling_mean,
                    "rolling_annualized_volatility": rolling_vol,
                    "rolling_sharpe_0rf": rolling_sharpe,
                }
            )
        )
    rolling = pd.concat(rolling_rows).reset_index().rename(columns={"index": "Date"})
    return pd.DataFrame(rows), monthly, rolling


def benchmark_analysis(
    strategy_returns: pd.DataFrame, aligned: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare the baseline with Static and SG Trend in raw and matched form."""
    static_summary, static_monthly, static_rolling = benchmark_pair_outputs(
        strategy_returns[TSMOM_NAME], strategy_returns[STATIC_NAME], "Static benchmark"
    )
    sg_summary, sg_monthly, sg_rolling = benchmark_pair_outputs(
        aligned["TSMOM"], aligned["SG Trend"], "SG Trend"
    )
    return (
        pd.concat([static_summary, sg_summary], ignore_index=True),
        pd.concat([static_monthly, sg_monthly], axis=1),
        pd.concat([static_rolling, sg_rolling], ignore_index=True),
    )


def plot_benchmark_raw_and_matched(monthly: pd.DataFrame) -> None:
    """Plot cumulative raw and volatility-matched benchmark comparisons."""
    groups = ["Static benchmark", "SG Trend"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for row, benchmark in enumerate(groups):
        for column, presentation in enumerate(("raw", "volatility_matched")):
            frame = monthly[f"{benchmark}_{presentation}"].dropna()
            wealth = (1.0 + frame).cumprod()
            wealth.plot(ax=axes[row, column], logy=True)
            axes[row, column].set_title(
                f"{benchmark}: {'raw returns' if presentation == 'raw' else 'benchmark matched to baseline volatility'}"
            )
            axes[row, column].set_ylabel("Growth of 1 (log scale)")
            axes[row, column].grid(alpha=0.25)
            axes[row, column].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "benchmark_raw_vs_volatility_matched.png", dpi=180)
    plt.close(fig)


def plot_benchmark_rolling_statistics(rolling: pd.DataFrame) -> None:
    metrics = [
        ("rolling_annualized_return", "Rolling annualized return"),
        ("rolling_annualized_volatility", "Rolling annualized volatility"),
        ("rolling_sharpe_0rf", "Rolling Sharpe ratio"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=False)
    for row, benchmark in enumerate(("Static benchmark", "SG Trend")):
        subset = rolling[rolling["benchmark_comparison"] == benchmark]
        for column, (metric, title) in enumerate(metrics):
            pivot = subset.pivot(index="Date", columns="series", values=metric)
            pivot.plot(ax=axes[row, column])
            axes[row, column].set_title(f"{benchmark}: {title.lower()}")
            axes[row, column].grid(alpha=0.25)
            axes[row, column].legend(frameon=False, fontsize=8)
            if metric != "rolling_sharpe_0rf":
                axes[row, column].yaxis.set_major_formatter(
                    matplotlib.ticker.PercentFormatter(1.0)
                )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "benchmark_rolling_statistics.png", dpi=180)
    plt.close(fig)


def write_benchmark_methodology() -> None:
    text = """# Benchmark comparison methodology

- The adjusted TSMOM baseline is compared with the always-long static futures benchmark over their common 1976–2014 sample.
- The adjusted baseline is compared with SG Trend over the available common January 2000–December 2014 sample.
- Raw returns are the primary historical series. Volatility-matched results are also reported by scaling each benchmark to the baseline's realized volatility over the relevant common sample.
- Volatility matching uses full-sample realized volatility and is descriptive rather than a tradable procedure.
- Rolling return, volatility, and Sharpe ratio use a 36-month window. Sharpe ratios use a zero risk-free rate for consistency with the strategy summaries.
- Factor regressions use monthly excess returns, six equity factors, and Newey–West HAC standard errors with three lags.
- SG Trend may differ from this replication in instruments, fees, implementation, volatility target, and index methodology. The equity factors are not a complete risk model for a diversified futures portfolio.
"""
    (OUT_DIR / "benchmark_methodology.md").write_text(text, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    returns = read_returns()
    asset_map = read_asset_map()
    baseline = load_baseline_outputs()
    strategy_returns, strategy_source = load_adjusted_strategy_returns(
        returns, asset_map, baseline["monthly_returns"]
    )

    instrument_summary = instrument_statistics(returns, asset_map)
    class_summary, class_monthly = asset_class_statistics(returns, asset_map)
    overall_summary = overall_strategy_statistics(strategy_returns)
    aligned = align_with_sg_trend(strategy_returns[TSMOM_NAME])
    comparison = sg_trend_comparison(aligned)
    regression = sg_trend_regressions(aligned)
    baseline_single_factor = single_factor_regressions(
        aligned, "TSMOM", "Baseline"
    )
    sg_trend_single_factor = single_factor_regressions(
        aligned, "SG Trend", "SG Trend"
    )
    combined_single_factor = pd.concat(
        [baseline_single_factor, sg_trend_single_factor], ignore_index=True
    )
    baseline_joint_factor = joint_factor_regression(
        aligned, "TSMOM", "Baseline"
    )
    sg_trend_joint_factor = joint_factor_regression(
        aligned, "SG Trend", "SG Trend"
    )
    factor_table = factor_comparison_table(combined_single_factor)
    rolling_betas = rolling_joint_factor_betas(aligned)
    benchmark_summary, benchmark_monthly, benchmark_rolling = benchmark_analysis(
        strategy_returns, aligned
    )

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
    baseline_single_factor.to_csv(
        OUT_DIR / "baseline_single_factor_regressions.csv",
        index=False,
        float_format="%.8g",
    )
    sg_trend_single_factor.to_csv(
        OUT_DIR / "sg_trend_single_factor_regressions.csv",
        index=False,
        float_format="%.8g",
    )
    combined_single_factor.to_csv(
        OUT_DIR / "baseline_sg_factor_comparison.csv",
        index=False,
        float_format="%.8g",
    )
    baseline_joint_factor.to_csv(
        OUT_DIR / "baseline_joint_factor_regression.csv",
        index=False,
        float_format="%.8g",
    )
    sg_trend_joint_factor.to_csv(
        OUT_DIR / "sg_trend_joint_factor_regression.csv",
        index=False,
        float_format="%.8g",
    )
    factor_table.to_csv(
        OUT_DIR / "factor_comparison_table.csv", index=False, float_format="%.8g"
    )
    rolling_betas.to_csv(
        OUT_DIR / "rolling_factor_betas.csv", index=False, float_format="%.8g"
    )
    benchmark_summary.to_csv(
        OUT_DIR / "benchmark_raw_volatility_matched_summary.csv",
        index=False,
        float_format="%.8g",
    )
    benchmark_monthly.to_csv(
        OUT_DIR / "benchmark_raw_volatility_matched_monthly_returns.csv",
        index_label="Date",
        float_format="%.8g",
    )
    benchmark_rolling.to_csv(
        OUT_DIR / "benchmark_rolling_statistics.csv",
        index=False,
        float_format="%.8g",
    )
    plot_cumulative_comparison(aligned)
    plot_rolling_correlation(aligned)
    plot_overall_cumulative_returns(strategy_returns)
    plot_overall_sharpe_ratios(overall_summary)
    plot_factor_betas(combined_single_factor)
    plot_factor_alphas(combined_single_factor)
    plot_benchmark_raw_and_matched(benchmark_monthly)
    plot_benchmark_rolling_statistics(benchmark_rolling)
    write_benchmark_methodology()

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
    print("\nSingle-factor comparison:")
    print(factor_table.to_string(index=False))
    print("\nJoint six-factor regressions:")
    print(
        pd.concat([baseline_joint_factor, sg_trend_joint_factor], ignore_index=True)
        .to_string(index=False)
    )
    print("\nRaw and volatility-matched benchmark comparison:")
    print(benchmark_summary.to_string(index=False))


if __name__ == "__main__":
    main()
