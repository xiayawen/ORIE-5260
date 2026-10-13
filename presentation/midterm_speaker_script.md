# ORIE 5260 — Presentation Speaker Script

Aligned with the current 39-slide presentation. Both baseline versions are introduced in Part 2; subsequent main analysis uses the course PPT / adjusted baseline.

## Five-part assignment

| Part | Slides |
| --- | --- |
| Part 1 — Motivation and focused EDA | 1–7 |
| Part 2 — Both baselines, lookbacks, and performance | 8–19 |
| Part 3 — Return attribution, risk, and benchmarks | 20–29 |
| Part 4 — Robustness and enhancement experiments | 30–36 |
| Part 5 — Conclusions, next steps, and reproducibility | 37–39 |

## Part 1 — Motivation and focused EDA

**Slides 1–7.**

### Slide 01 — Futures Time-Series Momentum

**What to cover:** We evaluate two baselines: rolling_backtest.py and strategy_backtest_adj.py, which follows the course PPT. Detailed downstream analyses use the adjusted baseline.

> We evaluate two baselines: rolling_backtest.py and strategy_backtest_adj.py, which follows the course PPT. Detailed downstream analyses use the adjusted baseline.

### Slide 02 — Research question and completed work

**What to cover:** Keep the opening brief. The main evaluation is 1976–2014. We have completed baseline evaluation and E1–E4; covariance and portfolio volatility targeting remain future work.

> Keep the opening brief. The main evaluation is 1976–2014. We have completed baseline evaluation and E1–E4; covariance and portfolio volatility targeting remain future work.

### Slide 03 — Coverage: the universe changes over time

**What to cover:** Full-panel missingness includes late starts and early endings. It is not the same as the rate of internal gaps. Do not interpret 34.45% as random data loss.

> The bars show how many valid monthly returns each market contributes. Wheat, ZW, has 551 observations, while Australian equity, AP, has only 75. About 34.45 percent of all possible panel cells are missing. That figure includes late starts and early endings, so it should not be interpreted as random missing data. Historical portfolio composition therefore changes.

### Slide 04 — Different market risks motivate volatility scaling

**What to cover:** These are instrument medians with unequal histories, not asset-class portfolio volatilities. Almost all markets have positive estimated excess kurtosis, reinforcing the need to assess tails and drawdowns.

> These are instrument medians with unequal histories, not asset-class portfolio volatilities. Almost all markets have positive estimated excess kurtosis, reinforcing the need to assess tails and drawdowns.

### Slide 05 — Data quality: flags, reconstruction, and open checks

**What to cover:** Outlier flags are diagnostic, not automatic deletions. Daily reconstruction uses last available monthly closes and exact matching dates; it does not fully validate roll, collateral, or currency conventions.

> Outlier flags are diagnostic, not automatic deletions. Daily reconstruction uses last available monthly closes and exact matching dates; it does not fully validate roll, collateral, or currency conventions.

### Slide 06 — Cross-market correlation challenges independence

**What to cover:** Pearson correlations use at least 60 overlapping monthly observations. Class figures are equally weighted means of off-diagonal pairs, not portfolio correlations. Different pairs may use different periods. These are descriptive full-history estimates, not tradable forecasts.

> The heatmap shows that futures markets are not independent. Average within-class pairwise correlation is about 0.76 for equity indices and 0.62 for fixed income, compared with 0.15 for commodities and 0.28 for FX. These calculations require at least 60 overlapping months. Different pairs can use different historical periods. The key implication is that market count alone can overstate diversification.

### Slide 07 — EDA implications for strategy construction

**What to cover:** This slide connects observed data characteristics to the strategy. It does not imply that all remaining issues have already been fixed.

> The EDA leads directly to our design choices. Unequal histories motivate dynamic eligibility. Different volatility levels motivate inverse-volatility positions. Extreme observations motivate tail and drawdown analysis. Strong correlations motivate risk-model validation. We still need to resolve the RL discrepancy and test outlier sensitivity. With that context, we can now explain the main strategy.

