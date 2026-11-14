"""Compare monthly, weekly and daily rebalancing on the same daily closes."""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from strategy_backtest_adj import (
    BASELINE_LOOKBACK, EVAL_START, expanding_volatility, momentum_signal,
    read_asset_map, read_returns, tsmom_weights,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "rebalance_frequency_output"
COST_BPS = (0, 2, 5, 10, 25)
FREQUENCIES = ("monthly", "weekly", "daily")


def read_closes(instruments, end):
    quotes = {}
    for instrument in instruments:
        source = ROOT / "FuturesUnderlyingData" / f"{instrument}.csv"
        frame = pd.read_csv(source, index_col=0, parse_dates=True)
        close = pd.to_numeric(frame["Close"], errors="coerce")
        if close.index.has_duplicates or (close.dropna() <= 0).any():
            raise ValueError(f"Duplicate dates or nonpositive close in {source.name}")
        quotes[instrument] = close.dropna().loc[:end]
    return pd.DataFrame(quotes).sort_index().dropna(how="all").rename_axis("Date")


def formation_targets(quotes, asset_map):
    """Keep the baseline's sum-of-monthly-returns convention at month-end."""
    dates = quotes.index
    # Form at scheduled weekdays even on a market holiday. If every market
    # is closed, the signal uses the previous available marks.
    calendar = pd.bdate_range(dates.min(), dates.max() + pd.offsets.BMonthEnd(0))
    month_end = pd.Series((calendar + pd.offsets.BDay()).month != calendar.month, index=calendar)
    monthly_close = quotes.resample("ME").last()
    monthly_returns = monthly_close.pct_change(fill_method=None)
    completed_vol = expanding_volatility(monthly_returns)
    prior_sum = monthly_returns.rolling(BASELINE_LOOKBACK - 1).sum()
    previous_month = (calendar.to_period("M") - 1).to_timestamp("M")

    def align_previous(frame):
        return frame.reindex(previous_month).set_axis(calendar)

    marks = quotes.reindex(calendar).ffill()
    last_close = align_previous(monthly_close)
    partial_return = marks / last_close - 1
    signal = np.sign(align_previous(prior_sum) + partial_return)
    volatility = align_previous(completed_vol)
    month_labels = calendar[month_end].to_period("M").to_timestamp("M")
    volatility.loc[month_end] = completed_vol.reindex(month_labels).to_numpy()
    signal.loc[month_end] = momentum_signal(monthly_returns, BASELINE_LOOKBACK).reindex(month_labels).to_numpy()

    # Expanding volatility survives gaps, so require a recent quote as well.
    fresh = quotes.reindex(calendar).notna().rolling(10, min_periods=1).max().astype(bool)
    volatility = volatility.where(fresh & (volatility > 0))
    targets = tsmom_weights(signal, volatility, asset_map).fillna(0)
    return targets, month_end, monthly_returns, signal


def simulate(quotes, targets, cost_bps):
    """Mark existing holdings, then fill new targets at the next quoted close."""
    calendar = targets.index
    marks = quotes.reindex(calendar).ffill()
    changes = marks.pct_change(fill_method=None).fillna(0).to_numpy()
    quoted = quotes.reindex(calendar).notna().to_numpy()
    instructions = targets.to_numpy()
    position = np.zeros(len(quotes.columns))
    pending = np.zeros(len(quotes.columns), dtype=bool)
    target = position.copy()
    rows = []
    for i, date in enumerate(calendar):
        gross_return = float(position @ changes[i])
        if gross_return <= -1:
            raise ValueError(f"Nonpositive gross wealth on {date.date()}")
        drifted = position * (1 + changes[i]) / (1 + gross_return)
        fills = pending & quoted[i]
        desired = np.where(fills, target, drifted)
        turnover = float(np.abs(desired - drifted).sum())
        # Size trades relative to marked NAV before commission. Costs lower
        # NAV and therefore increase the post-cost weights slightly.
        cost = turnover * cost_bps / 1e4
        if cost >= 1:
            raise ValueError(f"Trading cost exceeds marked wealth on {date.date()}")
        position = desired / (1 - cost)
        net_return = (1 + gross_return) * (1 - cost) - 1
        pending[fills] = False
        stale_gross = np.abs(position[~quoted[i]]).sum()
        rows.append((gross_return, net_return, turnover, (1 + gross_return)*cost,
                     np.abs(position).sum(), stale_gross, bool(fills.any())))
        # Today's close and signal can only affect future trades.
        if np.isfinite(instructions[i]).all():
            target = instructions[i]
            pending[:] = True
    return pd.DataFrame(rows, index=calendar, columns=[
        "gross_return", "net_return", "turnover", "cost", "gross_exposure",
        "unquoted_gross_exposure", "traded",
    ])


def performance(result):
    daily = result["net_return"]
    # Use calendar months for all headline performance metrics, including
    # volatility and Sharpe, to match the report's existing conventions.
    monthly = (1 + daily).resample("ME").prod() - 1
    wealth = (1 + daily).cumprod()
    years = len(monthly) / 12
    vol = monthly.std() * np.sqrt(12)
    return {
        "months": len(monthly),
        "cagr": wealth.iloc[-1] ** (1 / years) - 1,
        "annual_volatility": vol,
        "sharpe_0rf": 12 * monthly.mean() / vol,
        "max_daily_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min(),
        "annual_turnover": result.turnover.sum() / years,
        "annual_trading_cost": result.cost.sum() / years,
        "average_gross_exposure": result.gross_exposure.mean(),
        "average_unquoted_gross_exposure": result.unquoted_gross_exposure.mean(),
        "trading_sessions": int(result.traded.sum()),
    }


def main():
    monthly_source = read_returns()
    quotes = read_closes(monthly_source.columns, monthly_source.index.max())
    targets, month_end, reconstructed, _ = formation_targets(quotes, read_asset_map())
    official = monthly_source.set_axis(monthly_source.index.to_period("M").to_timestamp("M"))
    gap = reconstructed.reindex_like(official) - official
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "overlapping_months": gap.count(),
        "mean_absolute_return_difference": gap.abs().mean(),
        "max_absolute_return_difference": gap.abs().max(),
        "last_quote": quotes.apply(pd.Series.last_valid_index),
    }).rename_axis("instrument").to_csv(OUT / "data_reconciliation.csv")
    weeks = targets.index.dayofweek == 4
    schedules = {"monthly": month_end, "weekly": weeks, "daily": np.ones(len(targets), dtype=bool)}
    results, rows = {}, []
    for cadence in FREQUENCIES:
        orders = targets.copy()
        orders.loc[~schedules[cadence]] = np.nan
        for bps in COST_BPS:
            result = simulate(quotes, orders, bps).loc[EVAL_START:official.index.max()]
            rows.append({"frequency": cadence, "cost_bps": bps, **performance(result)})
            if bps in (0, 10):
                results[cadence, bps] = result

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "performance_summary.csv", index=False)
    pd.concat(results, names=["frequency", "cost_bps", "Date"]).to_csv(OUT / "daily_results.csv")
    periods = []
    for (cadence, bps), result in results.items():
        for start, end in (("1976", "1989"), ("1990", "1999"), ("2000", "2014")):
            periods.append({"frequency": cadence, "cost_bps": bps, "period": f"{start}–{end}",
                            **performance(result.loc[start:end])})
    period_summary = pd.DataFrame(periods)
    period_summary.to_csv(OUT / "performance_by_period.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
    for cadence in FREQUENCIES:
        daily = results[cadence, 10].net_return
        wealth = (1 + daily).cumprod()
        axes[0].plot(wealth, label=cadence.title())
        axes[1].plot(wealth / wealth.cummax().clip(lower=1) - 1, label=cadence.title(), lw=0.9)
    axes[0].set(title="Portfolio wealth after 10 bps trading costs", ylabel="Growth of $1", yscale="log")
    axes[1].set(title="Daily drawdown after 10 bps trading costs", ylabel="Drawdown")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:
        ax.legend(loc="best")
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "frequency_comparison.png", dpi=150)
    plt.close(fig)
    write_report(summary, period_summary, gap)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


