"""Evaluate out-of-sample exposure limits on the shared price trend baseline."""

from argparse import ArgumentParser
from pathlib import Path

import numpy as np
import pandas as pd

import economic_trend as trend
from net_exposure_backtest import LABELS, NET_CAP, build_exposure_strategies, plot_comparison
from portfolio_volatility_targeting import GROSS_CAP
from strategy_backtest_adj import read_returns

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "FuturesUnderlyingData_FullSample" / "FuturesUnderlyingData_FullSample"
OUT = ROOT / "outputs" / "net_exposure_out_of_sample_aligned"
BASELINE_LABEL = "Shared price trend baseline"


def read_full_sample_closes(folder, instruments):
    closes = {}
    for symbol in instruments:
        path = folder / f"{symbol}_RAD.CSV"
        data = pd.read_csv(path, header=None, usecols=[0, 4], names=["date", "close"])
        dates = pd.to_datetime(data.date, format="%m/%d/%Y")
        price = pd.to_numeric(data.close, errors="raise").set_axis(dates).sort_index()
        if price.empty or dates.duplicated().any() or not (np.isfinite(price) & price.gt(0)).all():
            raise ValueError(f"Duplicate dates or invalid prices in {path.name}")
        closes[symbol] = price
    return pd.DataFrame(closes).sort_index().rename_axis("Date")


def last_complete_month(latest):
    latest_month = latest.to_period("M")
    # A partial final month cannot be compared with a full portfolio holding month.
    if latest < latest_month.start_time + pd.offsets.BMonthEnd():
        latest_month -= 1
    return latest_month.to_timestamp("M")


def load_extension(folder, historical):
    closes = read_full_sample_closes(folder, historical.columns)
    latest = closes.index.max()
    end = last_complete_month(latest)
    cutoff = historical.index[-1]
    if end <= cutoff:
        raise ValueError("The supplied files contain no complete month after the historical sample")

    month_ends = pd.date_range(historical.index[0], end, freq="ME")
    marks = closes.resample("ME").last().reindex(month_ends)
    # No price carry across unquoted months. Both adjacent monthly closes are required.
    reconstructed = marks.pct_change(fill_method=None)
    extension = reconstructed.loc[reconstructed.index > cutoff]
    overlap = reconstructed.reindex(historical.index) - historical
    quality = pd.DataFrame({
        "last_quote": closes.apply(pd.Series.last_valid_index),
        "historical_overlap_months": overlap.count(),
        "historical_mean_absolute_return_difference": overlap.abs().mean(),
        "historical_max_absolute_return_difference": overlap.abs().max(),
        "oos_months_with_quote": marks.loc[extension.index].count(),
        "oos_months_with_return": extension.count(),
        "oos_largest_absolute_monthly_return": extension.abs().max(),
    }).rename_axis("instrument")
    return extension, quality, latest


def evaluate(returns, start):
    formed = trend.price_trend_weights(returns)
    monthly, summaries, exposures = {}, [], []
    for name, weights in build_exposure_strategies(formed).items():
        full = trend.backtest(weights, returns)
        sample = full.loc[start:].copy()
        row = {"strategy": name, "months": len(sample), **trend.stats(full, start, None)}
        for kind in ("gross", "net"):
            growth = (1 + sample[kind]).prod()
            row[f"{kind}_cumulative_return"] = growth - 1
            row[f"{kind}_cagr"] = growth ** (12 / len(sample)) - 1
        summaries.append(row)
        gross, net = sample.leverage, sample.imbalance
        exposures.append({
            "strategy": name,
            "average_gross": gross.mean(),
            "maximum_gross": gross.max(),
            "average_net": net.mean(),
            "average_absolute_net": net.abs().mean(),
            "max_absolute_net": net.abs().max(),
            "above_net_cap_frequency": (net.abs() > NET_CAP + 1e-10).mean(),
        })
        executed = weights.shift(1).reindex(sample.index).fillna(0)
        missing = executed.abs().where(returns.loc[sample.index].isna()).sum(axis=1)
        monthly[name] = sample.assign(gross_exposure=gross, net_exposure=net,
                                      gross_exposure_with_missing_return=missing)
    return pd.DataFrame(summaries), pd.DataFrame(exposures).set_index("strategy"), monthly


