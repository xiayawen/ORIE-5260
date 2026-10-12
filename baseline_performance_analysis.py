"""Consolidated performance evaluation of the adjusted TSMOM baseline.

This is item 3 of the baseline-analysis plan. It rebuilds the adjusted 12-month
baseline from ``strategy_backtest_adj.py``, verifies that weights formed at month t
earn month t+1 returns and use no later data, and reports cumulative and annualized
performance, drawdown depth and recovery time, rolling performance, turnover with
illustrative transaction costs, and gross/net/long/short exposure. The static
benchmark is reported alongside for reference. The strategy itself is not changed.

Transaction costs are charged per one-way absolute change in target weight, matching
``rolling_backtest.py``; they exclude position drift, contract rolls, spreads,
financing, and cash interest. Sharpe ratios use a zero risk-free rate, consistent
with the other strategy summaries.

Standardized baseline series (returns, instrument contributions, executed weights,
volatility estimates, exposures, turnover) are saved for downstream analyses.
"""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from baseline_risk_analysis import drawdown_table
from strategy_backtest_adj import (
    EVAL_START,
    STATIC_NAME,
    TSMOM_NAME,
    build_baseline,
    read_asset_map,
    read_returns,
)


TRADING_MONTHS = 12
COST_BPS = (0, 5, 10, 25)
ROLLING_WINDOWS = (12, 36, 60)
PRIMARY_ROLLING_WINDOW = 36
LOOKAHEAD_CHECK_DATES = ("1985-12-31", "1998-08-31", "2008-10-31")
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "baseline_performance_output"

BASELINE_COLOR = "#1f4e79"
STATIC_COLOR = "#9a9a9a"


# ---------------------------------------------------------------- checks


def timing_checks(returns: pd.DataFrame, asset_map: pd.DataFrame, tsmom: dict) -> pd.DataFrame:
    """Confirm the one-month execution lag and that weights at t ignore data after t."""
    rows = []
    lag_error = (tsmom["execution_weights"] - tsmom["weights"].shift(1).fillna(0.0)).abs().max().max()
    rows.append({"check": "execution_weights_equal_prior_month_weights", "max_abs_error": lag_error})

    rebuilt = (tsmom["execution_weights"] * returns.fillna(0.0)).sum(axis=1).loc[EVAL_START:]
    rows.append(
        {
            "check": "portfolio_return_equals_lagged_weights_times_returns",
            "max_abs_error": (rebuilt - tsmom["returns"]).abs().max(),
        }
    )

    for cutoff in LOOKAHEAD_CHECK_DATES:
        cutoff = pd.Timestamp(cutoff)
        date = returns.index[returns.index <= cutoff].max()
        truncated, _ = build_baseline(returns.loc[:date], asset_map)
        error = (truncated["weights"].loc[date] - tsmom["weights"].loc[date]).abs().max()
        rows.append(
            {
                "check": f"weights_at_{date.date()}_unchanged_when_later_data_removed",
                "max_abs_error": error,
            }
        )
    table = pd.DataFrame(rows)
    table["passed"] = table["max_abs_error"] < 1e-12
    return table


# ---------------------------------------------------------------- performance


def drawdown_events(returns: pd.Series) -> pd.DataFrame:
    _, events = drawdown_table(returns)
    if events.empty:
        return events
    positions = returns.index.get_indexer(events["peak_date"])
    last_position = len(returns) - 1
    events["recovered"] = events["recovery_date"].notna()
    events["months_trough_to_recovery"] = (
        events["months_peak_to_recovery"] - events["months_peak_to_trough"]
    )
    # Unrecovered episodes are counted as underwater through the end of the sample.
    events["months_underwater"] = events["months_peak_to_recovery"].fillna(
        pd.Series(last_position - positions, index=events.index)
    )
    return events


