"""Repeat the monthly, weekly and daily schedule comparison out of sample."""

from argparse import ArgumentParser
from pathlib import Path

import numpy as np
import pandas as pd

from net_exposure_out_of_sample import DATA, ROOT, last_complete_month, read_full_sample_closes
from rebalance_frequency_backtest import COST_BPS, FREQUENCIES, formation_targets, performance, simulate
from short_budget_backtest import SHORT_MULTIPLIER, short_budget
from strategy_backtest_adj import read_asset_map, read_returns

OUT = ROOT / "outputs" / "rebalance_frequency_out_of_sample"
HALF_SHORT_OUT = ROOT / "outputs" / "rebalance_frequency_half_short"
STALE_EXIT_DAYS = 10


def compare(returns, quotes, *, half_short=False):
    last_quote = quotes.index.max()
    end = last_complete_month(last_quote)
    start = (returns.index[-1].to_period("M") + 1).start_time
    if end < start:
        raise ValueError("No complete out-of-sample months")
    quotes = quotes.loc[:end]
    targets, month_end, _, _ = formation_targets(quotes, read_asset_map())
    if half_short:
        targets = short_budget(targets)
    schedules = {"monthly": month_end, "weekly": targets.index.dayofweek == 4}
    rows, daily, sensitivity = [], {}, []
    for cadence in FREQUENCIES:
        orders = targets.copy()
        if cadence in schedules:
            orders.loc[~schedules[cadence]] = np.nan
        for bps in COST_BPS:
            sample = simulate(quotes, orders, bps).loc[start:end]
            monthly = (1 + sample.net_return).resample("ME").prod() - 1
            rows.append({
                "frequency": cadence, "cost_bps": bps, "start": start.date(), "end": end.date(),
                **performance(sample), "annualized_mean_return": monthly.mean() * 12,
                "max_unquoted_gross_exposure": sample.unquoted_gross_exposure.max(),
            })
            if bps in (0, 10):
                daily[cadence, bps] = sample
        stale_exit = simulate(quotes, orders, 10, stale_exit_days=STALE_EXIT_DAYS).loc[start:end]
        sensitivity.append({"frequency": cadence, **performance(stale_exit)})
    return pd.DataFrame(rows), daily, pd.DataFrame(sensitivity), last_quote


def write_report(output, summary, sensitivity, last_quote, *, half_short=False):
    sample = summary.iloc[0]
    title = "# Out-of-sample rebalance frequency comparison"
    rule = ""
    if half_short:
        title += " with a smaller short budget"
        rule = (
            f" Each schedule keeps its original positive target weights and multiplies negative "
            f"targets by {SHORT_MULTIPLIER:.0%} before orders are generated. The rule followed "
            "attribution on the same post-2014 data, so the results are exploratory."
        )
    lines = [
        title,
        "",
        f"Evaluation covers {sample.start} through {sample.end}, with {sample.months} complete months. "
        f"The last available quote is dated {last_quote.date()}. The earlier price history warms up signals "
        "and positions before the start date.",
        "",
        "This repeats the earlier frequency experiment on the uploaded continuous futures closes. "
        "All three schedules share the same 12-month momentum rule, expanding instrument volatility, "
        "eligibility checks and close-to-close simulation. Within a month the signal combines 11 completed "
        "monthly returns and the current month-to-date return. Risk estimates update at month-end. "
        "Monthly targets form on the last weekday, weekly targets on Fridays and daily targets on weekdays. "
        "Orders fill at the next quoted close per instrument. Positions drift between fills." + rule,
        "",
        "Trading costs are charged per unit of drift-adjusted turnover. Cost scenarios are 0, 2, 5, 10 "
        "and 25 bps. They exclude separate roll, funding and market impact charges. Assets without a "
        "quote retain their last price and, if a trade remains pending, their existing holding. Some "
        "series stop before the end of the sample. The daily output reports unquoted gross exposure. "
        "The frequency results use this daily execution model and should be compared across schedules.",
        "",
        "| Frequency | Cost (bps) | CAGR | Annualized mean return | Sharpe | Daily max drawdown | Annual turnover |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples():
        lines.append(f"| {row.frequency} | {row.cost_bps} | {row.cagr:+.2%} | {row.annualized_mean_return:+.2%} | "
                     f"{row.sharpe_0rf:.2f} | {row.max_daily_drawdown:.2%} | {row.annual_turnover:.2f}× |")
    lines += ["", "Highest CAGR by cost assumption"]
    for bps, group in summary.groupby("cost_bps"):
        best = group.loc[group.cagr.idxmax()]
        lines.append(f"- {bps:g} bps. {best.frequency.title()} at {best.cagr:+.2%}.")
    lines += [
        "",
        f"At 10 bps, a sensitivity approximates liquidation after {STALE_EXIT_DAYS} weekdays "
        "without a quote, using the last observed mark and charging trading costs. That mark "
        "can differ from an executable exit price. The resulting CAGRs are "
        + ", ".join(f"{row.cagr:+.2%} for {row.frequency}" for row in sensitivity.itertuples()) + ".",
    ]
    (output / "frequency_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--half-short", action="store_true", help="apply the half-short rule to each schedule")
    args = parser.parse_args()
    output = args.output_dir if args.output_dir is not None else (HALF_SHORT_OUT if args.half_short else OUT)
    historical = read_returns()
    quotes = read_full_sample_closes(args.data_dir, historical.columns)
    summary, daily, sensitivity, last_quote = compare(historical, quotes, half_short=args.half_short)
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "performance_summary.csv", index=False)
    pd.concat(daily, names=["frequency", "cost_bps", "Date"]).to_csv(output / "daily_results.csv")
    quote_coverage = quotes.apply(pd.Series.last_valid_index).rename("last_quote")
    quote_coverage.to_csv(output / "last_quote_by_instrument.csv")
    sensitivity.to_csv(output / "stale_quote_sensitivity_10bps.csv", index=False)
    write_report(output, summary, sensitivity, last_quote, half_short=args.half_short)
    print(summary[["frequency", "cost_bps", "months", "cagr", "max_daily_drawdown", "annual_turnover"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