def write_report(output, summary, exposure, extension, quality, latest, missing_weight):
    results = summary.set_index("strategy")
    source_count = len(extension.columns)
    total_returns = int(extension.count().sum())
    first, last = extension.index[[0, -1]].strftime("%B %Y")
    largest_gap_month = missing_weight.idxmax().strftime("%B %Y")
    lines = [
        "# Out-of-sample leverage and net exposure on the shared price trend baseline",
        "",
        f"{first} to {last}, {len(extension)} monthly returns. All six variants start from the "
        f"price trend baseline in economic_trend.py. It uses a 12-month sign signal, {trend.VOL_WINDOW}-month "
        f"rolling instrument volatility with a {trend.VOL_FLOOR:.0%} annualized floor, and a "
        f"{trend.TARGET_VOL:.0%} portfolio volatility target based on a trailing {trend.SCALE_WINDOW}-month window. "
        f"The extension applies the {GROSS_CAP:g}× gross cap and ±{NET_CAP:g}× net cap after baseline sizing. "
        "Matched controls retain baseline long and short proportions at the same monthly gross exposure "
        "as the corresponding net cap variants.",
        "",
        f"The uploaded files provide prices for all {source_count} original tickers, with the latest "
        f"quote dated {latest.date()}. The evaluation ends in the last complete month. The original "
        "monthly returns through December 2014 seed the risk estimates and December "
        "formation weights. New returns use adjacent month-end closes from the uploaded files, "
        "including December 2014 closes for the January 2015 return. Positions execute with a "
        "one-month lag. Reported wealth starts at the sample boundary and turnover carries "
        "the preceding target weights.",
        "",
        f"The extension has {total_returns:,} observed instrument-month returns out of "
        f"{extension.size:,}. {quality.oos_months_with_return.lt(len(extension)).sum()} instruments "
        "have incomplete histories. Missing observations use the existing backtest convention "
        "of zero realized P&L on held positions. No gap is bridged with a multi-month return. "
        f"The baseline's average gross exposure with a missing realized return is {missing_weight.mean():.4f}× "
        f"of equity, with a maximum of {missing_weight.max():.4f}× in {largest_gap_month}. "
        f"All variants use economic_trend.py's cost convention of {trend.TCOST_BPS:g} bps per unit "
        f"of target-weight turnover and {trend.TCOST_BPS:g} bps per roll at {trend.ROLLS_PER_YEAR:g} "
        "rolls per year, prorated monthly by gross exposure.",
        "",
        "## Results under the shared cost model",
        "",
        "| Strategy | Gross CAGR | Net CAGR | Annualized mean net return | Annual volatility | Sharpe | Max drawdown | Avg. gross | Avg. net |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, label in LABELS.items():
        row, position = results.loc[name], exposure.loc[name]
        label = BASELINE_LABEL if name == "baseline" else label
        lines.append(f"| {label} | {row.gross_cagr:.2%} | {row.net_cagr:.2%} | "
                     f"{row.avg_net_ret:.2%} | {row.vol:.2%} | {row.sharpe:.2f} | {row.max_dd:.2%} | "
                     f"{position.average_gross:.2f}× | {position.average_net:+.2f}× |")
    baseline = results.loc["baseline"]
    lines += ["", f"The shared baseline has a net cumulative return of {baseline.net_cumulative_return:+.2%}. "
              "Annualized mean return multiplies the monthly average by 12. CAGR compounds monthly wealth."]
    lines += ["", "## Net caps versus matched gross controls", ""]
    for capped, matched in (("net_only", "net_matched_gross"), ("both", "both_matched_gross")):
        cagr_diff = 100 * (results.loc[capped, "net_cagr"] - results.loc[matched, "net_cagr"])
        drawdown_diff = 100 * (results.loc[capped, "max_dd"] - results.loc[matched, "max_dd"])
        lines.append(f"- **{LABELS[capped]}.** Net CAGR difference {cagr_diff:+.2f} percentage points "
                     f"and drawdown difference {drawdown_diff:+.2f} points at the same monthly gross exposure. "
                     "A positive drawdown difference corresponds to a shallower loss.")
    lines += [
        "",
        "The source uses continuous futures close prices. Some instrument-month moves are "
        "large. The experiment retains observed returns as supplied, and the coverage CSV "
        "reports each series' largest absolute monthly return for review.",
        "",
        "![Net exposure and drawdown](net_exposure_comparison.png)",
        "",
        "Run `python net_exposure_out_of_sample.py` from the project root to reproduce this report.",
    ]
    (output / "out_of_sample_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    historical = read_returns()
    historical.index = historical.index.to_period("M").to_timestamp("M")
    extension, quality, latest = load_extension(args.data_dir, historical)
    returns = pd.concat([historical, extension])
    start = extension.index[0]
    summary, exposure, monthly = evaluate(returns, start)
    missing_weight = monthly["baseline"].gross_exposure_with_missing_return
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "performance_summary.csv", index=False)
    exposure.to_csv(output / "exposure_summary.csv")
    pd.concat(monthly, names=["strategy", "Date"]).to_csv(output / "monthly_results.csv")
    quality.to_csv(output / "data_coverage.csv")
    plot_comparison(monthly, output, return_column="net", cost_label="trading and roll costs",
                    baseline_label=BASELINE_LABEL, names=tuple(LABELS), include_initial_wealth=False)
    write_report(output, summary, exposure, extension, quality, latest, missing_weight)
    print(summary[["strategy", "months", "gross_cagr", "net_cagr", "avg_net_ret", "max_dd"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