def performance_statistics(name: str, returns: pd.Series, turnover: pd.Series) -> dict:
    clean = returns.dropna()
    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    annual_mean = clean.mean() * TRADING_MONTHS
    annual_vol = clean.std() * np.sqrt(TRADING_MONTHS)
    cagr = wealth.iloc[-1] ** (TRADING_MONTHS / len(clean)) - 1.0
    events = drawdown_events(clean)
    worst = events.loc[events["maximum_drawdown"].idxmin()]
    return {
        "strategy": name,
        "start": clean.index.min().date(),
        "end": clean.index.max().date(),
        "months": len(clean),
        "cumulative_return": wealth.iloc[-1] - 1.0,
        "cumulative_arithmetic_return": clean.sum(),
        "cagr": cagr,
        "annual_mean_return": annual_mean,
        "annual_volatility": annual_vol,
        "sharpe_0rf": annual_mean / annual_vol,
        "max_drawdown": drawdown.min(),
        "calmar_ratio": cagr / abs(drawdown.min()),
        "max_drawdown_peak": worst["peak_date"].date(),
        "max_drawdown_trough": worst["trough_date"].date(),
        "max_drawdown_recovery": worst["recovery_date"].date() if worst["recovered"] else None,
        "max_drawdown_months_peak_to_trough": worst["months_peak_to_trough"],
        "max_drawdown_months_trough_to_recovery": worst["months_trough_to_recovery"],
        "max_drawdown_months_underwater": worst["months_underwater"],
        "longest_underwater_months": events["months_underwater"].max(),
        "share_of_months_underwater": (drawdown < 0).mean(),
        "drawdown_episodes": len(events),
        "hit_rate": (clean > 0).mean(),
        "best_month": clean.max(),
        "worst_month": clean.min(),
        "skew": clean.skew(),
        "kurtosis": clean.kurt(),
        "average_monthly_turnover": turnover.mean(),
        "annual_turnover": turnover.mean() * TRADING_MONTHS,
    }


def rolling_performance(results: dict[str, pd.Series]) -> pd.DataFrame:
    frames = []
    for name, returns in results.items():
        for window in ROLLING_WINDOWS:
            mean = returns.rolling(window).mean() * TRADING_MONTHS
            vol = returns.rolling(window).std() * np.sqrt(TRADING_MONTHS)
            frames.append(
                pd.DataFrame(
                    {
                        "strategy": name,
                        "window_months": window,
                        "annualized_return": mean,
                        "annualized_volatility": vol,
                        "sharpe_0rf": mean / vol,
                    }
                ).dropna()
            )
    return pd.concat(frames).rename_axis("Date").reset_index()


def net_of_costs(returns: pd.Series, turnover: pd.Series, bps: float) -> pd.Series:
    return returns - turnover.reindex(returns.index).fillna(0.0) * bps / 10000


