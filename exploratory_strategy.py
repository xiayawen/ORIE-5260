"""Exploratory strategies: tested, but not selected by the in-sample rule.

Each row is the final strategy (enhanced + continuous signal) with something added. None of them passed
the in-sample selection rule (or, for half-short, the rule was designed after seeing 2015-2025 data), so
their out-of-sample numbers are information, not evidence. This module is the single source for these rows:
summary_table.py imports the definitions and evaluation helpers from here, so both outputs always match.

All rows use combined_strategy.Pipeline on MonthlyReturns_FullSample.xlsx, net of the Lecture 11
convention (2 bps per unit turnover + 4 rolls/yr at 2 bps). IS = Jan 1976 - Dec 2014, OOS = Jan 2015 -
May 2025. Needs MonthlyReturns_FullSample.xlsx and macro_data/ in the project folder.

    python exploratory_strategy.py
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import pandas as pd

from combined_strategy import ROOT, ALL_COMPONENTS_CONTINUOUS, POST_2015_DESIGN, Pipeline, stats
from risk_budgeting import IS_START, IS_END, OOS_START, read_full_sample_returns

OUT = ROOT / "outputs" / "exploratory_strategy_output"
FINAL = frozenset({"continuous_signal"})
PERIODS = (("IS", (IS_START, IS_END)), ("OOS", (OOS_START, None)))

# (tier, key, short name, component set, cost convention)
REFERENCE_ROW = ("Reference", "final", "Final: enhanced + continuous signal", FINAL, "slide_2bps")
EXPLORATORY_ROWS = [
    ("Exploratory", "final_histgb", "Final + HistGB sleeve", FINAL | {"histgb_overlay"}, "slide_2bps"),
    ("Exploratory", "final_band", "Final + no-trade band (band_25)", FINAL | {"band_25"}, "slide_2bps"),
    ("Exploratory", "final_half_short", "Final + half-short †", FINAL | {"half_short"}, "slide_2bps"),
    ("Exploratory", "all_clean", "All clean candidates (continuous core)",
     ALL_COMPONENTS_CONTINUOUS - POST_2015_DESIGN, "slide_2bps"),
]

METRICS = [("annual_net_return", "Net ret", "{:.1%}"), ("annual_volatility", "Vol", "{:.1%}"),
           ("net_sharpe", "Sharpe", "{:.2f}"), ("max_drawdown", "Max DD", "{:.1%}"),
           ("average_gross_exposure", "Leverage", "{:.1f}x"), ("average_net_exposure", "Imbalance", "{:+.1f}x"),
           ("annual_turnover", "Turnover", "{:.1f}"), ("annual_cost_drag", "Cost", "{:.2%}")]

EXPLORATORY_EXPLANATIONS = {
    "final_histgb": """**What it is.** The final strategy plus a 30% sleeve from a gradient-boosted tree model that predicts each
market's next-month direction from about 60 price-based features. The model is refit every year on the
previous 15 years only (walk-forward), so its forecasts never use future data.

