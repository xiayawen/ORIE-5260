"""Test a symmetric net exposure limit on the adjusted monthly baseline."""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from portfolio_volatility_targeting import COST_BPS, GROSS_CAP, cap_only_weights, simulate, statistics
from strategy_backtest_adj import EVAL_START, build_baseline, read_asset_map, read_returns

OUT = Path(__file__).resolve().parent / "outputs" / "net_exposure_output"
NET_CAP = 1.0
REPORT_COST = 10
LABELS = {
    "baseline": "Original baseline",
    "gross_only": "Gross cap only",
    "net_only": "Net cap only",
    "both": "Gross and net caps",
    "net_matched_gross": "Baseline scaled to net-only gross",
    "both_matched_gross": "Baseline scaled to combined gross",
}


def net_cap_weights(weights):
    """Trim only the larger side when absolute net exposure exceeds the cap."""
    longs = weights.clip(lower=0)
    shorts = weights.clip(upper=0)
    long_gross = longs.sum(axis=1)
    short_gross = -shorts.sum(axis=1)
    net = long_gross - short_gross
    long_cut = (net - NET_CAP).clip(lower=0)
    short_cut = (-net - NET_CAP).clip(lower=0)
    long_scale = 1 - long_cut.div(long_gross.replace(0, np.nan)).fillna(0)
    short_scale = 1 - short_cut.div(short_gross.replace(0, np.nan)).fillna(0)
    return longs.mul(long_scale, axis=0) + shorts.mul(short_scale, axis=0)


def match_gross(baseline, comparator):
    """Match each formation month's gross exposure, retaining baseline proportions."""
    gross = baseline.abs().sum(axis=1)
    scale = comparator.abs().sum(axis=1).div(gross.replace(0, np.nan)).fillna(1)
    return baseline.mul(scale, axis=0)


def write_report(summary, exposure):
    selected = summary[summary.cost_bps == REPORT_COST].set_index("strategy")
    lines = [
        "# Baseline leverage and net exposure",
        "",
        "This experiment asks whether limiting the adjusted futures momentum strategy's "
        "net long or short exposure improves historical performance. All variants share "
        "the original monthly momentum signals and January 1976–December 2014 sample.",
        "",
        f"The net cap is ±{NET_CAP:g}× account equity. When net exposure exceeds the limit, "
        "positions on the larger side are reduced proportionally. The smaller side retains "
        "its weights. The combined strategy first applies the "
        f"{GROSS_CAP:g}× gross cap, then applies the net cap.",
        "",
        "Each matched control scales all baseline weights by the same factor to match the "
        "corresponding capped strategy's gross exposure each month. This preserves the original "
        "long/short proportions and helps distinguish the effect of changing those proportions "
        "from the effect of reducing total exposure. The strategies can still have different "
        "turnover, risk concentrations, and trading costs.",
        "",
        f"## Results at {REPORT_COST} bps per one-way change in target weight",
        "",
        "| Strategy | CAGR | Annual vol | Sharpe | Max drawdown | Annual turnover | Avg. gross | Avg. net | Avg. absolute net |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, label in LABELS.items():
        r, e = selected.loc[name], exposure.loc[name]
        lines.append(f"| {label} | {r.cagr:.2%} | {r.annual_volatility:.2%} | {r.sharpe_0rf:.2f} | "
                     f"{r.max_drawdown:.2%} | {r.annual_turnover:.2f}× | {e.average_gross:.2f}× | "
                     f"{e.average_net:+.2f}× | {e.average_absolute_net:.2f}× |")
    lines += [
        "",
        f"The baseline exceeds the ±{NET_CAP:g}× net limit in "
        f"{exposure.loc['baseline', 'above_net_cap_frequency']:.1%} of execution months. "
        f"After applying the gross cap alone, the fraction is "
        f"{exposure.loc['gross_only', 'above_net_cap_frequency']:.1%}.",
        "",
    ]
    for capped, matched in (("net_only", "net_matched_gross"), ("both", "both_matched_gross")):
        delta = (selected.loc[capped] - selected.loc[matched]) * 100
        lines.append(f"- **{LABELS[capped]} versus its matched gross control.** "
                     f"CAGR difference {delta.cagr:+.2f} percentage points, "
                     f"annual volatility difference {delta.annual_volatility:+.2f} points, "
                     f"and maximum drawdown difference {delta.max_drawdown:+.2f} points. "
                     "A positive drawdown difference corresponds to a smaller loss.")
    lines += [
        "",
        "Weights are formed using data through the formation month and earn returns in the "
        "next month. Costs use the existing fixed-rate turnover model at 0, 5, 10 and 25 bps. "
        "Drawdowns use monthly wealth and Sharpe assumes zero risk-free yield. The exposure "
        "limits apply to target weights at rebalance. These historical comparisons use an "
        "already studied sample and omit funding, roll and market impact.",
        "",
        "![Net exposure and performance comparison](net_exposure_comparison.png)",
        "",
        "Run `python net_exposure_backtest.py` from the project root to reproduce the results.",
    ]
    (OUT / "net_exposure_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_comparison(monthly, output_dir=OUT, *, return_column=f"return_{REPORT_COST}bps",
                    cost_label=f"{REPORT_COST} bps trading costs", baseline_label=LABELS["baseline"],
                    names=("baseline", "gross_only", "net_only", "both", "both_matched_gross"),
                    include_initial_wealth=True):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for name in names:
        data = monthly[name]
        label = baseline_label if name == "baseline" else LABELS[name]
        line, = axes[0].plot(data.net_exposure, lw=0.8, label=label)
        wealth = (1 + data[return_column]).cumprod()
        peak = wealth.cummax()
        if include_initial_wealth:
            peak = peak.clip(lower=1)
        drawdown = wealth / peak - 1
        axes[1].plot(drawdown, lw=1, color=line.get_color())
    for limit in (NET_CAP, -NET_CAP):
        axes[0].axhline(limit, color="black", linestyle="--", lw=0.8)
    axes[0].set(title="Net exposure at monthly rebalance", ylabel="Multiple of equity")
    axes[1].set(title=f"Drawdown after {cost_label}", ylabel="Drawdown")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(fontsize=8, ncol=2)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_dir / "net_exposure_comparison.png", dpi=150)
    plt.close(fig)