def transaction_cost_sensitivity(results: list[dict]) -> pd.DataFrame:
    rows = []
    for result in results:
        gross, turnover = result["returns"], result["turnover"]
        # One-way cost at which the arithmetic mean return falls to zero.
        break_even = gross.mean() / turnover.mean() * 10000 if turnover.mean() > 0 else np.nan
        for bps in COST_BPS:
            net = net_of_costs(gross, turnover, bps)
            stats = performance_statistics(result["name"], net, turnover)
            rows.append(
                {
                    "strategy": result["name"],
                    "cost_bps": bps,
                    "cagr": stats["cagr"],
                    "annual_mean_return": stats["annual_mean_return"],
                    "annual_volatility": stats["annual_volatility"],
                    "sharpe_0rf": stats["sharpe_0rf"],
                    "max_drawdown": stats["max_drawdown"],
                    "annual_turnover": stats["annual_turnover"],
                    "annual_cost_drag": turnover.mean() * TRADING_MONTHS * bps / 10000,
                    "break_even_cost_bps": break_even,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- exposure and turnover


def exposure_table(weights: pd.DataFrame, asset_map: pd.DataFrame) -> pd.DataFrame:
    class_lookup = asset_map.set_index("ID")["AssetClass"]
    exposures = pd.DataFrame(index=weights.index)
    exposures["gross_exposure"] = weights.abs().sum(axis=1)
    exposures["net_exposure"] = weights.sum(axis=1)
    exposures["long_exposure"] = weights.clip(lower=0).sum(axis=1)
    exposures["short_exposure"] = weights.clip(upper=0).sum(axis=1)
    exposures["active_positions"] = weights.ne(0).sum(axis=1)
    exposures["long_positions"] = weights.gt(0).sum(axis=1)
    exposures["short_positions"] = weights.lt(0).sum(axis=1)
    classes = weights.columns.map(class_lookup)
    gross_by_class = weights.abs().T.groupby(classes).sum().T.add_prefix("gross_")
    net_by_class = weights.T.groupby(classes).sum().T.add_prefix("net_")
    return pd.concat([exposures, gross_by_class, net_by_class], axis=1)


def exposure_summary(exposures: pd.DataFrame) -> pd.DataFrame:
    return exposures.agg(["mean", "median", "min", "max", "std"]).T.rename_axis("measure").reset_index()


def turnover_table(tsmom: dict, static: dict) -> pd.DataFrame:
    execution = tsmom["execution_weights"].loc[EVAL_START:]
    previous = tsmom["execution_weights"].shift(1).loc[EVAL_START:]
    flips = (np.sign(execution) * np.sign(previous) < 0).sum(axis=1)
    return pd.DataFrame(
        {
            "tsmom_turnover": tsmom["turnover"],
            "static_turnover": static["turnover"],
            "tsmom_signal_flips": flips,
            "tsmom_positions_opened": (execution.ne(0) & previous.eq(0)).sum(axis=1),
            "tsmom_positions_closed": (execution.eq(0) & previous.ne(0)).sum(axis=1),
        }
    )


# ---------------------------------------------------------------- plots


def plot_cumulative(monthly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot((1.0 + monthly[TSMOM_NAME]).cumprod(), color=BASELINE_COLOR, linewidth=1.9, label="TSMOM baseline (gross)")
    ax.plot(
        (1.0 + monthly[f"{TSMOM_NAME}_net_10bps"]).cumprod(),
        color=BASELINE_COLOR,
        linewidth=1.3,
        linestyle="--",
        label="TSMOM baseline (net of 10 bps)",
    )
    ax.plot((1.0 + monthly[STATIC_NAME]).cumprod(), color=STATIC_COLOR, linewidth=1.6, label="Static benchmark (gross)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"${y:g}"))
    ax.set_title("Adjusted baseline: growth of $1, compounded (1976-2014)")
    ax.set_ylabel("Growth of $1 (log scale)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "baseline_cumulative_return.png", dpi=180)
    plt.close(fig)


def plot_rolling(rolling: pd.DataFrame) -> None:
    subset = rolling.loc[rolling["window_months"] == PRIMARY_ROLLING_WINDOW]
    metrics = [
        ("annualized_return", "Rolling annualized return", True),
        ("annualized_volatility", "Rolling annualized volatility", True),
        ("sharpe_0rf", "Rolling Sharpe ratio", False),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    for ax, (column, title, percent) in zip(axes, metrics):
        for name, color in ((TSMOM_NAME, BASELINE_COLOR), (STATIC_NAME, STATIC_COLOR)):
            series = subset.loc[subset["strategy"] == name].set_index("Date")[column]
            ax.plot(series, color=color, linewidth=1.5, label=name)
        ax.axhline(0, color="#666666", linewidth=0.8)
        ax.set_title(f"{title} ({PRIMARY_ROLLING_WINDOW}-month window)")
        if percent:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "baseline_rolling_performance.png", dpi=180)
    plt.close(fig)


def plot_drawdowns(monthly: pd.DataFrame, events: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    for name, color in ((TSMOM_NAME, BASELINE_COLOR), (STATIC_NAME, STATIC_COLOR)):
        wealth = (1.0 + monthly[name]).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        ax.plot(drawdown, color=color, linewidth=1.3, label=f"{name} (max {drawdown.min():.0%})")
    ax.fill_between(
        monthly.index,
        ((1.0 + monthly[TSMOM_NAME]).cumprod() / (1.0 + monthly[TSMOM_NAME]).cumprod().cummax() - 1.0),
        0,
        color=BASELINE_COLOR,
        alpha=0.15,
    )
    for event in events.nsmallest(3, "maximum_drawdown").itertuples(index=False):
        recovery = f"recovered {event.recovery_date:%Y-%m}" if event.recovered else "not recovered"
        ax.annotate(
            f"{event.maximum_drawdown:.0%}\n{event.months_underwater:.0f}m underwater\n({recovery})",
            xy=(event.trough_date, event.maximum_drawdown),
            xytext=(0, -38),
            textcoords="offset points",
            ha="center",
            fontsize=7.5,
            arrowprops={"arrowstyle": "-", "color": "#666666", "linewidth": 0.6},
        )
    ax.set_title("Drawdowns from prior peak, compounded (three deepest baseline episodes annotated)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylim(top=0.02, bottom=min(ax.get_ylim()[0], events["maximum_drawdown"].min() * 1.6))
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "baseline_drawdowns.png", dpi=180)
    plt.close(fig)


def plot_exposures(exposures: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True)
    exposures[["gross_exposure", "long_exposure", "short_exposure", "net_exposure"]].plot(ax=axes[0], linewidth=1.3)
    axes[0].set_title("Baseline gross, long, short, and net exposure (executed weights)")
    axes[0].axhline(0, color="#666666", linewidth=0.8)
    axes[0].set_ylabel("Notional / capital")
    gross_columns = [c for c in exposures.columns if c.startswith("gross_") and c != "gross_exposure"]
    exposures[gross_columns].rename(columns=lambda c: c.removeprefix("gross_")).plot.area(ax=axes[1], stacked=True, linewidth=0)
    axes[1].set_title("Gross exposure by asset class")
    axes[1].set_ylabel("Notional / capital")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "baseline_exposures.png", dpi=180)
    plt.close(fig)


def plot_cost_sensitivity(costs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for name, color in ((TSMOM_NAME, BASELINE_COLOR), (STATIC_NAME, STATIC_COLOR)):
        subset = costs.loc[costs["strategy"] == name]
        break_even = subset["break_even_cost_bps"].iloc[0]
        axes[0].plot(subset["cost_bps"], subset["cagr"], marker="o", color=color, label=f"{name} (break-even {break_even:.0f} bps)")
        axes[1].plot(subset["cost_bps"], subset["sharpe_0rf"], marker="o", color=color, label=name)
    axes[0].set_title("CAGR after transaction costs")
    axes[0].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[1].set_title("Sharpe ratio after transaction costs")
    for ax in axes:
        ax.set_xlabel("One-way cost (bps of traded notional)")
        ax.set_xticks(COST_BPS)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "baseline_transaction_cost_sensitivity.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    asset_map = read_asset_map()
    tsmom, static = build_baseline(returns, asset_map)

    checks = timing_checks(returns, asset_map, tsmom)
    checks.to_csv(OUT_DIR / "timing_checks.csv", index=False)
    if not checks["passed"].all():
        raise AssertionError(f"Timing checks failed:\n{checks.to_string(index=False)}")

    monthly = pd.DataFrame({TSMOM_NAME: tsmom["returns"], STATIC_NAME: static["returns"]})
    for bps in COST_BPS[1:]:
        monthly[f"{TSMOM_NAME}_net_{bps}bps"] = net_of_costs(tsmom["returns"], tsmom["turnover"], bps)

    summary = pd.DataFrame(
        [performance_statistics(r["name"], r["returns"], r["turnover"]) for r in (tsmom, static)]
    )
    events = drawdown_events(tsmom["returns"])
    rolling = rolling_performance({TSMOM_NAME: tsmom["returns"], STATIC_NAME: static["returns"]})
    costs = transaction_cost_sensitivity([tsmom, static])
    executed = tsmom["execution_weights"].loc[EVAL_START:]
    exposures = exposure_table(executed, asset_map)
    turnover = turnover_table(tsmom, static)

    # Standardized series for downstream analyses. Volatility estimates are aligned with
    # executed weights: the row for month t holds the estimate formed at t-1.
    monthly.to_csv(OUT_DIR / "baseline_monthly_returns.csv", index_label="Date")
    tsmom["instrument_returns"].to_csv(OUT_DIR / "baseline_instrument_returns.csv", index_label="Date")
    executed.to_csv(OUT_DIR / "baseline_executed_weights.csv", index_label="Date")
    tsmom["vol"].shift(1).loc[EVAL_START:].to_csv(OUT_DIR / "baseline_volatility_estimates.csv", index_label="Date")
    exposures.to_csv(OUT_DIR / "baseline_exposures.csv", index_label="Date")
    turnover.to_csv(OUT_DIR / "baseline_turnover.csv", index_label="Date")

    summary.to_csv(OUT_DIR / "baseline_performance_summary.csv", index=False)
    rolling.to_csv(OUT_DIR / "rolling_performance.csv", index=False)
    events.to_csv(OUT_DIR / "drawdown_events.csv", index=False)
    costs.to_csv(OUT_DIR / "transaction_cost_sensitivity.csv", index=False)
    exposure_summary(exposures).to_csv(OUT_DIR / "exposure_summary.csv", index=False)

    plot_cumulative(monthly)
    plot_rolling(rolling)
    plot_drawdowns(monthly, events)
    plot_exposures(exposures)
    plot_cost_sensitivity(costs)

    print(f"Wrote baseline-performance outputs to {OUT_DIR}")
    print("\nTiming checks:")
    print(checks.to_string(index=False))
    columns = [
        "strategy", "cumulative_return", "cagr", "annual_mean_return", "annual_volatility",
        "sharpe_0rf", "max_drawdown", "max_drawdown_months_underwater", "longest_underwater_months",
        "annual_turnover",
    ]
    print("\nPerformance summary:")
    print(summary[columns].round(4).to_string(index=False))
    print("\nTransaction-cost sensitivity:")
    print(costs.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