**Why it is exploratory.** It slightly lowered in-sample Sharpe (1.11 vs 1.13), so the selection rule
correctly left it out. Its out-of-sample Sharpe (0.31, coincidentally the same as slide 30's baseline) was not
predictable from in-sample evidence; adopting it now would mean choosing on out-of-sample results. It is the
most promising direction for future work, to be validated on data after May 2025.""",

    "final_band": """**What it is.** The final strategy plus a no-trade band: a position is only traded when it drifts more
than 25% away from its target, and then only back to the band edge (Lecture 8: trade off alpha against costs).

**Why it is exploratory.** It cuts turnover, but on top of the continuous signal it lowered in-sample Sharpe,
so the rule rejected it. The continuous signal already shrinks weak positions, and the band then keeps
positions further below target. It looks better out of sample, when trading less helped in a choppy decade;
that is a regime effect, not evidence for the rule.""",

    "final_half_short": """**What it is.** The final strategy with every short position halved (longs unchanged).

**Why it is exploratory (†).** The rule was designed by the team after seeing that shorts lost money in
2015-2025, so its out-of-sample number is not a clean test. It also raises the net long position, i.e. more
equity-market exposure, which works against trend-following's role as crisis protection.""",

    "all_clean": """**What it is.** The continuous-signal strategy with every compatible candidate that was designed
before 2015 switched on at once: economic-trend, factor and HistGB sleeves, turning-point reduction,
net-exposure cap and the no-trade band. Half-short and the smoothing rules are left out because they were
designed after seeing 2015-2025 data. With all three sleeves active (from 1997, when HistGB starts) the trend
core is only 30% of the mix (economic trend 20%, factor 20%, HistGB 30%); before 1997 it is 60%. The
turning-point cut and the net cap then remove exposure after the mix is re-targeted to 10%.

**Why it is exploratory.** It is clearly worse in-sample (0.93 vs 1.13 Sharpe), a gap large enough to be a real
result rather than noise. Its higher out-of-sample Sharpe comes from lower risk, not more return: the overlays
keep shrinking the book (leverage about 2.3x, volatility about 4%), so net return is no higher than the final
strategy's. Including the post-2015 rules as well gives almost the same out-of-sample Sharpe (0.22), so the
effect is not driven by them.""",
}


def evaluate_rows(pipe, rows, series=None):
    """IS and OOS statistics for each row; `series` supplies precomputed results for rows without a config."""
    series = series or {}
    out = []
    for tier, key, name, config, convention in rows:
        result = series[key] if key in series else pipe.run(config)
        for period, (start, end) in PERIODS:
            out.append({"tier": tier, "key": key, "strategy": name, "costs": convention, "period": period,
                        **stats(result, start, end, convention)})
    return pd.DataFrame(out)


def markdown_rows(table, rows):
    """Markdown table: one line per row, IS and OOS side by side for every metric."""
    lines = ["| Tier | Strategy | " + " | ".join(f"IS {m[1]} | OOS {m[1]}" for m in METRICS) + " |",
             "|---|---|" + "---:|" * (2 * len(METRICS))]
    for tier, key, name, _, _ in rows:
        a = table[(table.key == key) & (table.period == "IS")].iloc[0]
        b = table[(table.key == key) & (table.period == "OOS")].iloc[0]
        lines.append(f"| {tier} | {name} | " + " | ".join(f"{f.format(a[k])} | {f.format(b[k])}"
                                                           for k, _, f in METRICS) + " |")
    return lines


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pipe = Pipeline(read_full_sample_returns())
    rows = [REFERENCE_ROW, *EXPLORATORY_ROWS]
    table = evaluate_rows(pipe, rows)
    table.to_csv(OUT / "exploratory_table.csv", index=False)
    lines = markdown_rows(table, rows)
    doc = ["# Exploratory strategies", "",
           "Tested, but not selected by the in-sample rule (a component is added only if it raises 1976-2014 net "
           "Sharpe by at least 0.05). The first row is the final strategy, for reference; each exploratory row adds "
           "one change to it, except the last, which switches on every pre-2015 candidate at once. Their "
           "out-of-sample numbers are information, not evidence: choosing any of them now would mean selecting on "
           "the test period.", "",
           "Net of 2 bps per unit turnover + 4 futures rolls a year at 2 bps (Lecture 11 slides 17-19). "
           "IS = Jan 1976 - Dec 2014; OOS = Jan 2015 - May 2025. Leverage = average gross exposure (x NAV); "
           "imbalance = average net long; turnover = annual traded notional (x NAV); cost = annual cost drag. "
           "† = rule designed after seeing 2015-2025 data, so its OOS result is not a clean test.", "",
           *lines, "",
           "Sharpe standard errors are about 0.19 in-sample and 0.31 out-of-sample, so OOS differences of 0.1-0.2 "
           "are within noise.", "", "## What each strategy is", ""]
    for _, key, name, _, _ in EXPLORATORY_ROWS:
        doc += [f"### {name}", "", EXPLORATORY_EXPLANATIONS[key], ""]
    (OUT / "exploratory_table.md").write_text("\n".join(doc), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
