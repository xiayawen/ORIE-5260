"""Cost-analysis figure for the enhanced TSMOM strategies (Lecture 8 cost model).

Reads the CSVs written by enhanced_strategy_backtest.py and draws one 2x2 figure:
  A  net Sharpe under each cost assumption (gross -> lecture flat rule -> full model by AUM)
  B  annual cost vs AUM (log-log): square-root impact vs the flat slide-32 rule
  C  where the cost comes from: annual cost by asset class at $1bn
  D  robustness: change in net Sharpe at $1bn when sigma, ADV or execution days change

Run after the backtest, from the project root:

    python enhanced_strategy_backtest.py
    python plot_cost_analysis.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = Path(__file__).resolve().parent / "outputs" / "enhanced_strategy_output"

STRATEGIES = ("baseline", "ewma_vol", "ewma_cov_target", "enhanced")
# Categorical slots 1-4 for strategies (same colour for a strategy in every panel),
# slots 5-8 for asset classes so the two kinds of entity never share a hue.
STRATEGY_COLORS = dict(zip(STRATEGIES, ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")))
CLASSES = ("COMM", "FX", "FI", "EQ")
CLASS_COLORS = dict(zip(CLASSES, ("#e87ba4", "#008300", "#6250d6", "#e34948")))
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

COST_CASES = (("gross", "Gross"), ("flat_2bps", "Flat 2bp\n+ roll"), ("flat_10bps", "Flat 10bp\n+ roll"),
              ("lecture8_$100m", "Model\n$100m"), ("lecture8_$1bn", "Model\n$1bn"),
              ("lecture8_$10bn", "Model\n$10bn"))


def style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK, pad=10)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8.5, length=0)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def label_line_ends(ax, ends, x, dx_points=6):
    """Direct labels at the right end of each line, nudged apart so they never overlap."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.045
    placed = None
    for name, y in sorted(ends.items(), key=lambda kv: kv[1]):
        placed = y if placed is None else max(y, placed + gap)
        ax.annotate(name, (x, placed), xytext=(dx_points, 0), textcoords="offset points",
                    fontsize=8.5, color=INK, va="center")


def panel_sharpe(ax, summary):
    style(ax, "A  Net Sharpe under each cost assumption")
    xs = np.arange(len(COST_CASES))
    ends = {}
    for name in STRATEGIES:
        s = summary[summary.strategy == name].set_index("costs").sharpe_0rf
        y = [s[c] for c, _ in COST_CASES]
        ax.plot(xs, y, color=STRATEGY_COLORS[name], lw=2, marker="o", ms=6,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=name)
        ends[name] = y[-1]
    ax.set_xticks(xs, [lbl for _, lbl in COST_CASES])
    ax.set_xlim(-0.3, len(xs) - 1 + 1.25)
    ax.set_ylabel("Sharpe ratio (RF = 0)")
    ax.axvspan(0.5, 2.5, color=GRID, alpha=0.35, lw=0)
    ax.text(1.5, ax.get_ylim()[1], "Lecture 8\nslide 32 rule", ha="center", va="top", fontsize=8, color=INK_2)
    label_line_ends(ax, ends, xs[-1])
    ax.legend(loc="lower left", fontsize=8, frameon=False)


def panel_capacity(ax, capacity, flat_cost_bps):
    style(ax, "B  Annual cost vs AUM: impact grows ~ √AUM")
    ends = {}
    for name in STRATEGIES:
        c = capacity[capacity.strategy == name].sort_values("aum_usd")
        bps = c.annual_total_cost * 1e4
        ax.plot(c.aum_usd, bps, color=STRATEGY_COLORS[name], lw=2, marker="o", ms=5,
                markeredgecolor=SURFACE, markeredgewidth=1.2, label=name)
        ends[name] = bps.iloc[-1]
    lo, hi = min(flat_cost_bps.values()), max(flat_cost_bps.values())
    ax.axhspan(lo, hi, color=INK_2, alpha=0.15, lw=0)
    ax.text(1.5e9, hi * 0.97, f"Flat 2bp + roll: {lo:.0f}–{hi:.0f} bps/yr\n(slide 32 rule, no AUM effect)",
            fontsize=8, color=INK_2, va="top")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_yticks([20, 50, 100, 200, 500, 1000])
    ax.minorticks_off()
    ax.set_ylim(20, 1600)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1e9:g}bn" if v >= 1e9 else f"${v/1e6:g}m"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("AUM (USD, log scale)")
    ax.set_ylabel("Total cost, bps per year (log scale)")
    ax.set_xlim(right=capacity.aum_usd.max() * 6)
    placed = None
    for name, y in sorted(ends.items(), key=lambda kv: kv[1]):  # nudge apart in log space
        placed = y if placed is None else max(y, placed * 1.2)
        ax.annotate(name, (capacity.aum_usd.max(), placed), xytext=(6, 0), textcoords="offset points",
                    fontsize=8.5, color=INK, va="center")
    ax.legend(loc="upper left", fontsize=8, frameon=False)


