"""Three-tier summary of the strategies to present (main / robustness / exploratory).

Every row is computed with combined_strategy.Pipeline on MonthlyReturns_FullSample.xlsx, net of the
Lecture 11 convention (2 bps per unit turnover + 4 rolls/yr at 2 bps) unless the row says otherwise.
IS = Jan 1976 - Dec 2014, OOS = Jan 2015 - May 2025. Run after combined_strategy.py:

    python summary_table.py
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import pandas as pd

from combined_strategy import (
    OUT, CLEAN_POOL, ALL_COMPONENTS_CONTINUOUS, Pipeline, stats, walk_forward,
)
from risk_budgeting import IS_START, IS_END, OOS_START, read_full_sample_returns

FINAL = frozenset({"continuous_signal"})

# (tier, key, short name, how it is built, convention)
ROWS = [
    ("Main", "slide_baseline", "Baseline (Lecture 11 replica)", None, "slide_2bps"),
    ("Main", "final", "Final: enhanced + continuous signal", FINAL, "slide_2bps"),
    ("Robustness", "course_baseline", "Course baseline (Lecture 6, midterm)", None, "slide_2bps"),
    ("Robustness", "enhanced", "Enhanced (without continuous signal)", frozenset(), "slide_2bps"),
    ("Robustness", "walk_forward", "Walk-forward selection, clean pool", None, "slide_2bps"),
    ("Robustness", "final_lecture8", "Final under Lecture 8 costs ($1bn)", FINAL, "lecture8"),
    ("Exploratory", "final_histgb", "Final + HistGB sleeve", FINAL | {"histgb_overlay"}, "slide_2bps"),
    ("Exploratory", "final_band", "Final + no-trade band (band_25)", FINAL | {"band_25"}, "slide_2bps"),
    ("Exploratory", "final_half_short", "Final + half-short †", FINAL | {"half_short"}, "slide_2bps"),
    ("Exploratory", "all_candidates", "All candidates (continuous core) †", ALL_COMPONENTS_CONTINUOUS, "slide_2bps"),
]

METRICS = [("annual_net_return", "Net ret", "{:.1%}"), ("annual_volatility", "Vol", "{:.1%}"),
           ("net_sharpe", "Sharpe", "{:.2f}"), ("max_drawdown", "Max DD", "{:.1%}"),
           ("average_gross_exposure", "Leverage", "{:.1f}x"), ("average_net_exposure", "Imbalance", "{:+.1f}x"),
           ("annual_turnover", "Turnover", "{:.1f}"), ("annual_cost_drag", "Cost", "{:.2%}")]

EXPLANATIONS = {
    "slide_baseline": """**What it is.** Our replica of the course baseline in Lecture 11 (slides 17-21). Each month, every
market gets a +1/-1 position from the sign of its past 12-month return, sized by 1/(12-month volatility) and
divided by the number of markets, so each market contributes roughly equal risk. The whole book is then scaled
so that the strategy's trailing 36-month realized volatility is 10%. There is no leverage cap and no volatility
floor. Costs follow slides 17-19 exactly.

**Why it is the benchmark.** The report guidelines ask for a baseline "broadly aligned" with the slides. It
reproduces slide 21's in-sample turnover exactly (13.42) and is close on Sharpe (1.18 vs 1.13), volatility,
leverage (4.6x vs 4.0x) and number of names. It does not reproduce slide 30's out-of-sample Sharpe (0.08 vs
0.31); the remaining gap is most likely the professor's daily data, which we do not have after 2014.

**Watch-outs.** Out of sample its leverage rises to about 9x with a 4x net long, mostly in low-volatility
interest-rate futures: its returns depend on leverage that a real fund would find hard to finance.""",

    "final": """**What it is.** Our enhanced strategy. Three changes to the baseline, in this order:
1. *Continuous signal* (Lecture 11 slide 24): instead of +1/-1, each market's signal is its 12-month return
   divided by its annual volatility, capped at +/-1. Strong trends (at least one standard deviation) get a full
   position; weak, noisy trends get a small one.
2. *EWMA volatility sizing*: market volatility is estimated with a 6-month half-life, so sizing reacts faster
   to volatility changes than a 12-month window.
3. *Covariance-based risk targeting* (Lecture 11 slide 23): the whole book is scaled to 10% predicted volatility
   using an EWMA covariance matrix (correlations included), with a 4x gross-leverage cap.

**How it was chosen.** Starting from steps 2-3 (`enhanced`), eleven candidate enhancements were tested with a
forward stepwise rule on 1976-2014 data only: a component is added if it raises in-sample net Sharpe by at
least 0.05. Only the continuous signal passed (+0.06). The out-of-sample period was evaluated once, afterwards.

**Result.** Same in-sample Sharpe as slide 21's baseline (1.13) with about a quarter less leverage (2.9x vs
4.0x). Slightly below our baseline replica in-sample (1.13 vs 1.18), with a deeper in-sample drawdown
(-16.5% vs -13.0%), mainly because the 4x cap limits the rate-futures leverage that paid off before 2015.
Out of sample it does better (0.12 vs 0.08) with about half the baseline's drawdown and leverage. The
out-of-sample gain is not statistically significant (Sharpe standard error about 0.3).""",

    "course_baseline": """**What it is.** The baseline from Lecture 6 that we used in the midterm: +1/-1 12-month signal,
