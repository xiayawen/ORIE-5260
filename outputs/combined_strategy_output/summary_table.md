# Strategy summary: main, robustness and exploratory

Net of 2 bps per unit turnover + 4 futures rolls a year at 2 bps (Lecture 11 slides 17-19) unless stated. IS = Jan 1976 - Dec 2014 (all choices made here); OOS = Jan 2015 - May 2025 (evaluated once). Leverage = average gross exposure (x NAV); imbalance = average net long; turnover = annual traded notional (x NAV); cost = annual cost drag. † = includes a rule designed after seeing 2015-2025 data, so its OOS result is not a clean test.

**Main** rows are the baseline-vs-enhanced comparison the report asks for. **Robustness** rows check that the conclusion survives other baselines, the selection procedure and the cost model. **Exploratory** rows were tested but not selected by the in-sample rule; their OOS numbers are information, not evidence. Each exploratory row adds one change to the final strategy, except the last, which switches on every pre-2015 candidate at once (details in `exploratory_strategy.py`).

| Tier | Strategy | IS Net ret | OOS Net ret | IS Vol | OOS Vol | IS Sharpe | OOS Sharpe | IS Max DD | OOS Max DD | IS Leverage | OOS Leverage | IS Imbalance | OOS Imbalance | IS Turnover | OOS Turnover | IS Cost | OOS Cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Main | Baseline (Lecture 11, 11% ex-ante target) | 15.4% | 0.5% | 12.5% | 12.6% | 1.23 | 0.04 | -16.0% | -24.6% | 5.7x | 11.0x | +2.0x | +4.3x | 21.8 | 43.7 | 0.90% | 1.75% |
| Main | Final: enhanced + continuous signal | 11.4% | 0.9% | 10.1% | 7.5% | 1.13 | 0.12 | -16.5% | -11.9% | 2.9x | 3.7x | +0.9x | +0.9x | 10.8 | 15.3 | 0.45% | 0.60% |
| Robustness | Baseline variant: 10% on 36m realized vol | 12.1% | 0.8% | 10.2% | 10.6% | 1.18 | 0.08 | -13.0% | -22.5% | 4.5x | 9.2x | +1.5x | +4.0x | 13.4 | 28.6 | 0.63% | 1.30% |
| Robustness | Course baseline (Lecture 6, midterm) | 10.4% | -0.9% | 11.1% | 11.1% | 0.93 | -0.08 | -26.2% | -32.6% | 3.1x | 4.4x | +0.8x | +0.7x | 7.9 | 12.5 | 0.41% | 0.60% |
| Robustness | Enhanced (without continuous signal) | 10.1% | -0.0% | 9.5% | 7.1% | 1.07 | -0.01 | -13.9% | -14.4% | 3.1x | 3.9x | +0.8x | +0.8x | 9.6 | 12.8 | 0.44% | 0.56% |
| Robustness | Walk-forward selection, clean pool | 9.7% | 0.9% | 9.7% | 7.5% | 1.00 | 0.12 | -13.9% | -11.9% | 3.1x | 3.7x | +0.9x | +0.9x | 11.2 | 15.3 | 0.47% | 0.60% |
| Robustness | Final under Lecture 8 costs ($1bn) | 11.1% | 0.9% | 10.1% | 7.5% | 1.10 | 0.13 | -17.0% | -12.3% | 2.9x | 3.7x | +0.9x | +0.9x | 10.7 | 15.3 | 0.74% | 0.59% |
| Exploratory | Final + HistGB sleeve | 11.0% | 2.1% | 9.9% | 6.7% | 1.11 | 0.31 | -16.5% | -8.3% | 3.0x | 3.8x | +1.2x | +1.8x | 12.1 | 15.9 | 0.48% | 0.62% |
| Exploratory | Final + no-trade band (band_25) | 9.5% | 1.7% | 9.0% | 6.7% | 1.06 | 0.25 | -14.6% | -9.9% | 2.6x | 3.3x | +0.8x | +0.8x | 6.3 | 8.8 | 0.33% | 0.44% |
| Exploratory | Final + half-short † | 10.0% | 1.6% | 8.6% | 5.6% | 1.16 | 0.28 | -12.6% | -7.7% | 2.4x | 3.0x | +1.4x | +1.6x | 8.6 | 11.6 | 0.37% | 0.47% |
| Exploratory | All clean candidates (continuous core) | 6.9% | 0.9% | 7.4% | 4.3% | 0.93 | 0.21 | -17.4% | -8.7% | 2.0x | 2.3x | +0.3x | +0.5x | 8.3 | 10.3 | 0.33% | 0.39% |

Sharpe standard errors are about 0.19 in-sample and 0.31 out-of-sample, so OOS differences of 0.1-0.2 are within noise. Trades are assumed to fill at the signal close; a feasible execution schedule costs about 0.07-0.09 Sharpe (`alpha_decay_execution.py`).

## What each strategy is

### Baseline (Lecture 11, 11% ex-ante target) (main)

**What it is.** The course baseline of Lecture 11 (slides 17-21), implemented as the slides state it.
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
find hard to finance, and costs absorb most of its gross return.

### Final: enhanced + continuous signal (main)

**What it is.** Our enhanced strategy. Three changes to the baseline, in this order:
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
statistically significant (Sharpe standard error about 0.3).

