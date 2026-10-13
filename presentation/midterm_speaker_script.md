# ORIE 5260 Presentation Speaker Script

Aligned with the concise 30-slide presentation. Five parts retain separate adjusted and rolling baseline discussions. Detailed attribution, risk validation, and SG Trend evidence refer to the adjusted baseline.

## Five part assignment

| Part | Slides |
| --- | --- |
| Part 1 — Motivation and EDA | 1–4 |
| Part 2 — Course PPT adjusted baseline | 5–12 |
| Part 3 — Rolling baseline | 13–19 |
| Part 4 — Attribution risk and SG Trend | 20–25 |
| Part 5 — Enhancements and conclusions | 26–30 |

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

## Part 4 — Attribution risk and SG Trend

**Slides 20–25.**

### Slide 20 — Asset classes and trading direction generate returns

**What to cover:** These are additive arithmetic return contributions, not CAGR components. Long positions provide 81.2 percent of the mean return and short positions 18.8 percent.

> These are additive arithmetic return contributions, not CAGR components. Long positions provide 81.2 percent of the mean return and short positions 18.8 percent.

### Slide 21 — Return attribution by regime and decade

**What to cover:** Bear events are an internal futures proxy: peak-to-recovery events that subsequently reach a 20% drawdown. This retrospective classification is not a live trading signal or an official cash-index regime. The 1970s sample begins in 1976.

> The strategy has positive returns in both internal bull and bear regimes and in every reported decade. Bear-regime volatility is higher, even though average returns remain positive. The 2010–2014 period is weaker than earlier periods. Our regimes use an S&P futures drawdown proxy identified retrospectively. They are descriptive categories, not a real-time trading signal or an official cash-index classification.

### Slide 22 — Six-factor regression: significant momentum exposure

**What to cover:** Monthly excess-return regression with Newey–West HAC standard errors, three lags. Future analysis should include carry, trend, duration, USD, and other futures-relevant factors.

> Over 2000 through 2014, the joint six-factor regression estimates annualized alpha of 7.20 percent and explains 28 percent of variance. Momentum has the clearest significant positive exposure, while market and size betas are close to zero. This is consistent with the strategy’s design. However, equity factors are incomplete controls for diversified futures, so residual alpha should not automatically be interpreted as manager skill.

### Slide 23 — Many markets, concentrated asset-class risk

**What to cover:** Risk shares here are internal diagonal-model w²σ² contributions. They omit covariance and are not a complete attribution of actual portfolio risk.

> We now move from where returns come from to where risk comes from. Under the diagonal model, commodities account for 62.7 percent of average predicted variance. The effective number of instrument risk positions is 39.6, but the effective number of asset-class positions is only 2.35. The portfolio is broad across contracts but concentrated across asset classes. These shares describe the model’s internal view and omit covariance.

### Slide 24 — The diagonal model understates future risk

**What to cover:** Future fixed-weight volatility differs from the 11.15% volatility of the monthly rebalanced strategy. Overlapping forecast windows are not independent observations.

> To validate the risk model, we freeze formation-date weights and compare predicted volatility with realized volatility over the following 12 months. Average predicted volatility is 6.82 percent, while realized volatility is 9.78 percent. Realized risk exceeds the forecast in 74.8 percent of observations. The three-month check also shows underestimation. This isolates risk forecasting from later trading decisions.

### Slide 25 — SG Trend: shared trend exposure, different drawdowns

**What to cover:** SG Trend differs in markets, fees, risk targets, and rules. This comparison is descriptive, not evidence of exact replication or superiority.

> The SG Trend comparison uses the common 2000–2014 sample. Our baseline has higher return and Sharpe, but also a deeper maximum drawdown: about 26 percent versus 18 percent. Correlation is 0.62, consistent with shared trend exposure. Differences in markets, fees, signals, and risk targets mean this is a descriptive comparison, not evidence that we exactly replicate or dominate a professional index.

## Part 5 — Enhancements and conclusions

**Slides 26–30.**

### Slide 26 — Four completed PPT / adjusted experiments

**What to cover:** E2 equalizes class allocation without solving covariance-aware equal risk contribution. It does not guarantee 25% of actual risk per class.

> We completed four experiments around the adjusted baseline. E1 replaces expanding volatility with EWMA using a six-month half-life. E2 allocates equally across asset classes and then within each class. E3 averages the one-, three-, six-, and 12-month direction signals. E4 combines all three changes. E2 is a class-allocation rule, not a covariance-aware solution guaranteeing equal realized risk.

### Slide 27 — Experimental improvements do not simply add up

**What to cover:** Matched volatility uses full-sample scaling to the baseline 11.15%, so it is retrospective. Experiment results are gross. Baseline transaction-cost results cannot be applied directly to experiments.

> E1 improves gross Sharpe to 1.12, but increases turnover. E3 has a Sharpe close to the baseline and reduces drawdowns, also with higher turnover. E2 and E4 have lower Sharpe than the baseline, so the benefits do not simply add up. Matched-volatility CAGR and drawdown use retrospective full-sample scaling. We still need separate cost and out-of-sample tests before selecting an enhancement.

### Slide 28 — Enhancement paths at comparable volatility

**What to cover:** Use the chart to compare paths, not only ending wealth. E1 has the strongest gross Sharpe. E3 has similar Sharpe and smaller drawdown but greater turnover. E2 and E4 do not preserve every individual benefit. Matching uses realized full-sample volatility and is not a tradable dynamic target.

> Use the chart to compare paths, not only ending wealth. E1 has the strongest gross Sharpe. E3 has similar Sharpe and smaller drawdown but greater turnover. E2 and E4 do not preserve every individual benefit. Matching uses realized full-sample volatility and is not a tradable dynamic target.

### Slide 29 — Findings: credible signal, incomplete risk model

**What to cover:** Highlight the evidence shown.

> Our main finding is that momentum has predictive information and produces attractive historical portfolio results. Returns are broad, but commodities and long positions dominate. The risk model is the clearest weakness because it understates future volatility and has limited forecasting power. Costs, leverage, and data assumptions matter. Enhancement results are promising in places, but they are not uniformly better.

### Slide 30 — Next steps and reproducibility

**What to cover:** Run baseline_performance_analysis.py before downstream adjusted attribution, validation, and benchmark analysis. E1–E4 are completed experiments; full covariance models, portfolio targeting, and walk-forward enhancements remain planned work. The central priority is improving risk measurement and implementation rather than selecting by full-sample Sharpe.

> Run baseline_performance_analysis.py before downstream adjusted attribution, validation, and benchmark analysis. E1–E4 are completed experiments; full covariance models, portfolio targeting, and walk-forward enhancements remain planned work. The central priority is improving risk measurement and implementation rather than selecting by full-sample Sharpe.
