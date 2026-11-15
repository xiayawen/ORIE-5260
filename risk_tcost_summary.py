"""Summary of the R1/R2/T1/T3 work: one table and one figure from saved outputs.

Run after risk_budget_backtest.py, cost_aware_rebalance.py and
alpha_decay_execution.py. All returns are net of the Lecture 8 cost model at $1bn
under the monthly execution convention (see README: execution timing).
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from risk_budgeting import ROOT, OOS_START

OUTPUTS = ROOT / "outputs"
OUT = OUTPUTS / "risk_tcost_summary_output"
CONFIGS = [  # (strategy, rule, label)
    ("baseline", "none", "Baseline"),
    ("enhanced", "none", "Enhanced"),
    ("rb_class", "none", "R2 risk budget"),
    ("baseline", "band_25", "Baseline + T1"),
    ("enhanced", "band_25", "Enhanced + T1"),
    ("rb_class", "band_25", "R2 + T1"),
    ("static_bmk", "none", "Static long"),
]
PERIODS = ("IS 1976-2014", "OOS 2015-2025", "Full 1976-2025")
COLORS = ["#1f4e79", "#2e8b57", "#b8860b", "#6fa8dc", "#93c47d", "#e69138", "#999999"]


def build_table():
    m = pd.read_csv(OUTPUTS / "cost_aware_rebalance_output" / "metrics_all.csv")
    rows = []
    for strategy, rule, label in CONFIGS:
        for period in PERIODS:
            r = m[(m.strategy == strategy) & (m.rule == rule) & (m.period == period)].iloc[0]
            rows.append({
                "configuration": label, "period": period,
                "net_cagr": r.cagr,
                "avg_annual_gross_return": r.annual_mean + r.annual_cost_drag,
                "avg_annual_net_return": r.annual_mean,
                "annual_volatility": r.annual_volatility,
                "net_sharpe": r.sharpe_0rf, "gross_sharpe": r.gross_sharpe,
                "sortino": r.sortino_0rf, "max_drawdown": r.max_drawdown, "calmar": r.calmar,
                "annual_turnover": r.annual_turnover, "annual_cost_drag": r.annual_cost_drag,
                "avg_gross_exposure": r.average_gross_exposure,
                "cumulative_net_return": r.cumulative_return,
            })
    return pd.DataFrame(rows)


def markdown(table):
    pct = {"net_cagr", "avg_annual_gross_return", "avg_annual_net_return", "annual_volatility",
           "max_drawdown", "annual_cost_drag", "cumulative_net_return"}
    cols = ["net_cagr", "avg_annual_gross_return", "avg_annual_net_return", "annual_volatility",
            "net_sharpe", "gross_sharpe", "max_drawdown", "calmar", "annual_turnover", "annual_cost_drag",
            "avg_gross_exposure", "cumulative_net_return"]
    out = []
    for period in PERIODS:
        out += [f"### {period}", "", "| Configuration | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
        for _, r in table[table.period == period].iterrows():
            out.append(f"| {r.configuration} | " + " | ".join(
                f"{r[c]:.1%}" if c in pct else f"{r[c]:.2f}" for c in cols) + " |")
        out.append("")
    return "\n".join(out)


def figure(table):
    monthly = pd.read_csv(OUTPUTS / "cost_aware_rebalance_output" / "monthly_returns.csv", index_col=0, parse_dates=True)
    fig, axes = plt.subplots(2, 3, figsize=(20, 11))
    labels = [c[2] for c in CONFIGS]

    ax = axes[0, 0]
    for (s, rule, label), color in zip(CONFIGS, COLORS):
        r = monthly[f"{s}|{rule}|net"]
        ax.plot((1 + r).cumprod(), color=color, lw=1.8 if "T1" in label else 1.1,
                ls="-" if "T1" in label or s == "static_bmk" else "--", label=label)
    ax.set_yscale("log")
    ax.axvspan(pd.Timestamp(OOS_START), monthly.index.max(), color="grey", alpha=0.15)
    ax.set_title("A. Growth of \\$1, net of costs (\\$1bn), log scale\nshaded = out-of-sample 2015-2025")
    ax.legend(fontsize=8, ncol=2)

    def bars(ax, metric, title, fmt_pct=False):
        x = np.arange(len(labels))
        for i, period in enumerate(PERIODS[:2]):
            v = table[table.period == period].set_index("configuration").loc[labels, metric]
            b = ax.bar(x + (i - 0.5) * 0.38, v, 0.38, label=period,
                       color=["#1f4e79", "#e69138"][i])
            for rect, val in zip(b, v):
                ax.annotate(f"{val:.0%}" if fmt_pct else f"{val:.2f}",
                            (rect.get_x() + rect.get_width() / 2, val), ha="center",
                            va="bottom" if val >= 0 else "top", fontsize=7)
        ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=8)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title(title)
        ax.legend(fontsize=8)
        if fmt_pct:
            ax.yaxis.set_major_formatter(PercentFormatter(1))

    bars(axes[0, 1], "net_sharpe", "B. Net Sharpe (RF = 0): in-sample vs out-of-sample")
    bars(axes[0, 2], "max_drawdown", "C. Maximum drawdown", fmt_pct=True)

    ax = axes[1, 0]
    t = table[table.period == "IS 1976-2014"].set_index("configuration").loc[labels]
    x = np.arange(len(labels))
    ax.bar(x, t.annual_turnover, color=COLORS)
    ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Annual turnover (x NAV)")
    ax2 = ax.twinx()
    ax2.plot(x, t.annual_cost_drag * 1e4, "ko-", label="cost drag (bps/yr)")
    ax2.set_ylabel("Cost drag, bps per year")
    ax2.legend(fontsize=8, loc="upper left")
    ax.set_title("D. In-sample turnover (bars) and Lecture 8 cost drag (line)")

    ax = axes[1, 1]
    diag = pd.read_csv(OUTPUTS / "baseline_risk_analysis_output" / "diagonal_vs_covariance_class_risk.csv")
    classes = ["COMM", "EQ", "FI", "FX"]
    views = {"Baseline\ndiagonal": "diagonal", "Baseline\nEWMA cov (R1)": "cov_ewma"}
    shares = {k: diag[diag.model == v].set_index("asset_class").average_risk_share for k, v in views.items()}
    ex = pd.read_csv(OUTPUTS / "risk_budget_output" / "exante_class_risk_share.csv")
    for label, period in (("R2 risk budget\nIS ex-ante", "in_sample_1976_2014"),
                          ("R2 risk budget\nOOS ex-ante", "out_of_sample_2015_2025")):
        shares[label] = ex[(ex.strategy == "rb_class") & (ex.period == period)].set_index("strategy")[classes].iloc[0]
    bottom = np.zeros(len(shares))
    for c, color in zip(classes, ["#b8860b", "#1f4e79", "#2e8b57", "#a64d79"]):
        vals = np.array([float(sh[c]) for sh in shares.values()])
        ax.bar(list(shares), vals, bottom=bottom, color=color, label=c)
        for i, (v, b) in enumerate(zip(vals, bottom)):
            ax.text(i, b + v / 2, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9)
        bottom += vals
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title("E. Share of portfolio risk by asset class (Euler PCR)")
    ax.tick_params(axis="x", labelsize=8)
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08))

    ax = axes[1, 2]
    opt = pd.read_csv(OUTPUTS / "alpha_decay_output" / "optimal_execution_days.csv")
    opt = opt[opt.aum == "$1bn"].set_index("strategy")
    names = {"baseline": "Baseline + T1", "enhanced": "Enhanced + T1", "rb_class": "R2 + T1"}
    monthly_conv = t.loc[list(names.values()), "net_sharpe"]
    x = np.arange(len(names))
    ax.bar(x - 0.2, monthly_conv.values, 0.4, label="monthly convention (close fill, 5-day impact)", color="#6fa8dc")
    feasible = opt.loc[list(names), "best_net_sharpe"].values
    ax.bar(x + 0.2, feasible, 0.4, label="feasible: start next day, best horizon", color="#e69138")
    for i, (a, b, d) in enumerate(zip(monthly_conv.values, feasible, opt.loc[list(names), "best_execution_days"])):
        ax.text(i - 0.2, a, f"{a:.2f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + 0.2, b, f"{b:.2f}\n(D={d})", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, list(names.values()))
    ax.set_ylim(0, 1.2)
    ax.set_title("F. T3: in-sample net Sharpe at \\$1bn under feasible execution")
    ax.legend(fontsize=8, loc="lower right")

    for a in axes.flat:
        a.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "risk_tcost_summary.png", dpi=150)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    table = build_table()
    table.to_csv(OUT / "summary_metrics.csv", index=False)
    (OUT / "summary_metrics.md").write_text(
        "# Summary metrics (net of Lecture 8 costs at $1bn, monthly execution convention)\n\n"
        "T1 = band_25 no-trade band. Enhanced = EWMA instrument volatility + EWMA covariance targeting. R2 = equal (25%) ex-ante risk per asset class. "
        "See README for the execution-timing caveat (T3).\n\n" + markdown(table), encoding="utf-8")
    figure(table)
    print(table[table.period != "Full 1976-2025"].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
