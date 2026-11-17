"""Three-tier summary of the strategies to present (main / robustness / exploratory).

Every row is computed with combined_strategy.Pipeline on MonthlyReturns_FullSample.xlsx, net of the
Lecture 11 convention (2 bps per unit turnover + 4 rolls/yr at 2 bps) unless the row says otherwise.
IS = Jan 1976 - Dec 2014, OOS = Jan 2015 - May 2025. Run after combined_strategy.py:

    python summary_table.py
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

from combined_strategy import OUT, CLEAN_POOL, Pipeline, walk_forward
from exploratory_strategy import (
    FINAL, EXPLORATORY_ROWS, EXPLORATORY_EXPLANATIONS, evaluate_rows, markdown_rows,
)
from risk_budgeting import read_full_sample_returns

# (tier, key, short name, how it is built, convention)
ROWS = [
    ("Main", "slide_baseline", "Baseline (Lecture 11, 11% ex-ante target)", None, "slide_2bps"),
    ("Main", "final", "Final: enhanced + continuous signal", FINAL, "slide_2bps"),
    ("Robustness", "slide_baseline_realized", "Baseline variant: 10% on 36m realized vol", None, "slide_2bps"),
    ("Robustness", "course_baseline", "Course baseline (Lecture 6, midterm)", None, "slide_2bps"),
    ("Robustness", "enhanced", "Enhanced (without continuous signal)", frozenset(), "slide_2bps"),
    ("Robustness", "walk_forward", "Walk-forward selection, clean pool", None, "slide_2bps"),
    ("Robustness", "final_lecture8", "Final under Lecture 8 costs ($1bn)", FINAL, "lecture8"),
    *EXPLORATORY_ROWS,  # defined in exploratory_strategy.py
]

EXPLANATIONS = {
    "slide_baseline": """**What it is.** The course baseline of Lecture 11 (slides 17-21), implemented as the slides state it.
Each month, every market gets a +1/-1 position from the sign of its past 12-month return, sized by 1/(12-month
volatility) and divided by the number of markets, so each market contributes roughly equal risk. The whole book
is then scaled so that its *predicted* (ex-ante) volatility is 11%, using a 6-month-half-life EWMA covariance
matrix estimated on returns up to the formation date. There is no leverage cap and no volatility floor. Costs
follow slides 17-19 exactly.

**Why it is the benchmark.** The report guidelines ask for a baseline "broadly aligned" with the slides, and this
follows slide 21's stated rule (11% ex-ante target) literally. In-sample Sharpe is close to slide 21 (1.23 vs
1.13). Because our covariance forecast uses monthly data, it tends to under-predict risk: realized volatility is
about 12.5% rather than 11%, and turnover (21.8 vs 13.42) and leverage (5.7x vs 4.0x) are above slide 21. It
does not reproduce slide 30's out-of-sample Sharpe (0.04 vs 0.31); the professor's forecast most likely uses
daily data, which we do not have after 2014.

**Watch-outs.** Out of sample its leverage rises to about 11x with a 4x net long, mostly in low-volatility
interest-rate futures, and turnover doubles (about 44): its returns depend on leverage that a real fund would
find hard to finance, and costs absorb most of its gross return.""",

    "slide_baseline_realized": """**What it is.** The same positions as the baseline, but the whole book is scaled to 10% using the
strategy's trailing 36-month *realized* volatility instead of an ex-ante covariance forecast. No caps.

**Why it is shown.** It is the closest match to slide 21's in-sample statistics on monthly data: turnover 13.42
(exactly slide 21's), volatility 10.2%, leverage 4.5x, Sharpe 1.18. Out of sample it gives 0.08 Sharpe. It shows
that the baseline-vs-final comparison does not depend on which reading of the slide-21 volatility target is used.""",

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
4.0x). Below our baseline in-sample (1.13 vs 1.23), mainly because the baseline runs about twice the leverage
(5.7x vs 2.9x) with no cap, and rate-futures leverage paid off before 2015; in-sample drawdowns are similar
(-16.5% vs -16.0%). Out of sample it does better (0.12 vs 0.04) with about half the baseline's drawdown
(-11.9% vs -24.6%), a third of its leverage and a third of its turnover. The out-of-sample gain is not
statistically significant (Sharpe standard error about 0.3).""",

    "course_baseline": """**What it is.** The baseline from Lecture 6 that we used in the midterm: +1/-1 12-month signal,
position = 40% / (volatility estimated on all past data, at least 36 months) / number of markets, no
portfolio-level volatility target.

**Why it is shown.** Continuity with the midterm. It explains why our earlier numbers differed from Lecture 11:
it sizes with slow, expanding-window volatility and never re-targets total risk, so in-sample Sharpe is lower
(0.93) and it lost money after 2015.""",

    "enhanced": """**What it is.** The final strategy without the continuous signal: +1/-1 signal, EWMA volatility sizing,
EWMA-covariance 10% risk target with a 4x cap. It is the starting point of the stepwise selection.

**Why it is shown.** It isolates the contribution of the continuous signal: in-sample +0.06 Sharpe, out of
sample from about zero to 0.12. Without it, the risk-control changes alone do not beat the baseline
in-sample (1.07 vs 1.23), mainly because of the 4x leverage cap (see the diagnosis in the report).""",

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
    **EXPLORATORY_EXPLANATIONS,  # defined in exploratory_strategy.py
}


def main():
    returns = read_full_sample_returns()
    pipe = Pipeline(returns)
    series = {
        "slide_baseline": pipe.evaluate(pipe.slide_baseline().shift(1).fillna(0.0)),
        "slide_baseline_realized": pipe.evaluate(pipe.slide_baseline_realized().shift(1).fillna(0.0)),
        "course_baseline": pipe.evaluate(pipe.course_baseline().shift(1).fillna(0.0)),
        "walk_forward": pipe.evaluate(walk_forward(pipe, CLEAN_POOL)[1]),
    }
    table = evaluate_rows(pipe, ROWS, series)
    table.to_csv(OUT / "summary_table.csv", index=False)
    lines = markdown_rows(table, ROWS)
    doc = ["# Strategy summary: main, robustness and exploratory", "",
           "Net of 2 bps per unit turnover + 4 futures rolls a year at 2 bps (Lecture 11 slides 17-19) unless "
           "stated. IS = Jan 1976 - Dec 2014 (all choices made here); OOS = Jan 2015 - May 2025 (evaluated once). "
           "Leverage = average gross exposure (x NAV); imbalance = average net long; turnover = annual traded "
           "notional (x NAV); cost = annual cost drag. † = includes a rule designed after seeing 2015-2025 data, "
           "so its OOS result is not a clean test.", "",
           "**Main** rows are the baseline-vs-enhanced comparison the report asks for. **Robustness** rows check "
           "that the conclusion survives other baselines, the selection procedure and the cost model. "
           "**Exploratory** rows were tested but not selected by the in-sample rule; their OOS numbers are "
           "information, not evidence. Each exploratory row adds one change to the final strategy, except the "
           "last, which switches on every pre-2015 candidate at once (details in `exploratory_strategy.py`).", "",
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
