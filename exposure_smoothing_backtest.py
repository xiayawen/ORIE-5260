"""Smooth portfolio leverage and dollar imbalance on the shared monthly baseline."""

from argparse import ArgumentParser
from pathlib import Path

import numpy as np
import pandas as pd

import economic_trend as trend
from net_exposure_out_of_sample import DATA, ROOT, load_extension
from strategy_backtest_adj import read_returns

OUT = ROOT / "outputs" / "exposure_smoothing_output"
WINDOW = 3
MAX_SIDE_MULTIPLIER = 1.25
LABELS = {
    "baseline": "Shared price trend baseline",
    "leverage_smoothing": "Smooth leverage only",
    "leverage_and_imbalance_smoothing": "Smooth leverage and imbalance",
}


def smooth_exposure(weights):
    """Smooth gross leverage and signed net share using only current and past targets."""
    longs = weights.clip(lower=0)
    shorts = weights.clip(upper=0)
    long_gross = longs.sum(axis=1)
    short_gross = -shorts.sum(axis=1)
    gross = long_gross + short_gross
    net_share = (long_gross - short_gross).div(gross.where(gross > 0))

    smooth_gross = gross.rolling(WINDOW, min_periods=1).mean()
    smooth_gross = smooth_gross.clip(upper=MAX_SIDE_MULTIPLIER * gross)
    scale = smooth_gross.div(gross.where(gross > 0)).fillna(0)
    leverage_only = weights.mul(scale, axis=0)

    smooth_share = net_share.rolling(WINDOW, min_periods=1).mean().fillna(0)
    desired_long = smooth_gross * (1 + smooth_share) / 2
    min_long = (smooth_gross - MAX_SIDE_MULTIPLIER * short_gross).clip(lower=0)
    max_long = np.minimum(smooth_gross, MAX_SIDE_MULTIPLIER * long_gross)
    target_long = desired_long.clip(lower=min_long, upper=max_long)
    target_short = smooth_gross - target_long
    long_scale = target_long.div(long_gross.where(long_gross > 0)).fillna(0)
    short_scale = target_short.div(short_gross.where(short_gross > 0)).fillna(0)
    joint = longs.mul(long_scale, axis=0) + shorts.mul(short_scale, axis=0)
    return leverage_only, joint


def evaluate(returns, start):
    baseline = trend.price_trend_weights(returns)
    leverage_only, joint = smooth_exposure(baseline)
    monthly, rows = {}, []
    for name, weights in zip(LABELS, (baseline, leverage_only, joint)):
        full = trend.backtest(weights, returns)
        sample = full.loc[start:]
        stats = trend.stats(full, start, None)
        row = {"strategy": name, "months": len(sample), **stats}
        for column in ("gross", "net"):
            wealth = (1 + sample[column]).prod()
            row[f"{column}_cagr"] = wealth ** (12 / len(sample)) - 1
            row[f"{column}_cumulative_return"] = wealth - 1
        row["average_absolute_net"] = sample.imbalance.abs().mean()
        row["mean_absolute_monthly_leverage_change"] = full.leverage.diff().abs().loc[start:].mean()
        row["mean_absolute_monthly_imbalance_change"] = full.imbalance.diff().abs().loc[start:].mean()
        rows.append(row)
        monthly[name] = sample
    return pd.DataFrame(rows), monthly


def write_report(output, summary):
    results = summary.set_index("strategy")
    baseline, leverage, joint = (results.loc[name] for name in LABELS)
    lines = [
        "# Out-of-sample leverage and imbalance smoothing",
        "",
        f"Evaluation covers {baseline.start} through {baseline.end}, with {baseline.months} monthly returns.",
        "The shared price trend baseline uses the original 12-month momentum signal, a rolling volatility "
        "estimate, and a 10% portfolio volatility target. Its weights form the starting point for both variants.",
        "",
        f"Gross exposure is the sum of absolute weights. Net share is signed net exposure divided by gross "
        f"exposure. The first variant smooths gross exposure with a trailing {WINDOW}-month average and "
        "scales both books proportionally. The second also smooths net share over the same window, then "
        "sets long and short notionals from gross exposure and the smoothed share. Each side may use up to "
        f"{MAX_SIDE_MULTIPLIER:.2f} times its baseline notional. Existing assets retain their direction "
        "and their relative weights within each book. The two variants match on gross exposure every month.",
        "",
        "Recorded targets use information through formation month and earn returns the following month. "
        f"All variants use the team cost model with {trend.TCOST_BPS:g} bps per unit of turnover and "
        f"{trend.TCOST_BPS:g} bps per roll at {trend.ROLLS_PER_YEAR:g} rolls annually. The parameters "
        "were fixed for this run. The evaluation period had already been examined for other specifications.",
        "",
        "| Strategy | Gross CAGR | Net CAGR | Annualized mean net return | Max drawdown | Annual turnover | Avg. gross | Avg. absolute net |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in results.iterrows():
        lines.append(f"| {LABELS[name]} | {row.gross_cagr:+.2%} | {row.net_cagr:+.2%} | "
                     f"{row.avg_net_ret:+.2%} | {row.max_dd:.2%} | {row.turnover:.2f}× | "
                     f"{row.leverage:.2f}× | {row.average_absolute_net:.2f}× |")
    lines += [
        "",
        f"Smoothing leverage alone changes net CAGR by {(leverage.net_cagr-baseline.net_cagr)*100:+.2f} "
        "percentage points versus the baseline. At the same monthly gross exposure, smoothing imbalance "
        f"as well changes net CAGR by {(joint.net_cagr-leverage.net_cagr)*100:+.2f} points and maximum "
        f"drawdown by {(joint.max_dd-leverage.max_dd)*100:+.2f} points. A positive drawdown difference "
        "corresponds to a shallower loss.",
        "",
        "The cost model uses monthly target-weight turnover. Missing returns follow the shared baseline "
        "convention and contribute zero realized P&L. The performance table and monthly returns are "
        "provided as CSV files.",
    ]
    (output / "exposure_smoothing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    historical = read_returns()
    historical.index = historical.index.to_period("M").to_timestamp("M")
    extension, _, _ = load_extension(args.data_dir, historical)
    summary, monthly = evaluate(pd.concat([historical, extension]), extension.index[0])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output_dir / "performance_summary.csv", index=False)
    pd.concat(monthly, names=["strategy", "Date"]).to_csv(args.output_dir / "monthly_results.csv")
    write_report(args.output_dir, summary)
    print(summary[["strategy", "gross_cagr", "net_cagr", "avg_net_ret", "max_dd", "turnover"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