def write_report(summary, periods, gap):
    def table(frame):
        rows = ["| Frequency | Cost (bps) | CAGR | Annual vol | Sharpe | Daily max drawdown | Annual turnover |",
                "|---|---:|---:|---:|---:|---:|---:|"]
        for r in frame.itertuples():
            rows.append(f"| {r.frequency} | {r.cost_bps} | {r.cagr:.2%} | {r.annual_volatility:.2%} | "
                        f"{r.sharpe_0rf:.2f} | {r.max_daily_drawdown:.2%} | {r.annual_turnover:.2f} |")
        return "\n".join(rows)

    cases = summary.set_index(["frequency", "cost_bps"])
    monthly, weekly, daily = (cases.loc[(cadence, 10)] for cadence in FREQUENCIES)
    gross_daily = cases.loc[("daily", 0), "cagr"]
    gross_weekly = cases.loc[("weekly", 0), "cagr"]
    (OUT / "frequency_report.md").write_text(
        "# Rebalance frequency experiment\n\n"
        "The three strategies share a futures universe, the baseline 12-month momentum convention, "
        "expanding volatility sizing, and a January 1976 to December 2014 evaluation window. "
        "The adjusted baseline sizing has no portfolio volatility target or explicit gross exposure cap. "
        "The monthly control uses reconstructed daily-close data, so the primary comparisons are within this experiment.\n\n"
        "Monthly signals form on the last weekday of the month, weekly signals on Fridays, and daily signals "
        "on weekdays. Within a month, the signal sums 11 completed monthly returns and the "
        "current month-to-date return. At month-end this equals the usual sum of 12 monthly returns. "
        "Instrument volatility updates only at month-end using at least 36 monthly observations. "
        "A quote in the last ten weekdays is required for eligibility, and signals with incomplete histories receive zero exposure.\n\n"
        "Positions are marked and allowed to drift between rebalances. Instructions formed at a close "
        "fill at the next quoted close for each instrument, using the latest pending instruction. "
        "Missing quotes carry the last mark; an instrument with no further quotes remains marked at its last close. "
        "The output reports gross exposure in instruments without a quote that day. Synthetic cross-market "
        "marking and observed closes are approximations to executable futures prices.\n\n"
        f"Daily-close reconstruction overlaps the supplied monthly file in {gap.count().sum():,} instrument-months. "
        f"The pooled mean absolute difference is {gap.abs().stack().mean():.4%}. "
        "Differences in price histories, delayed close fills and weight drift limit direct comparison with the published baseline.\n\n"
        "Costs are charged on drift-adjusted traded notional. The 2–25 bps scenarios are illustrative. "
        "They omit explicit futures roll, financing and size-dependent market impact. "
        "Returns compound daily, drawdowns use daily marks, and annual volatility and Sharpe use calendar-month returns.\n\n"
        "## Full-period comparison\n\n" + table(summary) + "\n\n"
        f"Before costs, daily CAGR is {gross_daily:.2%} and weekly CAGR is {gross_weekly:.2%}. "
        f"At 10 bps, weekly CAGR is {weekly.cagr:.2%}, versus {monthly.cagr:.2%} for monthly "
        f"and {daily.cagr:.2%} for daily. Daily turnover reaches {daily.annual_turnover:.2f} times capital "
        f"per year versus {weekly.annual_turnover:.2f} for weekly. Monthly leads at 25 bps. "
        "At 10 bps, weekly leads in two of three subperiods by CAGR, with monthly ahead in the 1990s. "
        "These are historical comparisons under fixed cost assumptions.\n\n"
        "## Subperiod checks at 10 bps\n\n" +
        "\n\n".join(f"**{period}**\n\n{table(frame)}" for period, frame in periods[periods.cost_bps == 10].groupby("period")) +
        "\n\n![Cumulative wealth and drawdown](frequency_comparison.png)\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