## Part 2 — Both baselines, lookbacks, and performance

**Slides 8–19.**

### Slide 08 — Two baseline versions: rolling and course PPT

**What to cover:** We have two baselines: rolling_backtest.py and strategy_backtest_adj.py, the course PPT approach. Both estimate risk using historical information and execute next month. Both use annualized arithmetic mean divided by volatility for zero-RF Sharpe. Gross rolling Sharpe is 1.06 and adjusted Sharpe is 0.97. Subsequent attribution, factor, risk, and SG Trend analyses use standardized adjusted-baseline outputs.

> We have two baselines: rolling_backtest.py and strategy_backtest_adj.py, the course PPT approach. Both estimate risk using historical information and execute next month. Both use annualized arithmetic mean divided by volatility for zero-RF Sharpe. Gross rolling Sharpe is 1.06 and adjusted Sharpe is 0.97. Subsequent attribution, factor, risk, and SG Trend analyses use standardized adjusted-baseline outputs.

### Slide 09 — The course PPT approach: adjusted baseline

**What to cover:** The divisor counts vol.notna(). A market with valid volatility but a missing consecutive signal window remains in the divisor and receives a zero signal.

> Our main baseline follows strategy_backtest_adj.py, the course PPT approach. For each market, we take the sign of the sum of its past 12 monthly returns. We estimate annualized volatility from available history through the formation month, requiring at least 36 valid observations. We multiply the signal by 40 percent divided by volatility, then divide across the eligible universe. The 40 percent parameter is instrument-level scaling, not a portfolio volatility target.

### Slide 10 — Execution timing and assumptions

**What to cover:** 

> Weights formed in month t are applied to returns in month t plus one. This one-month shift prevents us from trading on the return we are trying to predict. The adjusted risk estimate also uses only available history. However, missing held-market returns are filled with zero, and we omit leverage caps, financing, margin constraints, and explicit roll costs. The baseline risk model assumes zero covariance.

### Slide 11 — Momentum signals contain predictive information

**What to cover:** Signal diagnostics use a different sample and eligibility definition from the full 1976–2014 portfolio backtest. HAC statistics use monthly aggregated equal-weighted signed returns to account for within-month market dependence.

> We tested four lookback periods: one, three, six, and 12 months. All have positive next-month return spreads and directional hit rates above 50 percent. The 12-month signal reaches a 54.4 percent hit rate and the highest volatility-scaled Sharpe in these diagnostics. The three-month signal is also strong. These are signal tests, not the full portfolio backtest. The separate adjusted lookback backtests have Sharpes of about 0.72, 0.81, 0.77, and 0.97, respectively. This supports studying multiple horizons rather than claiming that 12 months is universally optimal.

### Slide 12 — Four lookbacks: complete portfolio backtests

**What to cover:** We tested four horizons, not an exhaustive parameter search. Twelve months has the strongest in-sample portfolio Sharpe. Signal diagnostics use different eligibility and samples. E3 later combines these four signals instead of selecting one solely by full-sample results.

> We tested four horizons, not an exhaustive parameter search. Twelve months has the strongest in-sample portfolio Sharpe. Signal diagnostics use different eligibility and samples. E3 later combines these four signals instead of selecting one solely by full-sample results.

### Slide 13 — Volatility persists more than raw returns

**What to cover:** 

> Absolute returns have much stronger lag-one persistence than raw returns: about 18.4 percent versus 6.2 percent on average. This is consistent with volatility clustering and supports using historical volatility as a risk input. It does not guarantee accurate portfolio forecasts. It also motivates comparing expanding estimates with faster methods such as EWMA.

### Slide 14 — Main results: stronger returns and smaller drawdowns

**What to cover:** All main performance results use the adjusted baseline. Sharpe assumes a zero risk-free rate; factor regressions separately use excess returns.

> Over 1976 through 2014, the adjusted TSMOM strategy earns a 10.64 percent CAGR and a Sharpe ratio of 0.97, compared with 5.91 percent and 0.47 for static long exposure. TSMOM also has lower volatility and a much smaller maximum drawdown. This suggests that changing position direction adds value in this historical sample. The cost is substantially higher turnover.

