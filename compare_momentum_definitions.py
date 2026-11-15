"""Compare project price-trend TSMOM with the later XSMOM experiment."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from economic_trend import price_trend_weights, backtest as economic_backtest
from futures_factor_backtest import read_returns, read_asset_map, build_signals, factor_weights, evaluate
from momentum_overlay import backtest

OUT = Path(__file__).resolve().parent / "outputs" / "momentum_definition_comparison"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    signals, vol = build_signals(r)
    classes = read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    tsmom = price_trend_weights(r)
    xsmom = factor_weights(signals["XSMOM_12_1"], vol, classes)
    runs = {"Project TSMOM (10% target vol)": backtest(tsmom, r),
            "Recent XSMOM (unit gross)": backtest(xsmom, r)}
    net = pd.DataFrame({name: frame.net for name, frame in runs.items()})
    net.loc["1980-01-01":].to_csv(OUT / "matched_cost_returns.csv")
    rows = []
    for period, start in [("1980_2014", "1980-01-01"), ("2005_2014", "2005-01-01")]:
        sample = net.loc[start:].dropna()
        for name in sample:
            rows.append(dict(strategy=name, period=period, **evaluate(sample[name])))
    pd.DataFrame(rows).to_csv(OUT / "matched_cost_summary.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout="constrained")
    colors = ["#1b78b8", "#697586"]
    for ax, start, title in zip(axes, ["1980-01-01", "2005-01-01"], ["1980–2014", "2005–2014"]):
        sample = net.loc[start:].dropna()
        logwealth = np.log1p(sample).cumsum()
        calendar = pd.period_range(sample.index.min().to_period("M"), sample.index.max().to_period("M"), freq="M")
        logwealth.index = logwealth.index.to_period("M")
        logwealth = logwealth.reindex(calendar)
        logwealth.index = calendar.to_timestamp("M")
        for name, color in zip(sample.columns, colors):
            ax.plot(logwealth.index, logwealth[name], label=name, color=color, linewidth=1.8)
        ax.set_title(title)
        ax.set_ylabel("Log compounded net wealth")
        ax.grid(alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("Different momentum strategies — matched 10 bps trading costs", fontsize=15)
    fig.supxlabel("Monthly rebalance; same retained months. TSMOM uses risk scaling; XSMOM uses unit gross.\n"
                  "Gaps are missing-return months. Post-2014 data are unavailable locally. No roll costs included.", fontsize=9)
    fig.savefig(OUT / "strategy_definition_comparison.png", dpi=180)
    native = economic_backtest(tsmom, r)
    print("Native economic_trend.py baseline, 1980–2014 (2 bps trades plus rolls):")
    print(evaluate(native.net.loc["1980-01-01":]))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
