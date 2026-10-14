# ORIE 5260 Presentation Speaker Script

Aligned with the concise 30-slide presentation. Five parts retain separate adjusted and rolling baseline discussions. Detailed attribution, risk validation, and SG Trend evidence refer to the adjusted baseline.

## Five part assignment

| Part | Slides |
| --- | --- |
| Part 1 — Motivation and EDA | 1–4 |
| Part 2 — Course PPT adjusted baseline | 5–12 |
| Part 3 — Rolling baseline | 13–19 |
| Part 4 — Signal evidence and return sources | 20–25 |
| Part 5 — Risk and external validation | 26–30 |

## Part 1 — Motivation and EDA

**Slides 1–4.**

### Slide 01 — Futures Time-Series Momentum

**What to cover:** We evaluate two baselines: rolling_backtest.py and strategy_backtest_adj.py, which follows the course PPT. Detailed downstream analyses use the adjusted baseline.

> We evaluate two baselines: rolling_backtest.py and strategy_backtest_adj.py, which follows the course PPT. Detailed downstream analyses use the adjusted baseline.

### Slide 02 — Research question and data

**What to cover:** Introduce the research question and dataset briefly. Histories differ and are not backfilled. The main emphasis is on the adjusted and rolling baselines, their benchmark relationships, and risk limitations.

> Introduce the research question and dataset briefly. Histories differ and are not backfilled. The main emphasis is on the adjusted and rolling baselines, their benchmark relationships, and risk limitations.

### Slide 03 — Data quality: flags, reconstruction, and open checks

**What to cover:** Outlier flags are diagnostic, not automatic deletions. Daily reconstruction uses last available monthly closes and exact matching dates; it does not fully validate roll, collateral, or currency conventions.

> Outlier flags are diagnostic, not automatic deletions. Daily reconstruction uses last available monthly closes and exact matching dates; it does not fully validate roll, collateral, or currency conventions.

### Slide 04 — EDA implications for portfolio design

**What to cover:** Instrument medians use unequal histories. Pairwise correlations require at least 60 overlaps. These findings motivate inverse-volatility sizing and later covariance validation, rather than proving that current risk estimates are accurate.

> Instrument medians use unequal histories. Pairwise correlations require at least 60 overlaps. These findings motivate inverse-volatility sizing and later covariance validation, rather than proving that current risk estimates are accurate.

## Part 2 — Course PPT adjusted baseline

**Slides 5–12.**

### Slide 05 — Two baseline versions: rolling and course PPT

**What to cover:** We have two baselines: rolling_backtest.py and strategy_backtest_adj.py, the course PPT approach. Both estimate risk using historical information and execute next month. Both use annualized arithmetic mean divided by volatility for zero-RF Sharpe. Gross rolling Sharpe is 1.06 and adjusted Sharpe is 0.97. Subsequent attribution, factor, risk, and SG Trend analyses use standardized adjusted-baseline outputs.

> We have two baselines: rolling_backtest.py and strategy_backtest_adj.py, the course PPT approach. Both estimate risk using historical information and execute next month. Both use annualized arithmetic mean divided by volatility for zero-RF Sharpe. Gross rolling Sharpe is 1.06 and adjusted Sharpe is 0.97. Subsequent attribution, factor, risk, and SG Trend analyses use standardized adjusted-baseline outputs.

### Slide 06 — The course PPT approach: adjusted baseline

**What to cover:** The divisor counts vol.notna(). A market with valid volatility but a missing consecutive signal window remains in the divisor and receives a zero signal.

> Our main baseline follows strategy_backtest_adj.py, the course PPT approach. For each market, we take the sign of the sum of its past 12 monthly returns. We estimate annualized volatility from available history through the formation month, requiring at least 36 valid observations. We multiply the signal by 40 percent divided by volatility, then divide across the eligible universe. The 40 percent parameter is instrument-level scaling, not a portfolio volatility target.

### Slide 07 — Execution timing and assumptions

**What to cover:** Highlight the evidence shown.

> Weights formed in month t are applied to returns in month t plus one. This one-month shift prevents us from trading on the return we are trying to predict. The adjusted risk estimate also uses only available history. However, missing held-market returns are filled with zero, and we omit leverage caps, financing, margin constraints, and explicit roll costs. The baseline risk model assumes zero covariance.

### Slide 08 — Four lookbacks: complete portfolio backtests