### Slide 15 — Compounded wealth of the main strategy

**What to cover:** The chart compounds realized monthly portfolio returns. Compounded wealth is consistent with a summed-return momentum signal.

> This chart compounds the realized monthly portfolio returns. It visualizes the cumulative difference between momentum and static exposure over the main sample. The important distinction is that the adjusted signal uses summed past returns, while portfolio wealth still compounds. A summed signal does not imply that investment returns are added without compounding.

### Slide 16 — Drawdowns: the cost of staying invested

**What to cover:** Discuss the depth and persistence of losses rather than only final wealth. The strategy still has material drawdowns, despite a smaller worst loss than static.

> Discuss the depth and persistence of losses rather than only final wealth. The strategy still has material drawdowns, despite a smaller worst loss than static.

### Slide 17 — Exposure: implicit leverage and average long bias

**What to cover:** Gross exposure sums absolute weights and net exposure sums signed weights. The instrument-level 40 percent scaling does not impose a portfolio leverage cap or a fixed risk target.

> Gross exposure sums absolute weights and net exposure sums signed weights. The instrument-level 40 percent scaling does not impose a portfolio leverage cap or a fixed risk target.

### Slide 18 — Rolling performance varies across periods

**What to cover:** Discuss variation in realized volatility and risk-adjusted performance. Full-sample averages conceal changes through time and motivate walk-forward evaluation.

> Discuss variation in realized volatility and risk-adjusted performance. Full-sample averages conceal changes through time and motivate walk-forward evaluation.

### Slide 19 — Transaction costs and turnover

**What to cover:** 

> We charge costs on each one-way change in target weight. At 25 basis points, CAGR declines from 10.64 to 8.68 percent and Sharpe declines from 0.97 to 0.81. The strategy remains profitable under the tested assumptions, but these are illustrative costs. They do not include contract-specific spreads, roll, financing, or market impact. Higher-turnover enhancements need their own cost analysis.

## Part 3 — Return attribution, risk, and benchmarks

**Slides 20–29.**

### Slide 20 — Return sources: every asset class contributes

**What to cover:** Annualized arithmetic contributions are additive. This is not a decomposition of asset-class CAGRs.

> All four asset classes contribute positively to annualized arithmetic returns. Commodities generate about 47.8 percent of the total, followed by FX, fixed income, and equities. Long positions contribute 81.2 percent, while shorts contribute 18.8 percent. This shows breadth, but also concentration in commodities and longs. These contributions add to arithmetic mean returns; they are not a decomposition of CAGR.

### Slide 21 — Asset classes and trading direction generate returns

**What to cover:** These are additive arithmetic return contributions, not CAGR components. Long positions provide 81.2 percent of the mean return and short positions 18.8 percent.

> These are additive arithmetic return contributions, not CAGR components. Long positions provide 81.2 percent of the mean return and short positions 18.8 percent.

### Slide 22 — Market-level attribution reveals concentration

**What to cover:** Look at the spread of contributions, not only the winners. Return attribution identifies concentration but does not establish that recent winners will remain profitable.

> Look at the spread of contributions, not only the winners. Return attribution identifies concentration but does not establish that recent winners will remain profitable.

### Slide 23 — Return attribution by regime and decade

**What to cover:** Bear events are an internal futures proxy: peak-to-recovery events that subsequently reach a 20% drawdown. This retrospective classification is not a live trading signal or an official cash-index regime. The 1970s sample begins in 1976.

> The strategy has positive returns in both internal bull and bear regimes and in every reported decade. Bear-regime volatility is higher, even though average returns remain positive. The 2010–2014 period is weaker than earlier periods. Our regimes use an S&P futures drawdown proxy identified retrospectively. They are descriptive categories, not a real-time trading signal or an official cash-index classification.

### Slide 24 — Six-factor regression: significant momentum exposure

**What to cover:** Monthly excess-return regression with Newey–West HAC standard errors, three lags. Future analysis should include carry, trend, duration, USD, and other futures-relevant factors.

