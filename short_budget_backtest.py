"""Reduce short notional on the shared price trend baseline and compare controls."""

from argparse import ArgumentParser
from pathlib import Path

import pandas as pd

import economic_trend as trend
from net_exposure_backtest import match_gross
from net_exposure_out_of_sample import DATA, ROOT, load_extension
from strategy_backtest_adj import read_returns

OUT = ROOT / "outputs" / "short_budget_output"
SHORT_MULTIPLIER = 0.50
SHORT_MULTIPLIERS = (1.0, 0.75, 0.50, 0.25, 0.0)
COST_SCENARIOS = (0, 2, 5, 10)
LABELS = {
    "baseline": "Shared price trend baseline",
    "half_short": "Half-sized short positions",
    "gross_matched": "Same gross exposure, original long–short proportions",
}


def short_budget(weights, multiplier=SHORT_MULTIPLIER):
    return weights.clip(lower=0) + multiplier * weights.clip(upper=0)


def cagr(returns):
    return (1 + returns).prod() ** (12 / len(returns)) - 1


def evaluate(returns, start):
    baseline = trend.price_trend_weights(returns)
    half_short = short_budget(baseline)
    weights = {"baseline": baseline, "half_short": half_short,
               "gross_matched": match_gross(baseline, half_short)}
    stats, periods, costs, monthly = [], [], [], {}
    for name, formed in weights.items():
        backtest = trend.backtest(formed, returns)
        sample = backtest.loc[start:]
        monthly[name] = sample
        stats.append({
            "strategy": name, "months": len(sample), **trend.stats(backtest, start, None),
            "gross_cagr": cagr(sample.gross), "net_cagr": cagr(sample.net),
            "net_cumulative_return": (1 + sample.net).prod() - 1,
        })
        for label, first, last in (
            ("1980–1997", "1980", "1997"), ("1998–2014", "1998", "2014"),
            ("2015–2019", "2015", "2019"), ("2020–latest", "2020", None),
        ):
            sub = backtest.loc[first:last]
            if not sub.empty:
                periods.append({"strategy": name, "period": label, "months": len(sub),
                                "net_cagr": cagr(sub.net)})
        trade_and_roll_base = sample.turnover + sample.leverage * trend.ROLLS_PER_YEAR / 12
        for bps in COST_SCENARIOS:
            after_cost = sample.gross - trade_and_roll_base * bps / 1e4
            costs.append({"strategy": name, "cost_bps": bps, "net_cagr": cagr(after_cost)})
    budgets = []
    for multiplier in SHORT_MULTIPLIERS:
        sample = trend.backtest(short_budget(baseline, multiplier), returns).loc[start:]
        budgets.append({"short_multiplier": multiplier, "net_cagr": cagr(sample.net)})
    return (pd.DataFrame(stats).set_index("strategy"), pd.DataFrame(periods),
            pd.DataFrame(costs), pd.DataFrame(budgets), monthly)


def report(summary, periods, costs, budgets):
    base, reduced, matched = (summary.loc[name] for name in LABELS)
    lines = [
        "# Leverage and imbalance with a smaller short budget",
        "",
        f"Evaluation covers {base.start} through {base.end}, with {base.months} months. "
        f"The strategy starts from the shared {trend.TARGET_VOL:.0%} price trend targets, keeps "
        f"each positive weight, and multiplies each negative weight by {SHORT_MULTIPLIER:.0%}. "
        "The targets earn returns in the next month. This reduces gross exposure and increases "
        "signed net exposure. The matched control scales both sides proportionally to the same gross "
        "exposure each month, keeping the original long–short proportions.",
        "",
        f"We use the shared model of {trend.TCOST_BPS:g} bps per unit of target-weight turnover "
        f"and {trend.TCOST_BPS:g} bps per roll at {trend.ROLLS_PER_YEAR:g} rolls per year. "
        "Missing realized returns are treated as zero, as in the shared baseline.",
        "",
        "| Strategy | Gross CAGR | Net CAGR | Annualized mean net return | Max drawdown | Annual turnover | Avg. gross | Avg. signed net |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in summary.iterrows():
        lines.append(f"| {LABELS[name]} | {row.gross_cagr:+.2%} | {row.net_cagr:+.2%} | "
                     f"{row.avg_net_ret:+.2%} | {row.max_dd:.2%} | {row.turnover:.2f}× | "
                     f"{row.leverage:.2f}× | {row.imbalance:+.2f}× |")
    lines += [
        "",
        f"The half-short strategy improves net CAGR by {(reduced.net_cagr-base.net_cagr)*100:.2f} "
        f"percentage points versus the baseline and {(reduced.net_cagr-matched.net_cagr)*100:.2f} "
        "points versus the control at equal gross exposure.",
        "",
        "| Period | Baseline net CAGR | Half-short net CAGR | Matched control net CAGR |",
        "|---|---:|---:|---:|",
    ]
    for period, group in periods.groupby("period", sort=False):
        values = group.set_index("strategy").loc[list(LABELS), "net_cagr"]
        lines.append(f"| {period} | " + " | ".join(f"{value:+.2%}" for value in values) + " |")
    lines += ["", "| Cost per unit traded or rolled | Baseline net CAGR | Half-short net CAGR | Matched control net CAGR |",
              "|---|---:|---:|---:|"]
    for bps, group in costs.groupby("cost_bps"):
        values = group.set_index("strategy").loc[list(LABELS), "net_cagr"]
        lines.append(f"| {bps:g} bps | " + " | ".join(f"{value:+.2%}" for value in values) + " |")
    lines += [
        "",
        "Short budgets tested on the later sample were "
        + ", ".join(f"{row.short_multiplier:.0%} ({row.net_cagr:+.2%} net CAGR)"
                    for row in budgets.itertuples()) + ". "
        "We favored the half-short rule to retain meaningful short exposure. The idea followed the earlier "
        "return attribution on the same post-2014 period, so this is an exploratory result. "
        "The historical comparisons show the trade-off with the original strategy before 2015. "
        "The higher net long exposure also increases sensitivity to sustained market declines.",
        "",
        "Run `python short_budget_backtest.py` from the repository root to reproduce the comparison.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    historical = read_returns()
    historical.index = historical.index.to_period("M").to_timestamp("M")
    extension, _, _ = load_extension(args.data_dir, historical)
    summary, periods, costs, budgets, monthly = evaluate(pd.concat([historical, extension]), extension.index[0])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output_dir / "performance_summary.csv")
    periods.to_csv(args.output_dir / "performance_by_period.csv", index=False)
    costs.to_csv(args.output_dir / "cost_sensitivity.csv", index=False)
    budgets.to_csv(args.output_dir / "short_budget_sensitivity.csv", index=False)
    pd.concat(monthly, names=["strategy", "Date"]).to_csv(args.output_dir / "monthly_results.csv")
    (args.output_dir / "short_budget_report.md").write_text(report(summary, periods, costs, budgets), encoding="utf-8")
    print(summary[["gross_cagr", "net_cagr", "max_dd", "turnover", "leverage", "imbalance"]].to_string())


if __name__ == "__main__":
    main()