**What to cover:** We tested four horizons, not an exhaustive parameter search. Twelve months has the strongest in-sample portfolio Sharpe. Signal diagnostics use different eligibility and samples. E3 later combines these four signals instead of selecting one solely by full-sample results.

> We tested four horizons, not an exhaustive parameter search. Twelve months has the strongest in-sample portfolio Sharpe. Signal diagnostics use different eligibility and samples. E3 later combines these four signals instead of selecting one solely by full-sample results.

### Slide 09 — Main results: stronger returns and smaller drawdowns

**What to cover:** All main performance results use the adjusted baseline. Sharpe assumes a zero risk-free rate; factor regressions separately use excess returns.

> Over 1976 through 2014, the adjusted TSMOM strategy earns a 10.64 percent CAGR and a Sharpe ratio of 0.97, compared with 5.91 percent and 0.47 for static long exposure. TSMOM also has lower volatility and a much smaller maximum drawdown. This suggests that changing position direction adds value in this historical sample. The cost is substantially higher turnover.

### Slide 10 — Compounded wealth of the main strategy

**What to cover:** The chart compounds realized monthly portfolio returns. Compounded wealth is consistent with a summed-return momentum signal.

> This chart compounds the realized monthly portfolio returns. It visualizes the cumulative difference between momentum and static exposure over the main sample. The important distinction is that the adjusted signal uses summed past returns, while portfolio wealth still compounds. A summed signal does not imply that investment returns are added without compounding.

### Slide 11 — Adjusted baseline: exposure and trading costs

**What to cover:** Gross exposure sums absolute weights and net exposure sums signed weights. The strategy has implicit leverage and an average long bias. Costs apply to one-way target-weight changes. It remains profitable under the tested scenarios, but these do not represent a complete implementable futures cost model.

> Gross exposure sums absolute weights and net exposure sums signed weights. The strategy has implicit leverage and an average long bias. Costs apply to one-way target-weight changes. It remains profitable under the tested scenarios, but these do not represent a complete implementable futures cost model.

### Slide 12 — Adjusted baseline versus static: correlation

**What to cover:** Static is the internally constructed always-long portfolio with the same expanding-volatility eligibility. Overall correlation is low but fixed-income contributions remain strongly correlated. Arithmetic mean difference is not CAGR difference or regression alpha. SG Trend is a separate external comparator.

> Static is the internally constructed always-long portfolio with the same expanding-volatility eligibility. Overall correlation is low but fixed-income contributions remain strongly correlated. Arithmetic mean difference is not CAGR difference or regression alpha. SG Trend is a separate external comparator.

## Part 3 — Rolling baseline

**Slides 13–19.**

### Slide 13 — Rolling baseline: a second strategy specification

**What to cover:** The rolling baseline differs from the course PPT baseline in both the signal and the risk estimator. It keeps only the latest 12 months in the volatility window, whereas the adjusted baseline uses expanding history with a 36-observation threshold. Both use historical inputs and next-month execution. This is a separate baseline specification, not a minor change in a displayed statistic.

> The rolling baseline differs from the course PPT baseline in both the signal and the risk estimator. It keeps only the latest 12 months in the volatility window, whereas the adjusted baseline uses expanding history with a 36-observation threshold. Both use historical inputs and next-month execution. This is a separate baseline specification, not a minor change in a displayed statistic.

### Slide 14 — Compounded versus summed momentum signals

**What to cover:** Compounding the signal measures the growth of an underlying return sequence, while summation uses its arithmetic total. The example shows why the signs can differ. It does not imply one definition is universally better. Our two observed strategies simultaneously change risk windows and samples, so their Sharpe difference cannot isolate the signal effect.

> Compounding the signal measures the growth of an underlying return sequence, while summation uses its arithmetic total. The example shows why the signs can differ. It does not imply one definition is universally better. Our two observed strategies simultaneously change risk windows and samples, so their Sharpe difference cannot isolate the signal effect.

### Slide 15 — Rolling baseline: performance and cost sensitivity

**What to cover:** This is the rolling version of our baseline, not merely a robustness variant. We show only rolling_tsmom and rolling_static results. Costs use one-way absolute target-weight changes. Different samples and constructions prevent claiming that the higher gross Sharpe alone establishes superiority.

> This is the rolling version of our baseline, not merely a robustness variant. We show only rolling_tsmom and rolling_static results. Costs use one-way absolute target-weight changes. Different samples and constructions prevent claiming that the higher gross Sharpe alone establishes superiority.

### Slide 16 — Rolling baseline: compounded wealth

