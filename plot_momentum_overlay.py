"""Plot net compounded P&L and drawdowns on common observed months."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "momentum_overlay"


def main():
    returns = pd.read_csv(OUT / "comparison_net_returns.csv", index_col=0, parse_dates=True)
    assert returns.notna().all().all()
    # Mark absent calendar months as gaps rather than interpolate missing P&L.
    periods = returns.index.to_period("M")
    calendar = pd.period_range(periods.min(), periods.max(), freq="M")
    base_date = (periods.min() - 1).to_timestamp("M")
    nav = (1 + returns).cumprod() * 100
    nav.index = periods
    nav = nav.reindex(calendar)
    nav.index = calendar.to_timestamp("M")
    nav.loc[base_date] = 100
    nav = nav.sort_index()
    drawdown = nav.div(nav.cummax().clip(lower=100)) - 1
    names = {
        "Mom": ("Mom", "#697586"),
        "Mom_NegativeSkew_12m_20pct": ("80% Mom + 20% negative skew", "#167d8d"),
        "Mom_EqualDefensiveBasket_20pct": ("80% Mom + 20% defensive basket", "#c7842b"),
    }
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, (ax, dd) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                gridspec_kw={"height_ratios": [2.3, 1]}, layout="constrained")
    for col, (label, color) in names.items():
        last = nav[col].dropna().iloc[-1]
        ax.plot(nav.index, nav[col], color=color, linewidth=2,
                label=f"{label}  |  final {last:.2f}")
        dd.plot(drawdown.index, drawdown[col], color=color, linewidth=1.6)
    missing = calendar.difference(periods)
    for month in missing:
        for panel in (ax, dd):
            panel.axvspan(month.start_time, month.end_time, color="#d5d9df", alpha=.55, linewidth=0)
    ax.axhline(100, color="#b6bcc5", lw=.8)
    ax.set_title("Momentum core + factor overlays", loc="left", fontsize=19, weight="bold", pad=30)
    ax.text(0, 1.025, "2005–2014 | Net of 10 bps per dollar traded | Monthly rebalance | Gross exposure = 1",
            transform=ax.transAxes, color="#526070", fontsize=10)
    ax.set_ylabel("Net wealth (initial = 100)")
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    dd.set_ylabel("Drawdown")
    dd.yaxis.set_major_formatter(PercentFormatter(1))
    dd.xaxis.set_major_locator(mdates.YearLocator(2))
    dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for panel in (ax, dd):
        panel.grid(axis="y", alpha=.18)
    fig.supxlabel("Shaded gaps: 4 missing months; curves compound 116 retained months without filling missing P&L.\n"
                  "80/20 denotes sleeve budgets before netting. Previously inspected comparison period; not a pristine holdout.",
                  fontsize=9, color="#526070")
    fig.savefig(OUT / "net_pnl_comparison.png", dpi=180)
    fig.savefig(OUT / "net_pnl_comparison.pdf")
    nav.to_csv(OUT / "plotted_net_wealth.csv")
    print(((1 + returns).prod() - 1).to_string())


if __name__ == "__main__":
    main()