> Over 2000 through 2014, the joint six-factor regression estimates annualized alpha of 7.20 percent and explains 28 percent of variance. Momentum has the clearest significant positive exposure, while market and size betas are close to zero. This is consistent with the strategy’s design. However, equity factors are incomplete controls for diversified futures, so residual alpha should not automatically be interpreted as manager skill.

### Slide 25 — Many markets, concentrated asset-class risk

**What to cover:** Risk shares here are internal diagonal-model w²σ² contributions. They omit covariance and are not a complete attribution of actual portfolio risk.

> We now move from where returns come from to where risk comes from. Under the diagonal model, commodities account for 62.7 percent of average predicted variance. The effective number of instrument risk positions is 39.6, but the effective number of asset-class positions is only 2.35. The portfolio is broad across contracts but concentrated across asset classes. These shares describe the model’s internal view and omit covariance.

### Slide 26 — The diagonal model understates future risk

**What to cover:** Future fixed-weight volatility differs from the 11.15% volatility of the monthly rebalanced strategy. Overlapping forecast windows are not independent observations.

> To validate the risk model, we freeze formation-date weights and compare predicted volatility with realized volatility over the following 12 months. Average predicted volatility is 6.82 percent, while realized volatility is 9.78 percent. Realized risk exceeds the forecast in 74.8 percent of observations. The three-month check also shows underestimation. This isolates risk forecasting from later trading decisions.

### Slide 27 — Weak linear risk-forecasting power

**What to cover:** This test provides direct motivation for covariance-aware risk estimation and a portfolio-level volatility target.

> The scatterplot complements the average forecast error. Prediction and realized volatility have a correlation of only 0.13 at the 12-month horizon. The model therefore has both downward bias and weak linear forecasting power. Ignoring correlated positions is a plausible contributor, although it is not the only possible cause. This is our strongest direct motivation for covariance-aware portfolio risk.

### Slide 28 — SG Trend: shared trend exposure, different drawdowns

**What to cover:** SG Trend differs in markets, fees, risk targets, and rules. This comparison is descriptive, not evidence of exact replication or superiority.

> The SG Trend comparison uses the common 2000–2014 sample. Our baseline has higher return and Sharpe, but also a deeper maximum drawdown: about 26 percent versus 18 percent. Correlation is 0.62, consistent with shared trend exposure. Differences in markets, fees, signals, and risk targets mean this is a descriptive comparison, not evidence that we exactly replicate or dominate a professional index.

### Slide 29 — Compounded performance versus SG Trend

**What to cover:** Additional volatility-matched comparisons use full-sample realized volatility. They are retrospective comparisons, not tradable dynamic risk targets.

> The wealth paths help show how the strategies differ through time, beyond their average statistics. We also examine volatility-matched comparisons, but those use full-sample realized volatility for scaling. They are useful for retrospective comparison and are not a tradable dynamic targeting rule. The benchmark evidence supports meaningful trend exposure while leaving clear implementation differences.

## Part 4 — Robustness and enhancement experiments

**Slides 30–36.**

### Slide 30 — Rolling baseline: performance and cost sensitivity

**What to cover:** This is the rolling version of our baseline, not merely a robustness variant. We show only rolling_tsmom and rolling_static results. Costs use one-way absolute target-weight changes. Different samples and constructions prevent claiming that the higher gross Sharpe alone establishes superiority.

> This is the rolling version of our baseline, not merely a robustness variant. We show only rolling_tsmom and rolling_static results. Costs use one-way absolute target-weight changes. Different samples and constructions prevent claiming that the higher gross Sharpe alone establishes superiority.

### Slide 31 — Four completed PPT / adjusted experiments

**What to cover:** E2 equalizes class allocation without solving covariance-aware equal risk contribution. It does not guarantee 25% of actual risk per class.

> We completed four experiments around the adjusted baseline. E1 replaces expanding volatility with EWMA using a six-month half-life. E2 allocates equally across asset classes and then within each class. E3 averages the one-, three-, six-, and 12-month direction signals. E4 combines all three changes. E2 is a class-allocation rule, not a covariance-aware solution guaranteeing equal realized risk.