position = 40% / (volatility estimated on all past data, at least 36 months) / number of markets, no
portfolio-level volatility target.

**Why it is shown.** Continuity with the midterm. It explains why our earlier numbers differed from Lecture 11:
it sizes with slow, expanding-window volatility and never re-targets total risk, so in-sample Sharpe is lower
(0.93) and it lost money after 2015.""",

    "enhanced": """**What it is.** The final strategy without the continuous signal: +1/-1 signal, EWMA volatility sizing,
EWMA-covariance 10% risk target with a 4x cap. It is the starting point of the stepwise selection.

**Why it is shown.** It isolates the contribution of the continuous signal: in-sample +0.06 Sharpe, out of
sample from about zero to 0.12. Without it, the risk-control changes alone do not beat the baseline replica
in-sample (1.07 vs 1.18), mainly because of the 4x leverage cap (see the diagnosis in the report).""",

    "walk_forward": """**What it is.** The same stepwise rule, re-run every December 31 from 1989 onward using only data
available up to that date (expanding window from 1976), with the chosen combination traded for the next
year. The candidate pool excludes rules that were designed after looking at 2015-2025 data.

**Why it is shown.** It tests the selection *procedure*, not one fixed answer. From 2005 onward it picks the
continuous signal every year, so its 2015-2025 result equals the final strategy's. Its lower in-sample number
reflects 1990-2004, when shorter histories led it to switch components (e.g. economic trend) at a cost.""",

    "final_lecture8": """**What it is.** The final strategy evaluated with our more detailed Lecture 8 cost model instead of
2 bps: commission, futures roll, bid-ask half-spread and square-root market impact for a $1bn fund trading
over 5 days.

**Why it is shown.** The conclusions do not depend on the cost assumption: Sharpe ratios move by about 0.03,
and the stepwise selection picks the same strategy under either convention.""",

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

    "all_candidates": """**What it is.** The continuous-signal strategy with every compatible candidate switched on at once:
economic-trend, factor and HistGB sleeves, turning-point reduction, half-short, net-exposure cap, leverage and
imbalance smoothing, and the no-trade band.

**Why it is exploratory (†).** It is clearly worse in-sample (about 0.2 Sharpe lower). Its higher
out-of-sample Sharpe comes from lower risk, not more return: the overlays keep shrinking the book (leverage
about 1.7x, volatility about 4%), so net return is no higher than the final strategy's. It includes rules
designed after seeing 2015+ data.""",
}


def main():
    returns = read_full_sample_returns()
    pipe = Pipeline(returns)
    series = {
        "slide_baseline": pipe.evaluate(pipe.slide_baseline().shift(1).fillna(0.0)),
        "course_baseline": pipe.evaluate(pipe.course_baseline().shift(1).fillna(0.0)),
        "walk_forward": pipe.evaluate(walk_forward(pipe, CLEAN_POOL)[1]),
    }
    rows = []
    for tier, key, name, config, convention in ROWS:
        s = series[key] if key in series else pipe.run(config)
        for period, (start, end) in (("IS", (IS_START, IS_END)), ("OOS", (OOS_START, None))):
            rows.append({"tier": tier, "key": key, "strategy": name, "costs": convention, "period": period,
                         **stats(s, start, end, convention)})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "summary_table.csv", index=False)

    head = "| Tier | Strategy | " + " | ".join(f"IS {m[1]} | OOS {m[1]}" for m in METRICS) + " |"
    lines = [head, "|---|---|" + "---:|" * (2 * len(METRICS))]
    for tier, key, name, _, convention in ROWS:
        a = table[(table.key == key) & (table.period == "IS")].iloc[0]
        b = table[(table.key == key) & (table.period == "OOS")].iloc[0]
        lines.append(f"| {tier} | {name} | " + " | ".join(f"{f.format(a[k])} | {f.format(b[k])}"
                                                           for k, _, f in METRICS) + " |")
    doc = ["# Strategy summary: main, robustness and exploratory", "",
           "Net of 2 bps per unit turnover + 4 futures rolls a year at 2 bps (Lecture 11 slides 17-19) unless "
           "stated. IS = Jan 1976 - Dec 2014 (all choices made here); OOS = Jan 2015 - May 2025 (evaluated once). "
           "Leverage = average gross exposure (x NAV); imbalance = average net long; turnover = annual traded "
           "notional (x NAV); cost = annual cost drag. † = includes a rule designed after seeing 2015-2025 data, "
           "so its OOS result is not a clean test.", "",
           "**Main** rows are the baseline-vs-enhanced comparison the report asks for. **Robustness** rows check "
           "that the conclusion survives other baselines, the selection procedure and the cost model. "
           "**Exploratory** rows were tested but not selected by the in-sample rule; their OOS numbers are "
           "information, not evidence. Exploratory rows are all the final strategy plus one change.", "",
           *lines, "",
           "Sharpe standard errors are about 0.19 in-sample and 0.31 out-of-sample, so OOS differences of 0.1-0.2 "
           "are within noise. Trades are assumed to fill at the signal close; a feasible execution schedule "
           "costs about 0.07-0.09 Sharpe (`alpha_decay_execution.py`).", "", "## What each strategy is", ""]
    for tier, key, name, _, _ in ROWS:
        doc += [f"### {name} ({tier.lower()})", "", EXPLANATIONS[key], ""]
    (OUT / "summary_table.md").write_text("\n".join(doc), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
