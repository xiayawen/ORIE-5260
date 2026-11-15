# Additional 20 futures signal candidates

These are 20 additional **candidate signals**, not 20 independent established
risk premia. They extend the four price-based signals and TSMOM control in
`futures_factor_backtest.py`. Positive scores are bought relative to negative
scores within the same asset class. Directions and windows are fixed before
examining results; no sign flipping or parameter search is performed.

Here `r` is monthly futures return, `sd12` is trailing 12-month standard
deviation, and all windows end at formation month t unless shifted.

| # | Code | Hypothesis / score (higher is long) | Family |
| --- | --- | --- | --- |
| 1 | Reversal_3m | Negative 3-month summed return / sd12 | Reversal |
| 2 | LongReversal_36_12 | Negative sum from t-35 through t-12 / sd12 | Long reversal; not fundamental value |
| 3 | NegativeSkew_12m | Negative sample return skewness | Distribution / lottery |
| 4 | LowKurtosis_12m | Negative excess kurtosis | Tail risk |
| 5 | LowMaxReturn_12m | Negative largest monthly return | Lottery |
| 6 | MildWorstReturn_12m | Smallest monthly return, preferring less negative | Tail risk |
| 7 | LowTailLoss_12m | 10th percentile monthly return | Tail risk |
| 8 | LowUpsideRisk_12m | Negative RMS of positive returns, zeros otherwise | Semivolatility |
| 9 | RiskAsymmetry_12m | (Mean squared positive returns minus mean squared negative returns) / sd12² | Asymmetry |
| 10 | VolCompression_3_12 | Negative 3-month SD / sd12 | Volatility regime |
| 11 | LowVolOfVol_12m | Negative SD / mean of the past 12 monthly sd12 estimates | Risk stability |
| 12 | ReturnPersistence_12m | Lag-one correlation of returns within 12 months | Serial dependence |
| 13 | Seasonality_5y | Mean returns at t-11, t-23, t-35, t-47, t-59 | Calendar |
| 14 | TrendEfficiency_12m | Sum of log returns / sum of absolute log returns | Trend path |
| 15 | TrendAcceleration_3m | (Latest 3-month sum minus preceding 3-month sum) / sd12 | Trend change |
| 16 | MeanToVol_12m | Mean monthly return / sd12 | Risk-adjusted trend |
| 17 | NearWealthHigh_12m | Terminal log wealth minus highest log wealth in 12-month local path | Trend proximity |
| 18 | ShallowDrawdown_12m | Worst log drawdown in a 12-month local wealth path, preferring shallower | Path risk |
| 19 | PositiveMonthShare_12m | Fraction of strictly positive months | Trend consistency |
| 20 | MedianReturn_12m | Median monthly return / sd12 | Robust trend |

Wealth paths start at zero log wealth at each window's beginning and use
`log(1+r)`. They are synthetic total-return paths, not actual futures-price
highs, spot valuations, or roll yields. Returns at or below -100% invalidate
log-path windows. Seasonality requires all five historical observations.

## Research context

Value and momentum are documented across multiple asset classes in
[Asness, Moskowitz and Pedersen](https://www.aqr.com/insights/research/journal-article/value-and-momentum-everywhere).
Low-beta investing is studied across futures and other markets in
[Frazzini and Pedersen](https://www.nber.org/papers/w16601).
These papers motivate broader research beyond momentum; they do **not**
validate all 20 formulas above. The present formulas are transparent exploratory
price-only proxies and variants, not reproductions of those papers' portfolios.

Carry, fundamental value, liquidity and positioning remain separate candidates
requiring contract curves, fundamentals, daily volume/open interest or CFTC data.
The 20 candidates here deliberately run on the existing monthly return panel.

## Evaluation and limitations

### Monthly IC diagnostics

Run `python3 futures_factor_ic.py` to generate `ic_monthly.csv` and
`ic_summary.csv` in the factor output directory. IC is cross-sectional Pearson
correlation of formation-month raw scores and next-month raw returns; Rank IC
is Spearman correlation with average ranks for ties. Only markets with known
scores, expanding volatility eligibility and observed forward returns enter.
At least four paired markets and nonconstant observations are required.
The primary `within_class_equal` measure equally averages valid class ICs each
month and requires at least two valid classes. Individual classes and pooled
`all_markets` are also exported. This class average is not a pooled neutralized
correlation. Scores, rather than final portfolio weights, are evaluated.

Rebalancing remains monthly, using information through t and holding at t+1.
IC is gross predictive association, with no transaction-cost adjustment.
The evaluation begins with returns realized in January 1976; no unobserved
forward returns are fabricated at the sample endpoint. Each factor uses its own
valid months, so sample counts differ (particularly sign-only TSMOM, whose
within-class scores are sometimes constant). ICIR is mean IC / sample SD;
annualized ICIR multiplies this by sqrt(12). Mean t statistics use HAC with
three calendar lags, preserving missing calendar months in the estimating
equation. Pre/post-2000 summaries are included. T statistics are descriptive
and have no adjustment for examining many related signals.

Run `python3 futures_factor_backtest.py`. Outputs use the same delayed execution,
class-neutral ranks and 10 bps turnover cost assumptions described in README.
The 25 portfolios now share a new common-month sample; compare the newly
generated CSVs rather than mixing their figures with the earlier five-factor run.
The older five-factor figures in README describe that earlier experiment.
Missing held returns are excluded and reported in each coverage file.

The summary includes pre-2000 and 2000-onward descriptive splits. Both have
already been observed: neither is a pristine holdout. Examining 20 signals
creates multiple-testing risk. Tail-risk variants and trend variants are
expected to overlap, so count families and inspect return correlations before
claiming diversification. Full-sample Sharpe alone does not establish alpha.