**What to cover:** The logarithmic axis makes proportional growth easier to compare over the long sample. The 10-basis-point curve shows cumulative trading costs rather than a one-time adjustment to terminal wealth. These curves contain only the permitted rolling baseline and its benchmark, with no excluded strategy results. Historical growth remains dependent on leverage and implementation assumptions.

> The logarithmic axis makes proportional growth easier to compare over the long sample. The 10-basis-point curve shows cumulative trading costs rather than a one-time adjustment to terminal wealth. These curves contain only the permitted rolling baseline and its benchmark, with no excluded strategy results. Historical growth remains dependent on leverage and implementation assumptions.

### Slide 17 — Rolling correlation with its static benchmark

**What to cover:** At zero costs the correlation is approximately 0.385, larger than the adjusted baseline’s 0.08 in its separate sample. This means rolling momentum retains more shared movement with its static comparator. Costs leave correlation nearly unchanged but reduce the mean advantage. A low correlation and a positive return difference answer different questions.

> At zero costs the correlation is approximately 0.385, larger than the adjusted baseline’s 0.08 in its separate sample. This means rolling momentum retains more shared movement with its static comparator. Costs leave correlation nearly unchanged but reduce the mean advantage. A low correlation and a positive return difference answer different questions.

### Slide 18 — Rolling regressions: benchmark and factor evidence

**What to cover:** Static regressions use 539 months of raw returns; six-factor regressions use 180 months of excess returns. The positive gross six-factor intercept becomes less statistically strong after costs. Residual alpha cannot automatically be interpreted as skill. Do not mix these rolling regressions with adjusted-baseline regression results.

> Static regressions use 539 months of raw returns; six-factor regressions use 180 months of excess returns. The positive gross six-factor intercept becomes less statistically strong after costs. Residual alpha cannot automatically be interpreted as skill. Do not mix these rolling regressions with adjusted-baseline regression results.

### Slide 19 — Why do the static correlations differ?

**What to cover:** Separate the observed correlation gap from untested explanations. Each strategy has its own static benchmark.

> The adjusted baseline has a correlation of 0.080 with its own static portfolio, while the rolling baseline has a correlation of 0.385 with its own static portfolio. These are different benchmarks and historical samples, not a comparison against one common return series. A possible explanation is that both rolling portfolios respond to the same recent-volatility estimates, which may create shared changes in exposure. However, both adjusted portfolios also share their risk scaling, so shared scaling alone does not establish the cause. Compounded versus summed signals, eligibility rules, and evaluation dates also differ. We have not isolated their contributions. Higher correlation means more common return movement, not automatically worse performance. Rolling has higher gross Sharpe in its sample but higher turnover and much larger peak exposure. The next step is a common-sample comparison that changes one component at a time.

## Part 4 — Signal evidence and return sources

**Slides 20–25.**

### Slide 20 — Autocorrelation: returns versus volatility

**What to cover:** ACF(k) = Corr(xₜ, xₜ₋ₖ). Test k = 1–12 for returns, |returns|, and returns². Mean lag-1: raw 6.2%, absolute 18.4%.

> This slide distinguishes return persistence from volatility persistence. Autocorrelation compares a series with its lagged values. Absolute and squared returns proxy volatility, not return direction. Diagnostics are computed per instrument and summarized by asset class and period. Stronger volatility persistence supports backward-looking risk estimates but does not by itself establish a tradable momentum signal.

### Slide 21 — Signal predictiveness across four horizons

**What to cover:** Spread = E[rₜ₊₁ | sₜ > 0] − E[rₜ₊₁ | sₜ < 0]. Hit rate = share of nonzero signals matching next-return direction. *HAC t uses monthly aggregated vol-scaled signed returns.

> This is signal predictiveness, not the portfolio performance table in Part 2. Signals are formed before next-month returns. A correct negative signal means a subsequent negative return. Statistical inference uses monthly aggregated signed returns with HAC errors to avoid treating correlated markets within a month as independent. These samples and eligibility rules differ from the full baseline portfolio.

### Slide 22 — Signal stability by class and period

**What to cover:** Instrument-level diagnostics are aggregated by class and period. Similar hit rates can coexist with smaller economic return spreads.

> All classes have positive twelve-month return spreads. Across periods the directional hit rate is comparatively stable while the economic spread becomes much smaller in 2010 through 2014. Therefore, hit rate alone is insufficient. Unequal instrument histories change the composition of period summaries, so these descriptive comparisons do not isolate a time effect.