### Slide 32 — E1: faster volatility estimates

**What to cover:** Explain the volatility-estimation mechanism before the outcome. Growth and drawdown panels use retrospective matching to baseline volatility, whereas rolling volatility and turnover refer to unscaled results. Higher turnover needs its own cost test.

> Explain the volatility-estimation mechanism before the outcome. Growth and drawdown panels use retrospective matching to baseline volatility, whereas rolling volatility and turnover refer to unscaled results. Higher turnover needs its own cost test.

### Slide 33 — E2: allocation across asset classes

**What to cover:** E2 divides allocation equally across valid asset classes and then within each class. This is not covariance-aware equal risk contribution. A diversification objective can change performance and must be evaluated on both risk and costs.

> E2 divides allocation equally across valid asset classes and then within each class. This is not covariance-aware equal risk contribution. A diversification objective can change performance and must be evaluated on both risk and costs.

### Slide 34 — E3: combine four signal horizons

**What to cover:** The averaged signal can take intermediate values, reducing position size when horizons disagree. It reduces dependence on a single lookback but increases turnover. Similar Sharpe does not mean identical risk or implementation burden.

> The averaged signal can take intermediate values, reducing position size when horizons disagree. It reduces dependence on a single lookback but increases turnover. Similar Sharpe does not mean identical risk or implementation burden.

### Slide 35 — E4: combined changes are not automatically better

**What to cover:** The interaction of the three changes does not preserve every individual benefit. Gross Sharpe is below baseline, despite improvements in matched-volatility drawdown. Treat this as evidence against assuming improvements are additive.

> The interaction of the three changes does not preserve every individual benefit. Gross Sharpe is below baseline, despite improvements in matched-volatility drawdown. Treat this as evidence against assuming improvements are additive.

### Slide 36 — Experimental improvements do not simply add up

**What to cover:** Matched volatility uses full-sample scaling to the baseline 11.15%, so it is retrospective. Experiment results are gross. Baseline transaction-cost results cannot be applied directly to experiments.

> E1 improves gross Sharpe to 1.12, but increases turnover. E3 has a Sharpe close to the baseline and reduces drawdowns, also with higher turnover. E2 and E4 have lower Sharpe than the baseline, so the benefits do not simply add up. Matched-volatility CAGR and drawdown use retrospective full-sample scaling. We still need separate cost and out-of-sample tests before selecting an enhancement.

## Part 5 — Conclusions, next steps, and reproducibility

**Slides 37–39.**

### Slide 37 — Findings: credible signal, incomplete risk model

**What to cover:** 

> Our main finding is that momentum has predictive information and produces attractive historical portfolio results. Returns are broad, but commodities and long positions dominate. The risk model is the clearest weakness because it understates future volatility and has limited forecasting power. Costs, leverage, and data assumptions matter. Enhancement results are promising in places, but they are not uniformly better.

### Slide 38 — Next stage: covariance and implementable risk control

**What to cover:** Covariance estimation and a portfolio-level volatility target have not yet been implemented in the current baseline.

> Our next priority is covariance-aware risk estimation, including rolling, EWMA, and shrinkage approaches. We will validate forecasts before adding portfolio volatility targeting and leverage limits. We also plan realistic costs, walk-forward evaluation, broader futures factors, and data sensitivity checks. We should separate improvements in risk measurement from changes in leverage, so we can identify what actually helps.

### Slide 39 — Reproducibility: two baselines, one attribution pipeline

**What to cover:** Reproduce the two baseline versions separately. Run baseline_performance_analysis.py before adjusted-baseline attribution, risk validation, and benchmark comparison. Do not assume that the rolling baseline has the same downstream attribution results.

> Reproduce the two baseline versions separately. Run baseline_performance_analysis.py before adjusted-baseline attribution, risk validation, and benchmark comparison. Do not assume that the rolling baseline has the same downstream attribution results.
