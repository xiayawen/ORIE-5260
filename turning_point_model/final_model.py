"""Final five-strategy comparison for the turning-point enhancement."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from economic_trend import price_trend_weights
from turning_point_model import OUTPUT_ROOT
from turning_point_model.data_loader import build_baseline_inputs
from turning_point_model.evaluation import (
    exposure_frame,
    hac_mean_statistics,
    performance_metrics,
    slice_period,
)
from turning_point_model.macro_features import (
    economic_confirmation_features,
    four_of_five_opposition,
    macro_confirmed_binary_weights,
    validate_macro_directory,
)
from turning_point_model.regime_features import disagreement_from_signals
from turning_point_model.strategy_engine import (
    binary_reduction_weights,
    flat_cost_returns,
    simulate,
)


ALPHA = 0.50
COST_BPS = (0, 2, 10)
FINAL_DIR = OUTPUT_ROOT / "final_model"
SUMMARY_PATH = OUTPUT_ROOT / "TURNING_POINT_MODEL.md"
PERIODS = {
    "training_1980_1997": ("1980-01-01", "1997-12-31"),
    "validation_1998_2014": ("1998-01-01", "2014-12-31"),
    "holdout_testing_2015_2025": ("2015-01-01", None),
}
LABELS = {
    "adjusted_baseline": "Adjusted baseline",
    "vol_targeted_baseline": "Volatility-targeted baseline",
    "unfiltered_method1": "Vol-targeted + Method 1",
    "majority_vote_method1": "Method 1 + majority macro vote",
    "four_of_five_method1": "Method 1 + 4-of-5 macro vote",
}


def build_final_weights(
    adjusted: pd.DataFrame,
    vol_targeted: pd.DataFrame,
    disagreement: pd.DataFrame,
    majority_opposition: pd.DataFrame,
    strict_opposition: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Construct the five final comparison portfolios."""
    return {
        "adjusted_baseline": adjusted.fillna(0.0),
        "vol_targeted_baseline": vol_targeted.fillna(0.0),
        "unfiltered_method1": binary_reduction_weights(
            vol_targeted, disagreement, ALPHA
        ),
        "majority_vote_method1": macro_confirmed_binary_weights(
            vol_targeted, disagreement, majority_opposition, ALPHA
        ),
        "four_of_five_method1": macro_confirmed_binary_weights(
            vol_targeted, disagreement, strict_opposition, ALPHA
        ),
    }

