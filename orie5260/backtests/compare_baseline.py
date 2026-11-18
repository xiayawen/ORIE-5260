"""Compare the two strategies on identical 21-business-day period endpoints."""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from orie5260.common.data import ROOT

BASE = ROOT / "outputs" / "baseline" / "periods_exante_11_sample_u58.csv"
FINAL = ROOT / "outputs" / "final_strategy" / "daily_returns_and_costs.csv"
OUT = ROOT / "outputs" / "comparison"
PERIODS = {"IS_1976_2014": ("1976-01-01", "2014-12-31"),
           "OOS_2015_2025": ("2015-01-01", "2025-05-31")}


def drawdown_series(returns):
    """Loss from the previous period-end wealth peak, including initial $1."""
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax().clip(lower=1) - 1


def measures(returns):
    wealth = (1 + returns).cumprod()
    vol = returns.std() * np.sqrt(12)
    return {"periods": len(returns), "annual_mean_net_return": returns.mean() * 12,
            "annual_volatility": vol, "sharpe_zero_rf": returns.mean() * 12 / vol,
            "cagr": wealth.iloc[-1] ** (12 / len(returns)) - 1,
            "max_endpoint_drawdown": drawdown_series(returns).min()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = pd.read_csv(BASE, index_col="Date", parse_dates=True)
    final = pd.read_csv(FINAL, index_col="Date", parse_dates=True)
    dates = baseline.index.intersection(final.index)
    # Returns earned from the preceding common formation close through the
    # current 21-day period end. The first period begins at prior formation.
    wealth = (1 + final.net_return).cumprod().reindex(dates)
    final_period = wealth / wealth.shift(1) - 1
    aligned = pd.DataFrame({"baseline": baseline.net.reindex(dates),
                            "final_four_sleeve": final_period}, index=dates).dropna()
    aligned.to_csv(OUT / "aligned_period_returns.csv", index_label="period_end")
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, (label, (start, end)) in zip(axes, PERIODS.items()):
        sample = aligned.loc[start:end]
        for name in sample:
            rows.append({"strategy": name, "period": label, **measures(sample[name])})
            ax.plot(sample.index, (1 + sample[name]).cumprod(), label=name.replace("_", " "))
        if label.startswith("IS"):
            ax.set_yscale("log")
        ax.set(title=label.replace("_", " "), ylabel="Growth of $1", xlabel="21-day period end")
        ax.grid(alpha=.2); ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "baseline_vs_four_sleeve.png", dpi=170)
    plt.close(fig)
    drawdown_fig, drawdown_axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    colors = {"baseline": "#1f77b4", "final_four_sleeve": "#ff7f0e"}
    names = {"baseline": "Course baseline", "final_four_sleeve": "Four-sleeve portfolio"}
    titles = {"IS_1976_2014": "In sample (1976–2014)",
              "OOS_2015_2025": "Later evaluation (2015–May 2025)"}
    for ax, (label, (start, end)) in zip(drawdown_axes, PERIODS.items()):
        sample = aligned.loc[start:end]
        for name in sample:
            drawdown = drawdown_series(sample[name])
            ax.plot(sample.index, drawdown,
                    label=f"{names[name]} (max {drawdown.min():.1%})",
                    color=colors[name], linewidth=1.7)
        ax.axhline(0, color="0.4", linewidth=.8)
        ax.set(title=titles[label], xlabel="21-day period end")
        ax.set_ylim(-.30, .025)
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(alpha=.2)
        ax.legend(loc="lower left")
    drawdown_axes[0].set_ylabel("Drawdown from prior peak")
    drawdown_fig.suptitle("Matched-period drawdowns: course baseline vs four-sleeve portfolio")
    drawdown_fig.tight_layout()
    drawdown_fig.savefig(OUT / "drawdown_comparison.png", dpi=170)
    plt.close(drawdown_fig)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "matched_period_performance.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