### Slide 23 — Rolling performance and drawdown recovery

**What to cover:** Drawdown = wealth / running peak − 1. Recovery is the first return to that prior peak. Rolling metrics use a moving historical window; they differ from rolling volatility used to form weights.

> This adds stability and recovery information without repeating headline CAGR and Sharpe. The chart contains rolling return, volatility, and risk-adjusted performance. The largest adjusted drawdown took five months to reach its trough and 58 months from its peak to recover. A good full-sample Sharpe does not imply a short recovery period.

### Slide 24 — Return attribution: sources and drawdown drivers

**What to cover:** Monthly contribution cᵢ,ₜ = executed weight × market return. Arithmetic contributions add to portfolio returns; event sums do not decompose compounded MaxDD exactly.

> Return attribution answers where profits and losses came from. The largest drawdown episode has notable negative arithmetic contributions from Australian dollar, copper, and Canadian dollar. These event contributions are sums over the episode rather than a geometrically linked drawdown decomposition. Do not equate return share with risk share.

### Slide 25 — Market regimes: definition and attribution

**What to cover:**  Classification:  compound SP futures returns into proxy wealth. If a peak-to-recovery episode reaches a drawdown of at least 20%, label months after the peak through recovery as Bear. If unrecovered, label through sample end. All remaining observed months are Bull.

> The 20-percent threshold identifies the whole episode retrospectively, not just months after the threshold is crossed. The peak month is excluded from Bear and the recovery month is included. Recovery means proxy wealth reaches or exceeds its previous peak. Thus early months are classified using later outcomes. The result describes historical market conditions and must not be claimed as a live regime signal. The 1970s strategy sample begins in 1976.

## Part 5 — Risk and external validation

**Slides 26–30.**

### Slide 26 — Risk concentration under the diagonal model

**What to cover:** Diagonal variance = Σ wᵢ²σᵢ², omitting all cross-market covariance terms. Risk share qᵢ = wᵢ²σᵢ² / total; effective positions = 1 / Σqᵢ².

> This is the internal risk model, not a complete estimate of realized covariance-aware risk. Equal instrument allocation does not create equal class risk. Correlated same-direction positions can increase true portfolio risk through omitted covariance terms. The current validation diagnoses the model; it does not yet isolate covariance from every other forecast error source.

### Slide 27 — Validate risk forecasts using fixed weights

**What to cover:** Save formation-month prediction. Freeze those weights and measure annualized volatility over the next H months. Error = realized − predicted; bias = mean error. Exceedance = realized > predicted.

> Fixed weights isolate risk forecasting from later signal and trading changes. The future realized volatility is different from the volatility of the monthly rebalanced strategy. Error files include absolute and squared errors for MAE and RMSE calculations. Overlapping horizons create dependent observations. Future covariance and targeting models must be assessed with the same validation design.

### Slide 28 — Risk validation in high-volatility periods

**What to cover:** High-volatility label: future fixed-weight realized vol at or above its 80th-percentile cutoff, separately for each horizon. This is an ex-post evaluation label, not a forecast available at formation.

> The high-volatility test demonstrates where underestimation is especially severe. The reported twelve-month high subset has 61 observations after summary filtering. We must not present the ex-post label as a tradable regime predictor. Bias is mean signed error and RMSE is the square root of mean squared error. This analysis strengthens the case for risk-model improvements.

### Slide 29 — SG Trend: external benchmark and active risk

**What to cover:** Tracking error = Std(TSMOM − SG) × √12. Information ratio = annual mean difference / tracking error. Alpha is a regression intercept; beta measures benchmark exposure.

> SG Trend is an external trend index, not our internal always-long benchmark. Use the common 180-month sample. The adjusted baseline has higher return and Sharpe but a deeper drawdown. Tracking error measures variability of active returns, not volatility forecast error. Benchmark outputs also contain cumulative and rolling comparisons, but this concise page summarizes their main metrics rather than reproducing every chart.

### Slide 30 — Enhancements and next evaluation

**What to cover:** Matched-vol results use full-sample scaling to baseline volatility, for retrospective comparison. E2 equalizes class allocation, not covariance-aware risk contributions.

> These are completed gross experiments around the adjusted baseline. E1 improves Sharpe, while E3 reduces matched-volatility drawdowns with higher turnover. Combined changes do not automatically preserve every benefit. Full covariance, portfolio targeting, and walk-forward implementation remain future work. End with the core conclusion: useful momentum evidence, but risk modeling and implementation need improvement.