def build_exposure_strategies(formed):
    gross_only, _ = cap_only_weights(formed)
    net_only = net_cap_weights(formed)
    both = net_cap_weights(gross_only)
    return {
        "baseline": formed, "gross_only": gross_only, "net_only": net_only, "both": both,
        "net_matched_gross": match_gross(formed, net_only),
        "both_matched_gross": match_gross(formed, both),
    }


def evaluate_exposure_strategies(returns, formed, start):
    summary, exposure, monthly = [], [], {}
    for name, weights in build_exposure_strategies(formed).items():
        raw, turnover, executed = (item.loc[start:] for item in simulate(returns, weights))
        gross = executed.abs().sum(axis=1)
        net = executed.sum(axis=1)
        data = pd.DataFrame({"gross_return": raw, "turnover": turnover, "gross_exposure": gross,
                             "net_exposure": net})
        exposure.append({
            "strategy": name, "average_gross": gross.mean(), "maximum_gross": gross.max(),
            "average_net": net.mean(), "average_absolute_net": net.abs().mean(),
            "max_absolute_net": net.abs().max(), "net_long_frequency": (net > 1e-10).mean(),
            "above_net_cap_frequency": (net.abs() > NET_CAP + 1e-10).mean(),
        })
        for bps in COST_BPS:
            net_return = raw - turnover * bps / 1e4
            data[f"return_{bps}bps"] = net_return
            summary.append({"strategy": name, "cost_bps": bps, **statistics(net_return, turnover)})
        monthly[name] = data
    return pd.DataFrame(summary), pd.DataFrame(exposure).set_index("strategy"), monthly


def main():
    returns = read_returns()
    baseline, _ = build_baseline(returns, read_asset_map())
    summary, exposure, monthly = evaluate_exposure_strategies(returns, baseline["weights"], EVAL_START)
    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / "performance_summary.csv", index=False)
    exposure.to_csv(OUT / "exposure_summary.csv")
    pd.concat(monthly, names=["strategy", "Date"]).to_csv(OUT / "monthly_results.csv")
    write_report(summary, exposure)
    plot_comparison(monthly)
    print((OUT / "net_exposure_report.md").read_text(encoding="utf-8").split("![")[0])


if __name__ == "__main__":
    main()