def panel_asset_class(ax, by_class):
    style(ax, "C  Where the cost comes from ($1bn, bps per year)")
    sel = (by_class[by_class.aum_usd == 1e9].pivot(index="strategy", columns="asset_class", values="annual_cost")
           .reindex(index=list(STRATEGIES)[::-1], columns=list(CLASSES)) * 1e4)
    left = np.zeros(len(sel))
    ys = np.arange(len(sel))
    for cls in CLASSES:
        widths = sel[cls].to_numpy()
        ax.barh(ys, widths, left=left, height=0.6, color=CLASS_COLORS[cls], edgecolor=SURFACE,
                linewidth=2, label=cls)
        for y, l, w in zip(ys, left, widths):
            if w >= 12:
                ax.text(l + w / 2, y, f"{w:.0f}", ha="center", va="center", fontsize=8, color="white",
                        fontweight="bold")
        left += widths
    for y, total, name in zip(ys, left, sel.index):
        share = sel.loc[name, "COMM"] / total
        ax.text(total + 2, y, f"{total:.0f}  (COMM {share:.0%})", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(ys, sel.index)
    ax.set_xlim(0, left.max() * 1.35)
    ax.set_xlabel("bps per year (commission + roll + spread + impact)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper right", fontsize=8, frameon=False, ncol=2, title="Asset class", title_fontsize=8)


def panel_robustness(ax, sensitivity, execution):
    style(ax, "D  Robustness: change in net Sharpe vs base ($1bn)")
    base = sensitivity[sensitivity.case.str.startswith("base")].set_index("strategy").sharpe_0rf
    rows = []
    for case in ("sigma = expanding vol", "ADV x0.5", "ADV x2"):
        s = sensitivity[sensitivity.case == case].set_index("strategy").sharpe_0rf
        rows.append((case.replace("sigma", "σ").replace(" x", " × "), s - base))
    ex = execution.set_index(["execution_days", "strategy"]).sharpe_0rf
    for days, label in ((1, "Execute in 1 day"), (21, "Execute over 21 days")):
        rows.append((label, ex.loc[days] - ex.loc[5]))
    ys = np.arange(len(rows))[::-1]
    offsets = np.linspace(-0.24, 0.24, len(STRATEGIES))
    for (label, delta), y in zip(rows, ys):
        ax.plot([delta[list(STRATEGIES)].min(), delta[list(STRATEGIES)].max()], [y, y], color=GRID, lw=6,
                solid_capstyle="round", zorder=1)
    for off, name in zip(offsets, STRATEGIES):
        ax.scatter([d[name] for _, d in rows], ys + off, s=46, color=STRATEGY_COLORS[name],
                   edgecolor=SURFACE, linewidth=1.5, zorder=3, label=name)
    ax.axvline(0, color=INK_2, lw=1)
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.set_xlabel("Δ net Sharpe (base: EWMA σ, class ADV, 5 execution days)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ranks_same = all((d[list(STRATEGIES)] + base[list(STRATEGIES)]).rank().equals(base[list(STRATEGIES)].rank())
                     for _, d in rows[:3])
    note = "Strategy ranking unchanged in every σ/ADV case" if ranks_same else "Ranking changes in some cases"
    ax.text(0.01, 0.99, note, transform=ax.transAxes, fontsize=8, color=INK_2, va="top")


def main():
    summary = pd.read_csv(OUT / "performance_summary.csv")
    capacity = pd.read_csv(OUT / "capacity_curve.csv")
    by_class = pd.read_csv(OUT / "cost_by_asset_class.csv")
    sensitivity = pd.read_csv(OUT / "cost_input_sensitivity.csv")
    execution = pd.read_csv(OUT / "execution_days_sensitivity.csv")
    monthly = pd.read_csv(OUT / "monthly_returns_and_costs.csv", index_col=0)
    flat_cost_bps = {n: (monthly[f"{n}_gross"] - monthly[f"{n}_flat_2bps"]).mean() * 12 * 1e4 for n in STRATEGIES}

    fig, axes = plt.subplots(2, 2, figsize=(15, 10.5), facecolor=SURFACE)
    panel_sharpe(axes[0, 0], summary)
    panel_capacity(axes[0, 1], capacity, flat_cost_bps)
    panel_asset_class(axes[1, 0], by_class)
    panel_robustness(axes[1, 1], sensitivity, execution)
    fig.suptitle("Transaction-cost analysis: Lecture 8 model, Jan 1976 – Dec 2014",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.5, w_pad=3)
    fig.savefig(OUT / "cost_analysis.png", dpi=180, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {OUT / 'cost_analysis.png'}")


if __name__ == "__main__":
    main()
