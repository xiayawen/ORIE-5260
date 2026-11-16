# Exploratory strategies

Tested, but not selected by the in-sample rule (a component is added only if it raises 1976-2014 net Sharpe by at least 0.05). The first row is the final strategy, for reference; each exploratory row adds one change to it, except the last, which switches on every pre-2015 candidate at once. Their out-of-sample numbers are information, not evidence: choosing any of them now would mean selecting on the test period.

Net of 2 bps per unit turnover + 4 futures rolls a year at 2 bps (Lecture 11 slides 17-19). IS = Jan 1976 - Dec 2014; OOS = Jan 2015 - May 2025. Leverage = average gross exposure (x NAV); imbalance = average net long; turnover = annual traded notional (x NAV); cost = annual cost drag. † = rule designed after seeing 2015-2025 data, so its OOS result is not a clean test.

| Tier | Strategy | IS Net ret | OOS Net ret | IS Vol | OOS Vol | IS Sharpe | OOS Sharpe | IS Max DD | OOS Max DD | IS Leverage | OOS Leverage | IS Imbalance | OOS Imbalance | IS Turnover | OOS Turnover | IS Cost | OOS Cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Reference | Final: enhanced + continuous signal | 11.4% | 0.9% | 10.1% | 7.5% | 1.13 | 0.12 | -16.5% | -11.9% | 2.9x | 3.7x | +0.9x | +0.9x | 10.8 | 15.3 | 0.45% | 0.60% |
| Exploratory | Final + HistGB sleeve | 11.0% | 2.1% | 9.9% | 6.7% | 1.11 | 0.31 | -16.5% | -8.3% | 3.0x | 3.8x | +1.2x | +1.8x | 12.1 | 15.9 | 0.48% | 0.62% |
| Exploratory | Final + no-trade band (band_25) | 9.5% | 1.7% | 9.0% | 6.7% | 1.06 | 0.25 | -14.6% | -9.9% | 2.6x | 3.3x | +0.8x | +0.8x | 6.3 | 8.8 | 0.33% | 0.44% |
| Exploratory | Final + half-short † | 10.0% | 1.6% | 8.6% | 5.6% | 1.16 | 0.28 | -12.6% | -7.7% | 2.4x | 3.0x | +1.4x | +1.6x | 8.6 | 11.6 | 0.37% | 0.47% |
| Exploratory | All clean candidates (continuous core) | 6.9% | 0.9% | 7.4% | 4.3% | 0.93 | 0.21 | -17.4% | -8.7% | 2.0x | 2.3x | +0.3x | +0.5x | 8.3 | 10.3 | 0.33% | 0.39% |

Sharpe standard errors are about 0.19 in-sample and 0.31 out-of-sample, so OOS differences of 0.1-0.2 are within noise.

## What each strategy is

### Final + HistGB sleeve

**What it is.** The final strategy plus a 30% sleeve from a gradient-boosted tree model that predicts each
market's next-month direction from about 60 price-based features. The model is refit every year on the
previous 15 years only (walk-forward), so its forecasts never use future data.

**Why it is exploratory.** It slightly lowered in-sample Sharpe (1.11 vs 1.13), so the selection rule
correctly left it out. Its out-of-sample Sharpe (0.31, coincidentally the same as slide 30's baseline) was not
predictable from in-sample evidence; adopting it now would mean choosing on out-of-sample results. It is the
most promising direction for future work, to be validated on data after May 2025.

### Final + no-trade band (band_25)

**What it is.** The final strategy plus a no-trade band: a position is only traded when it drifts more
than 25% away from its target, and then only back to the band edge (Lecture 8: trade off alpha against costs).

**Why it is exploratory.** It cuts turnover, but on top of the continuous signal it lowered in-sample Sharpe,
so the rule rejected it. The continuous signal already shrinks weak positions, and the band then keeps
positions further below target. It looks better out of sample, when trading less helped in a choppy decade;
that is a regime effect, not evidence for the rule.

### Final + half-short †

**What it is.** The final strategy with every short position halved (longs unchanged).

**Why it is exploratory (†).** The rule was designed by the team after seeing that shorts lost money in
2015-2025, so its out-of-sample number is not a clean test. It also raises the net long position, i.e. more
equity-market exposure, which works against trend-following's role as crisis protection.

### All clean candidates (continuous core)

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
