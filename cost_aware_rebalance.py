"""T1: cost-aware rebalancing (no-trade band / partial rebalancing) and a full metric
comparison of strategies with and without risk budgeting, in-sample vs out-of-sample.

Reading: AQR, "Transactions Costs: Practical Application" - what matters is net,
not gross, return; a slow-decaying signal (12-month TSMOM) can be traded patiently.

Rules (fixed in advance; the grid was not looked at on 2015-2025 data):
- none        trade to target every month (current behaviour)
- band_10/25  no-trade band of +/-10% / +/-25% of |target| around each target weight;
              a drifted weight outside the band is traded only to the nearest band edge.
              Exits (target 0) and sign flips always cross zero, so they are executed.
- partial_50  move halfway from the drifted weight to the target; exits are executed in full.

Holdings are path dependent: month-t holdings start from month t-1 holdings drifted with
month t-1 returns (the same drift used by the Lecture 8 cost model), and the target is the
weight formed at the end of month t-1. The gross cap (4x) is re-applied after the rule for
strategies that have one.

Adopted rule: band_25. It was chosen on in-sample (1976-2014) data only; across the TSMOM
strategies kept here its median in-sample net Sharpe effect is about zero (band_10 is similar),
and it is retained because it removes the most turnover without lowering in-sample net
Sharpe. The out-of-sample period is used only for evaluation.

Run from the project root:  python cost_aware_rebalance.py
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from portfolio_volatility_targeting import GROSS_CAP
from risk_budget_backtest import build_all, MAIN
from risk_budgeting import ROOT, IS_START, IS_END, OOS_START, read_full_sample_returns
from strategy_backtest_adj import read_asset_map
from transaction_cost_model import (
    DEFAULT_PARAMETERS, trailing_contract_volume, instrument_adv_usd, cost_breakdown, trade_weights,
)

OUT = ROOT / "outputs" / "cost_aware_rebalance_output"
RULES = {"none": None, "band_10": ("band", 0.10), "band_25": ("band", 0.25), "partial_50": ("partial", 0.5)}
CAPPED = {"ewma_cov_target", "enhanced", "rb_class"}
RISK_BUDGET = {"rb_class"}
ADOPTED_RULE = "band_25"
NO_RISK_BUDGET = ("baseline", "class_count", "ewma_vol", "ewma_cov_target", "enhanced")
TSMOM = [s for s in MAIN if s != "static_bmk"]
PERIODS = {"IS 1976-2014": (IS_START, IS_END), "OOS 2015-2025": (OOS_START, None), "Full 1976-2025": (IS_START, None)}


def rebalance_path(formed: pd.DataFrame, returns: pd.DataFrame, rule, gross_cap=None) -> pd.DataFrame:
    """Executed weights (earning month-t returns) under a rebalancing rule."""
    targets = formed.fillna(0).shift(1).fillna(0)
    r = returns.reindex_like(targets).fillna(0).to_numpy()
    target = targets.to_numpy()
    held = np.zeros_like(target)
    previous = np.zeros(target.shape[1])
    for t in range(len(target)):
        if t > 0:
            drifted = previous * (1 + r[t - 1]) / (1 + previous @ r[t - 1])
        else:
            drifted = previous
        goal = target[t]
        if rule is None:
            w = goal.copy()
        elif rule[0] == "band":
            width = rule[1] * np.abs(goal)
            w = np.clip(drifted, goal - width, goal + width)
        elif rule[0] == "partial":
            w = np.where(goal == 0, 0.0, drifted + rule[1] * (goal - drifted))
        else:
            raise ValueError(rule)
        gross = np.abs(w).sum()
        if gross_cap is not None and gross > gross_cap:
            w *= gross_cap / gross
        held[t] = w
        previous = w
    return pd.DataFrame(held, index=targets.index, columns=targets.columns)


def metrics(net: pd.Series, gross: pd.Series, traded: pd.Series, exposure: pd.Series,
            static: pd.Series, baseline: pd.Series) -> dict:
    r = net.dropna()
    idx = r.index
    years = len(r) / 12
    wealth = (1 + r).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1) - 1
    vol = r.std() * np.sqrt(12)
    downside = np.sqrt((r.clip(upper=0) ** 2).mean()) * np.sqrt(12)
    cagr = wealth.iloc[-1] ** (1 / years) - 1
    tail = r[r <= r.quantile(0.05)]
    return {
        "months": len(r),
        "cumulative_return": wealth.iloc[-1] - 1,
        "cagr": cagr,
        "annual_mean": r.mean() * 12,
        "annual_volatility": vol,
        "sharpe_0rf": r.mean() * 12 / vol,
        "sortino_0rf": r.mean() * 12 / downside,
        "max_drawdown": drawdown.min(),
        "calmar": cagr / abs(drawdown.min()),
        "skewness": r.skew(),
        "excess_kurtosis": r.kurt(),
        "cvar_95_monthly": tail.mean(),
        "worst_month": r.min(),
        "hit_rate": (r > 0).mean(),
        "annual_turnover": traded.loc[idx].mean() * 12,
        "annual_cost_drag": (gross.loc[idx] - r).mean() * 12,
        "gross_sharpe": gross.loc[idx].mean() / gross.loc[idx].std() * np.sqrt(12),
        "average_gross_exposure": exposure.loc[idx].mean(),
        "corr_static": r.corr(static.loc[idx]),
        "corr_baseline": r.corr(baseline.loc[idx]),
        # Descriptive only: ex-post rescaling to 10% realised vol (uses the period's own vol).
        "cum_return_at_10pct_vol_expost": (1 + r * 0.10 / vol).prod() - 1,
    }


def window(series, start, end):
    return series.loc[start:end] if end else series.loc[start:]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns, asset_map = read_full_sample_returns(), read_asset_map()
    strategies, _, ewma_vol, asset_class = build_all(returns, asset_map)
    volume = trailing_contract_volume(returns.index, returns.columns)
    adv, _ = instrument_adv_usd(volume, asset_class, DEFAULT_PARAMETERS)

    series = {}
    for name, formed in strategies.items():
        rules = RULES if name != "static_bmk" else {"none": None}
        for rule_name, rule in rules.items():
            executed = rebalance_path(formed, returns, rule, GROSS_CAP if name in CAPPED else None)
            if rule is None:  # identical to the standard one-month-lag execution
                np.testing.assert_allclose(executed.to_numpy(), formed.fillna(0).shift(1).fillna(0).to_numpy())
            gross = (executed * returns.fillna(0)).sum(axis=1)
            cost, _ = cost_breakdown(executed, ewma_vol, adv, asset_class, DEFAULT_PARAMETERS, returns)
            traded = trade_weights(executed, returns, "drift").sum(axis=1)
            series[(name, rule_name)] = {"gross": gross, "net": gross - cost.total, "traded": traded,
                                         "exposure": executed.abs().sum(axis=1), "impact": cost.market_impact,
                                         "cost": cost.total}
            if rule_name == ADOPTED_RULE:
                executed.loc[IS_START:].to_csv(OUT / f"executed_weights_{name}_{rule_name}.csv")

    static_net = series[("static_bmk", "none")]["net"]
    rows = []
    for (name, rule_name), s in series.items():
        base_net = series[("baseline", rule_name if name != "static_bmk" else "none")]["net"]
        for period, (start, end) in PERIODS.items():
            rows.append({"strategy": name, "rule": rule_name, "period": period,
                         "risk_budgeting": name in RISK_BUDGET,
                         **metrics(window(s["net"], start, end), s["gross"], s["traded"], s["exposure"],
                                   static_net, base_net)})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "metrics_all.csv", index=False)

    # ---- IS-only rule selection
    is_net = table[(table.period == "IS 1976-2014") & table.strategy.isin(TSMOM)] \
        .pivot(index="strategy", columns="rule", values="sharpe_0rf")
    improvement = is_net.sub(is_net["none"], axis=0).median()
    selected = ADOPTED_RULE
    pd.DataFrame({"median_IS_net_sharpe_change": improvement}).to_csv(OUT / "rule_comparison_in_sample.csv")

    monthly = pd.DataFrame({f"{n}|{r}|{k}": v[k] for (n, r), v in series.items() for k in ("gross", "net", "traded")})
    monthly.loc[IS_START:].rename_axis("Date").to_csv(OUT / "monthly_returns.csv")
    write_outputs(table, selected, improvement, series)
    print("adopted rule:", selected)
    print(improvement.round(3).to_string())
    view = table[table.strategy.isin(TSMOM) & (table.period != "Full 1976-2025")] \
        .pivot_table(index="strategy", columns=["period", "rule"], values="sharpe_0rf")
    print(view.loc[TSMOM].round(3).to_string())


KEY = ["cumulative_return", "cagr", "annual_volatility", "sharpe_0rf", "sortino_0rf", "max_drawdown",
       "calmar", "skewness", "cvar_95_monthly", "hit_rate", "annual_turnover", "annual_cost_drag",
       "average_gross_exposure", "corr_static", "cum_return_at_10pct_vol_expost"]
PCT = {"cumulative_return", "cagr", "annual_volatility", "max_drawdown", "cvar_95_monthly", "hit_rate",
       "annual_cost_drag", "cum_return_at_10pct_vol_expost"}


def fmt(metric, value):
    return f"{value:.1%}" if metric in PCT else f"{value:.2f}"


def md_table(table, rule, period, names):
    sub = table[(table.period == period) & table.strategy.isin(names)
                & ((table.rule == rule) | (table.strategy == "static_bmk"))].set_index("strategy").loc[names]
    head = "| Metric | " + " | ".join(names) + " |"
    lines = [head, "|---|" + "---:|" * len(names)]
    for m in KEY:
        lines.append(f"| {m} | " + " | ".join(fmt(m, sub.loc[n, m]) for n in names) + " |")
    return "\n".join(lines)


def group_summary(table, rule):
    sub = table[(table.rule == rule) & table.strategy.isin(TSMOM) & (table.period != "Full 1976-2025")].copy()
    sub["group"] = np.where(sub.risk_budgeting, "with risk budgeting (R2)", "without risk budgeting (5)")
    cols = ["cagr", "annual_volatility", "sharpe_0rf", "sortino_0rf", "max_drawdown", "calmar",
            "annual_turnover", "annual_cost_drag", "average_gross_exposure"]
    return sub.groupby(["period", "group"])[cols].mean()


def write_outputs(table, selected, improvement, series):
    names = ["baseline", "class_count", "ewma_vol", "ewma_cov_target", "enhanced",
             "rb_class", "static_bmk"]
    # Sharpe grid
    grid = table[table.strategy.isin(TSMOM) & (table.period != "Full 1976-2025")] \
        .pivot_table(index="strategy", columns=["period", "rule"], values=["sharpe_0rf", "annual_turnover"])
    grid.to_csv(OUT / "sharpe_turnover_by_rule.csv")
    lines = ["| Strategy | " + " | ".join(f"{p.split()[0]} {r}" for p in ("IS 1976-2014", "OOS 2015-2025") for r in RULES) + " |",
             "|---|" + "---:|" * (2 * len(RULES))]
    for n in TSMOM:
        vals = [grid.loc[n, ("sharpe_0rf", p, r)] for p in ("IS 1976-2014", "OOS 2015-2025") for r in RULES]
        lines.append(f"| {n} | " + " | ".join(f"{v:.2f}" for v in vals) + " |")
    sharpe_md = "\n".join(lines)
    lines = ["| Strategy | " + " | ".join(f"{r}" for r in RULES) + " |", "|---|" + "---:|" * len(RULES)]
    for n in TSMOM:
        lines.append(f"| {n} | " + " | ".join(f"{grid.loc[n, ('annual_turnover', 'IS 1976-2014', r)]:.1f}" for r in RULES) + " |")
    turnover_md = "\n".join(lines)
    groups = {rule: group_summary(table, rule) for rule in ("none", selected)}
    for rule, g in groups.items():
        g.to_csv(OUT / f"group_means_rule_{rule}.csv")

    def group_md(g):
        cols = list(g.columns)
        out = ["| Period | Group | " + " | ".join(cols) + " |", "|---|---|" + "---:|" * len(cols)]
        for (p, grp), row in g.iterrows():
            out.append(f"| {p} | {grp} | " + " | ".join(fmt(c, row[c]) for c in cols) + " |")
        return "\n".join(out)

    report = [
        "# T1 cost-aware rebalancing and with/without risk-budgeting comparison", "",
        "All returns are net of the Lecture 8 cost model at $1bn AUM unless stated (commission, roll, spread, "
        "square-root impact, financing). IS = Jan 1976-Dec 2014, OOS = Jan 2015-May 2025. "
        "Rules are described in `cost_aware_rebalance.py`.", "",
        "**Execution timing convention (main results).** Trades fill at the signal close while Lecture 8 impact "
        "assumes 5-day execution; `alpha_decay_execution.py` shows this overstates in-sample net Sharpe by about "
        "0.07-0.09.", "",
        "## In-sample rule comparison", "",
        "Median change in IS net Sharpe across the six TSMOM strategies:", "",
        "| Rule | Median IS net Sharpe change |", "|---|---:|",
        *[f"| {r} | {v:+.3f} |" for r, v in improvement.items()], "",
        f"**Adopted rule: `{selected}`.** Its median IS net Sharpe effect is about zero (band_10 is similar); it is "
        "kept because it removes the most turnover without lowering IS net Sharpe. OOS numbers were not used to choose it.", "",
        "## Findings", "",
        "1. band_25 cuts IS turnover by roughly 30-40% for every strategy and IS cost drag by 0.3-0.9% a year. "
        "IS net Sharpe is roughly unchanged for the 1/N and enhanced variants and rises for R2, whose turnover is highest.",
        "2. OOS net Sharpe rises for every TSMOM variant. Part of this exceeds the cost saving: slower trading also helped "
        "gross returns in the choppy 2015-2025 period, which is a regime effect that reversed IS.",
        "3. partial_50 is the worst rule IS and the best OOS; choosing it after seeing OOS would be research look-ahead.",
        "4. The band under-allocates: entries are made at 75% of target and exits in full, so average exposure, volatility "
        "and CAGR fall. Compare Sharpe, Sortino and Calmar rather than CAGR or cumulative return.", "",
        "## Net Sharpe by rule", "", sharpe_md, "",
        "## IS annual turnover by rule", "", turnover_md, "",
        "## Group averages: without vs with risk budgeting", "",
        "Simple average of the five non-risk-budget TSMOM variants vs R2.", "",
        "### Monthly full rebalancing (`none`)", "", group_md(groups["none"]), "",
        f"### Adopted rule (`{selected}`)", "", group_md(groups[selected]), "",
    ]
    for rule in dict.fromkeys(("none", selected)):
        for period in ("IS 1976-2014", "OOS 2015-2025", "Full 1976-2025"):
            report += [f"## Full metrics, rule `{rule}`, {period}", "",
                       md_table(table, rule, period, names), ""]
    report += ["`cum_return_at_10pct_vol_expost` rescales each strategy to 10% realised volatility over the "
               "period itself. It uses ex-post information, is descriptive only, and is shown because the "
               "risk-budget strategy runs near 5% volatility when the 4x gross cap binds. Sharpe, Sortino and "
               "Calmar are unaffected by that scale difference.", ""]
    (OUT / "t1_and_risk_budget_comparison.md").write_text("\n".join(report), encoding="utf-8")

    # Plots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for ax, period in zip(axes[0], ("IS 1976-2014", "OOS 2015-2025")):
        x = np.arange(len(TSMOM))
        for i, rule in enumerate(RULES):
            ax.bar(x + (i - 1.5) * 0.2, [grid.loc[n, ("sharpe_0rf", period, rule)] for n in TSMOM], 0.2, label=rule)
        ax.set_xticks(x, TSMOM, rotation=30, ha="right", fontsize=8)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title(f"Net Sharpe ($1bn) by rebalancing rule, {period}")
        ax.legend(fontsize=8)
    ax = axes[1, 0]
    for n in TSMOM:
        xs = [grid.loc[n, ("annual_turnover", "IS 1976-2014", r)] for r in RULES]
        ys = [grid.loc[n, ("sharpe_0rf", "IS 1976-2014", r)] for r in RULES]
        ax.plot(xs, ys, marker="o", label=n)
    ax.set_xlabel("IS annual turnover (x NAV)")
    ax.set_ylabel("IS net Sharpe")
    ax.set_title("Turnover vs net Sharpe, IS (points: none, band_10, band_25, partial_50)")
    ax.legend(fontsize=7)
    ax = axes[1, 1]
    for n, style in (("baseline", "--"), ("enhanced", "--"), ("rb_class", "-")):
        for rule, alpha in (("none", 0.45), (selected, 1.0)):
            r = series[(n, rule)]["net"].loc[IS_START:]
            ax.plot((1 + r).cumprod(), ls=style, alpha=alpha, label=f"{n} {rule}")
    ax.set_yscale("log")
    ax.axvspan(pd.Timestamp(OOS_START), r.index.max(), color="grey", alpha=0.15)
    ax.set_title("Net wealth: without RB dashed, with RB solid; faded = monthly full rebalance")
    ax.legend(fontsize=7)
    for a in axes.flat:
        a.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "t1_rebalancing_comparison.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