def _evaluate(
    returns: pd.DataFrame,
    weights: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict]]:
    simulations = {name: simulate(returns, formed) for name, formed in weights.items()}
    rows = []
    monthly = {}
    for strategy, simulation in simulations.items():
        exposures = exposure_frame(simulation)
        for bps in COST_BPS:
            net = flat_cost_returns(simulation, bps)
            monthly[f"{strategy}|{bps}bps"] = net
            for period, (start, end) in PERIODS.items():
                subset = slice_period(net, start, end)
                if subset.dropna().empty:
                    continue
                rows.append(
                    {
                        "strategy": strategy,
                        "period": period,
                        "cost_bps": bps,
                        **performance_metrics(
                            subset,
                            simulation["turnover"],
                            exposures,
                            simulation["turnover"] * bps / 10_000.0,
                        ),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(monthly).rename_axis("Date"), simulations


def _hac_tests(monthly_10: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        ("adjusted_vs_vol_targeted", "adjusted_baseline", "vol_targeted_baseline"),
        ("unfiltered_vs_vol_targeted", "unfiltered_method1", "vol_targeted_baseline"),
        ("majority_vs_vol_targeted", "majority_vote_method1", "vol_targeted_baseline"),
        ("4of5_vs_vol_targeted", "four_of_five_method1", "vol_targeted_baseline"),
        ("4of5_vs_majority", "four_of_five_method1", "majority_vote_method1"),
    ]
    rows = []
    for period, (start, end) in PERIODS.items():
        for comparison, candidate, comparator in comparisons:
            paired = slice_period(monthly_10[[candidate, comparator]], start, end).dropna()
            if paired.empty:
                continue
            stats = hac_mean_statistics(paired[candidate] - paired[comparator])
            rows.append(
                {
                    "comparison": comparison,
                    "candidate": candidate,
                    "comparator": comparator,
                    "period": period,
                    "months": len(paired),
                    "annualized_incremental_return": stats["mean"] * 12.0,
                    "annualized_hac_se": stats["hac_se"] * 12.0,
                    "annualized_ci_low": stats["ci_low"] * 12.0,
                    "annualized_ci_high": stats["ci_high"] * 12.0,
                    "hac_t_stat": stats["t_stat"],
                }
            )
    return pd.DataFrame(rows)


def _coverage(
    weights: dict[str, pd.DataFrame],
    disagreement: pd.DataFrame,
    majority: pd.DataFrame,
    strict: pd.DataFrame,
) -> pd.DataFrame:
    active = weights["vol_targeted_baseline"].ne(0.0)
    disagreement = disagreement.reindex_like(active).fillna(False)
    gates = {
        "unfiltered_method1": pd.DataFrame(True, index=active.index, columns=active.columns),
        "majority_vote_method1": majority.reindex_like(active).fillna(False),
        "four_of_five_method1": strict.reindex_like(active).fillna(False),
    }
    realized_dates = (active.index.to_period("M") + 1).to_timestamp("M")
    rows = []
    for period, (start, end) in PERIODS.items():
        mask = realized_dates >= pd.Timestamp(start)
        if end is not None:
            mask &= realized_dates <= pd.Timestamp(end)
        local_turning = disagreement.loc[mask] & active.loc[mask]
        turning_count = int(local_turning.to_numpy().sum())
        for strategy, gate in gates.items():
            confirmed = int((local_turning & gate.loc[mask]).to_numpy().sum())
            rows.append(
                {
                    "period": period,
                    "strategy": strategy,
                    "method1_disagreements": turning_count,
                    "confirmed_reductions": confirmed,
                    "confirmation_rate": confirmed / turning_count if turning_count else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _period_background(axis: plt.Axes, end: pd.Timestamp) -> None:
    spans = [
        (pd.Timestamp("1980-01-01"), pd.Timestamp("1997-12-31"), "#e8f1fb", "Training\n1980–1997"),
        (pd.Timestamp("1998-01-01"), pd.Timestamp("2014-12-31"), "#f4efe5", "Validation\n1998–2014"),
        (pd.Timestamp("2015-01-01"), end, "#e9f4ea", "Holdout testing\n2015–2025"),
    ]
    for start, stop, color, _ in spans:
        axis.axvspan(start, stop, color=color, alpha=0.55, zorder=0)
    axis.axvline(pd.Timestamp("1998-01-01"), color="grey", linestyle="--", linewidth=1)
    axis.axvline(pd.Timestamp("2015-01-01"), color="grey", linestyle="--", linewidth=1)


def _write_figure(monthly_10: pd.DataFrame, out: Path) -> None:
    local = monthly_10.loc["1980":]
    wealth = (1.0 + local).cumprod()
    drawdown = wealth.div(wealth.cummax()).sub(1.0)
    colors = {
        "adjusted_baseline": "#7f7f7f",
        "vol_targeted_baseline": "#1f77b4",
        "unfiltered_method1": "#d62728",
        "majority_vote_method1": "#ff7f0e",
        "four_of_five_method1": "#2ca02c",
    }
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for axis in axes:
        _period_background(axis, local.index.max())
        axis.grid(alpha=0.2)
    for strategy in LABELS:
        width = 2.4 if strategy == "four_of_five_method1" else 1.6
        axes[0].plot(wealth.index, wealth[strategy], label=LABELS[strategy], color=colors[strategy], linewidth=width)
        axes[1].plot(drawdown.index, drawdown[strategy], color=colors[strategy], linewidth=width)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Cumulative wealth (log scale)")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[1].set_xlabel("Return month")
    period_labels = [
        (pd.Timestamp("1989-01-01"), "Training\n1980–1997"),
        (pd.Timestamp("2006-06-30"), "Validation\n1998–2014"),
        (pd.Timestamp("2020-01-01"), "Holdout testing\n2015–2025"),
    ]
    for x, label in period_labels:
        axes[0].text(x, 0.98, label, transform=axes[0].get_xaxis_transform(), ha="center", va="top", fontsize=10, fontweight="bold")
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Turning-point strategy comparison after 10 bps", y=0.995, fontsize=16)
    fig.legend(
        handles,
        legend_labels,
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.97),
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(out / "five_strategy_periods.png", dpi=180)
    plt.close(fig)


def _write_summary(
    performance: pd.DataFrame,
    hac: pd.DataFrame,
    coverage: pd.DataFrame,
    source: Path,
) -> None:
    selected = performance.loc[performance["cost_bps"].eq(10)]
    lines = [
        "# Turning-point model",
        "",
        "## Objective",
        "",
        "The turning-point model tests whether short-horizon momentum disagreement and macro confirmation can reduce losses around trend reversals without giving up too much return during temporary corrections.",
        "",
        "## Data and evaluation design",
        "",
        f"The experiment uses `{source.name}` and the same futures universe as the baseline project. Signals and weights are formed at month-end and executed in the following month. Growth and inflation indicators include a one-month publication lag. The macro files contain revised histories rather than real-time vintages.",
        "",
        "- **Training:** 1980–1997",
        "- **Validation:** 1998–2014",
        "- **Holdout testing:** 2015–2025",
        "",
        "No model choice uses the holdout period.",
        "",
        "## Methods",
        "",
        "1. **Adjusted baseline:** the course-style 12-month TSMOM benchmark.",
        "2. **Volatility-targeted baseline:** 12-month price trend, inverse trailing 12-month instrument volatility with a 1% floor, and trailing 36-month portfolio scaling toward 10% annual volatility.",
        "3. **Unfiltered Method 1:** reduce each volatility-targeted position by 50% whenever its 2-month and 12-month momentum directions disagree.",
        "4. **Majority macro vote:** apply the same reduction only when more than half of the available mapped macro themes oppose the baseline direction.",
        "5. **4-of-5 macro vote:** apply the reduction only when at least four macro themes oppose. This is the preferred tested specification because it gives the most consistent numerical improvement over the volatility-targeted baseline.",
        "",
        "All five strategies use a one-month execution lag and the same flat 10 bps turnover-cost assumption in the main comparison. Reduced portfolios are not re-targeted immediately after the exposure cut.",
        "",
        "## Five-strategy comparison",
        "",
        "![Five turning-point strategies across training, validation, and holdout testing](final_model/five_strategy_periods.png)",
        "",
        "### Performance after 10 bps",
        "",
        "| Period | Strategy | Annual mean | Volatility | Sharpe | Maximum drawdown | Turnover | Cost drag |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for period in PERIODS:
        for strategy in LABELS:
            row = selected.loc[
                selected["period"].eq(period) & selected["strategy"].eq(strategy)
            ].iloc[0]
            lines.append(
                f"| {period} | {LABELS[strategy]} | {row.annual_mean:.2%} | "
                f"{row.annual_volatility:.2%} | {row.sharpe_0rf:.3f} | "
                f"{row.max_drawdown:.2%} | {row.annual_turnover:.2f} | "
                f"{row.annual_cost_drag:.2%} |"
            )
    lines += [
        "",
        "### Incremental return tests after 10 bps",
        "",
        "| Period | Comparison | Annual increment | 95% HAC interval | HAC t |",
        "|---|---|---:|---:|---:|",
    ]
    for row in hac.itertuples():
        lines.append(
            f"| {row.period} | {row.comparison} | {row.annualized_incremental_return:+.2%} | "
            f"[{row.annualized_ci_low:+.2%}, {row.annualized_ci_high:+.2%}] | "
            f"{row.hac_t_stat:.2f} |"
        )
    validation = selected.loc[selected["period"].eq("validation_1998_2014")].set_index("strategy")
    holdout = selected.loc[selected["period"].eq("holdout_testing_2015_2025")].set_index("strategy")
    final_hac = hac.loc[hac["comparison"].eq("4of5_vs_vol_targeted")].set_index("period")
    lines += [
        "",
        "## Main findings",
        "",
        f"- Volatility targeting is the largest improvement in validation: Sharpe rises from {validation.at['adjusted_baseline', 'sharpe_0rf']:.3f} for the adjusted baseline to {validation.at['vol_targeted_baseline', 'sharpe_0rf']:.3f}.",
        f"- Unfiltered Method 1 lowers validation Sharpe to {validation.at['unfiltered_method1', 'sharpe_0rf']:.3f}, showing that fast–slow disagreement alone creates substantial opportunity cost.",
        f"- The 4-of-5 model reaches validation and holdout Sharpes of {validation.at['four_of_five_method1', 'sharpe_0rf']:.3f} and {holdout.at['four_of_five_method1', 'sharpe_0rf']:.3f}, compared with {validation.at['vol_targeted_baseline', 'sharpe_0rf']:.3f} and {holdout.at['vol_targeted_baseline', 'sharpe_0rf']:.3f} for volatility targeting alone.",
        f"- Its annual incremental return over the volatility-targeted baseline is {final_hac.at['validation_1998_2014', 'annualized_incremental_return']:+.2%} in validation and {final_hac.at['holdout_testing_2015_2025', 'annualized_incremental_return']:+.2%} in holdout testing. Both HAC confidence intervals include zero.",
        "- The stricter macro gate reduces false alarms relative to the ordinary majority vote, but the improvement is economically small and not statistically reliable against the volatility-targeted baseline.",
        "",
        "## Conclusion",
        "",
        "The 4-of-5 macro vote with a 50% reduction is the preferred tested turning-point specification. It should be presented as a modest robustness enhancement rather than a proven source of incremental return. The volatility-targeted price strategy remains the appropriate primary benchmark.",
        "",
        "## Output files",
        "",
        "- `final_model/strategy_performance.csv`",
        "- `final_model/monthly_returns_10bps.csv`",
        "- `final_model/hac_incremental_tests_10bps.csv`",
        "- `final_model/confirmation_coverage.csv`",
        "- `final_model/five_strategy_periods.png`",
        "",
        "Exploratory variants are stored locally under `sensitivity/` and excluded from Git.",
        "",
    ]
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_final_model(
    returns_path: str | Path | None = None,
    macro_dir: str | Path = "macro_data",
) -> dict[str, object]:
    """Run and save the final five-strategy comparison."""
    returns, asset_map, baseline, source = build_baseline_inputs(returns_path)
    macro_path = validate_macro_directory(macro_dir)
    disagreement = disagreement_from_signals(
        baseline["signal"], np.sign(returns.rolling(2, min_periods=2).sum())
    )
    features = economic_confirmation_features(
        returns, asset_map, baseline["signal"], macro_path
    )
    strict = four_of_five_opposition(features)
    weights = build_final_weights(
        baseline["weights"],
        price_trend_weights(returns),
        disagreement,
        features["macro_vote_opposes_baseline"],
        strict,
    )
    performance, monthly_all, simulations = _evaluate(returns, weights)
    monthly_10 = pd.DataFrame(
        {strategy: monthly_all[f"{strategy}|10bps"] for strategy in weights}
    )
    hac = _hac_tests(monthly_10)
    coverage = _coverage(
        weights,
        disagreement,
        features["macro_vote_opposes_baseline"],
        strict,
    )

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    performance.to_csv(FINAL_DIR / "strategy_performance.csv", index=False)
    monthly_all.to_csv(FINAL_DIR / "monthly_returns_all_costs.csv")
    monthly_10.to_csv(FINAL_DIR / "monthly_returns_10bps.csv")
    hac.to_csv(FINAL_DIR / "hac_incremental_tests_10bps.csv", index=False)
    coverage.to_csv(FINAL_DIR / "confirmation_coverage.csv", index=False)
    _write_figure(monthly_10, FINAL_DIR)
    _write_summary(performance, hac, coverage, source)
    (FINAL_DIR / "configuration.json").write_text(
        json.dumps(
            {
                "returns_input": str(source),
                "macro_directory": str(macro_path),
                "reduction": ALPHA,
                "cost_bps": list(COST_BPS),
                "periods": PERIODS,
                "preferred_specification": "four_of_five_method1",
                "post_reduction_retargeting": False,
                "holdout_used_for_selection": False,
                "strategies": list(weights),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "performance": performance,
        "monthly_returns_10bps": monthly_10,
        "hac_tests": hac,
        "coverage": coverage,
        "weights": weights,
        "simulations": simulations,
    }

__all__ = ["run_final_model"]