### Baseline variant: 10% on 36m realized vol (robustness)

**What it is.** The same positions as the baseline, but the whole book is scaled to 10% using the
strategy's trailing 36-month *realized* volatility instead of an ex-ante covariance forecast. No caps.

**Why it is shown.** It is the closest match to slide 21's in-sample statistics on monthly data: turnover 13.42
(exactly slide 21's), volatility 10.2%, leverage 4.5x, Sharpe 1.18. Out of sample it gives 0.08 Sharpe. It shows
that the baseline-vs-final comparison does not depend on which reading of the slide-21 volatility target is used.

### Course baseline (Lecture 6, midterm) (robustness)

**What it is.** The baseline from Lecture 6 that we used in the midterm: +1/-1 12-month signal,
position = 40% / (volatility estimated on all past data, at least 36 months) / number of markets, no
portfolio-level volatility target.

**Why it is shown.** Continuity with the midterm. It explains why our earlier numbers differed from Lecture 11:
it sizes with slow, expanding-window volatility and never re-targets total risk, so in-sample Sharpe is lower
(0.93) and it lost money after 2015.

### Enhanced (without continuous signal) (robustness)

**What it is.** The final strategy without the continuous signal: +1/-1 signal, EWMA volatility sizing,
EWMA-covariance 10% risk target with a 4x cap. It is the starting point of the stepwise selection.

**Why it is shown.** It isolates the contribution of the continuous signal: in-sample +0.06 Sharpe, out of
sample from about zero to 0.12. Without it, the risk-control changes alone do not beat the baseline
in-sample (1.07 vs 1.23), mainly because of the 4x leverage cap (see the diagnosis in the report).

### Walk-forward selection, clean pool (robustness)

**What it is.** The same stepwise rule, re-run every December 31 from 1989 onward using only data
available up to that date (expanding window from 1976), with the chosen combination traded for the next
year. The candidate pool excludes rules that were designed after looking at 2015-2025 data.

**Why it is shown.** It tests the selection *procedure*, not one fixed answer. From 2005 onward it picks the
continuous signal every year, so its 2015-2025 result equals the final strategy's. Its lower in-sample number
reflects 1990-2004, when shorter histories led it to switch components (e.g. economic trend) at a cost.

### Final under Lecture 8 costs ($1bn) (robustness)

**What it is.** The final strategy evaluated with our more detailed Lecture 8 cost model instead of
2 bps: commission, futures roll, bid-ask half-spread and square-root market impact for a $1bn fund trading
over 5 days.

**Why it is shown.** The conclusions do not depend on the cost assumption: Sharpe ratios move by about 0.03,
and the stepwise selection picks the same strategy under either convention.

### Final + HistGB sleeve (exploratory)

**What it is.** The final strategy plus a 30% sleeve from a gradient-boosted tree model that predicts each
market's next-month direction from about 60 price-based features. The model is refit every year on the
previous 15 years only (walk-forward), so its forecasts never use future data.

**Why it is exploratory.** It slightly lowered in-sample Sharpe (1.11 vs 1.13), so the selection rule
correctly left it out. Its out-of-sample Sharpe (0.31, coincidentally the same as slide 30's baseline) was not
predictable from in-sample evidence; adopting it now would mean choosing on out-of-sample results. It is the
most promising direction for future work, to be validated on data after May 2025.

### Final + no-trade band (band_25) (exploratory)

**What it is.** The final strategy plus a no-trade band: a position is only traded when it drifts more
than 25% away from its target, and then only back to the band edge (Lecture 8: trade off alpha against costs).

**Why it is exploratory.** It cuts turnover, but on top of the continuous signal it lowered in-sample Sharpe,
so the rule rejected it. The continuous signal already shrinks weak positions, and the band then keeps
positions further below target. It looks better out of sample, when trading less helped in a choppy decade;
that is a regime effect, not evidence for the rule.

### Final + half-short † (exploratory)

**What it is.** The final strategy with every short position halved (longs unchanged).

**Why it is exploratory (†).** The rule was designed by the team after seeing that shorts lost money in
2015-2025, so its out-of-sample number is not a clean test. It also raises the net long position, i.e. more
equity-market exposure, which works against trend-following's role as crisis protection.

### All clean candidates (continuous core) (exploratory)

**What it is.** The continuous-signal strategy with every compatible candidate that was designed
before 2015 switched on at once: economic-trend, factor and HistGB sleeves, turning-point reduction,
net-exposure cap and the no-trade band. Half-short and the smoothing rules are left out because they were
designed after seeing 2015-2025 data. With all three sleeves active (from 1997, when HistGB starts) the trend
core is only 30% of the mix (economic trend 20%, factor 20%, HistGB 30%); before 1997 it is 60%. The
turning-point cut and the net cap then remove exposure after the mix is re-targeted to 10%.

**Why it is exploratory.** It is clearly worse in-sample (0.93 vs 1.13 Sharpe), a gap large enough to be a real
result rather than noise. Its higher out-of-sample Sharpe comes from lower risk, not more return: the overlays
keep shrinking the book (leverage about 2.3x, volatility about 4%), so net return is no higher than the final
strategy's. Including the post-2015 rules as well gives almost the same out-of-sample Sharpe (0.22), so the
effect is not driven by them.
