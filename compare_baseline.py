"""Compare the two strategies on identical 21-business-day period endpoints."""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_utils import ROOT

BASE = ROOT / "outputs" / "baseline" / "periods_exante_11_sample_u58.csv"
FINAL = ROOT / "outputs" / "final_strategy" / "daily_returns_and_costs.csv"
OUT = ROOT / "outputs" / "comparison"
PERIODS = {"IS_1976_2014": ("1976-01-01", "2014-12-31"),
           "OOS_2015_2025": ("2015-01-01", "2025-05-31")}


def measures(returns):
    wealth = (1 + returns).cumprod()
    vol = returns.std() * np.sqrt(12)
    return {"periods": len(returns), "annual_mean_net_return": returns.mean() * 12,
            "annual_volatility": vol, "sharpe_zero_rf": returns.mean() * 12 / vol,
            "cagr": wealth.iloc[-1] ** (12 / len(returns)) - 1,
            "max_endpoint_drawdown": (wealth / wealth.cummax() - 1).min()}


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
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "matched_period_performance.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
