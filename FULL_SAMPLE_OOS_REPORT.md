# Frozen-strategy out-of-sample results: January 2015–May 2025

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 out_of_sample_full_data.py`.
An optional `--data /path/to/MonthlyReturns_FullSample.xlsx` overrides the input.

## Input and freezing

The supplied workbook covers February 1969–May 2025 with 58 instrument columns
and no missing calendar months. Post-2014 contains 125 months. The 551
overlapping months agree numerically to within 4.66e-8 where both files observe
a return, but six cells disagree in missingness. Keep original MonthlyReturns.csv
through December 2014 and append only January 2015 onward, so new historical
data cannot retroactively change the fitted models, signals or selections.
The input SHA256, coverage, differing missing cells and largest returns are
exported. No return winsorization or outlier-driven parameter changes occur.

Frozen strategies, all chosen before viewing this new period:

- Original TSMOM: original `economic_trend.py` rules.
- Rescaled-only TSMOM control.
- 70/30 TSMOM + residual momentum, selected in the previous rank/factor study.
- 80/20 TSMOM + negative skewness, selected in the earlier factor study.
- 70/30 TSMOM + HistGB sign-probability sleeve, selected in the sign study.
- HistGB sign-probability sleeve standalone, as a diagnostic.

All classifiers remain fitted to labels ending November 1994. No OOS fitting,
calibration, feature selection, model selection or blending optimization occurs.
Risk forecasts and signals update using available past observations, as required
by the previously fixed rolling strategy; this is not OOS parameter tuning.
Positions carry across December 2014/January 2015 rather than restart in cash.

## Main results

Original risk/cost method: monthly execution, 10% target annual volatility,
2 bps per dollar of target-weight change plus four annual rolls at 2 bps of
gross exposure per roll. Futures leverage is permitted. These are the same
native accounting rules used in the preceding original-TSMOM experiments.

| Strategy, 125 OOS months | Annual mean net return | Net CAGR | Net Sharpe | Cumulative net return | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original TSMOM | 0.40% | -0.16% | 0.038 | -1.61% | -24.71% |
| Rescaled-only TSMOM | 0.48% | -0.05% | 0.046 | -0.56% | -24.67% |
| Residual-momentum 30% mix | -0.37% | -0.88% | -0.036 | -8.82% | -29.88% |
| Negative-skewness 20% mix | 0.13% | -0.40% | 0.013 | -4.08% | -22.81% |
| Sign-HistGB 30% mix | 0.60% | 0.06% | 0.057 | 0.65% | -20.18% |
| Sign-HistGB standalone | 0.55% | 0.03% | 0.054 | 0.35% | -17.21% |

Annual arithmetic mean and CAGR differ because roughly 10% annual realized
volatility consumes much of the small arithmetic mean through compounding.
These results do not demonstrate a reliable positive return for any strategy.
The sign mix's relative improvement is small and must not become a new winner
selected retrospectively on this OOS sample.

The prior residual-momentum result does **not** generalize:
its 2005–2014 net Sharpe was 1.104, versus -0.036 after 2014. Original TSMOM
also falls from 0.891 to 0.038. This supports the importance of separating
the historical development sample from later data; it does not identify a
single causal explanation for the performance decline.

| Period | Original TSMOM Sharpe | Residual mix Sharpe | Sign mix Sharpe |
| --- | ---: | ---: | ---: |
| 2015–2019 | 0.014 | -0.220 | 0.035 |
| 2020–May 2025 | 0.060 | 0.156 | 0.082 |

The sign classifier's OOS accuracy is 51.05%, balanced accuracy 50.98%,
AUC 0.5112 and log loss 0.7005 on 6,919 nonzero-return instrument-months.
Positive prevalence is 52.03%, so always predicting up has higher raw accuracy
while no discrimination (AUC .5). The classifier provides little OOS separation.

## Reproduction and missing-return checks

Recomputing all strategies on the full file reproduces every previously
evaluated holding before 2015 exactly, within floating-point tolerance. The
comparison checks formation through November 2014 / execution through December
2014: historical runners omitted their final formation row when no forward
label date existed. This terminal bookkeeping row is not treated as evidence
of future-data leakage. Model training boundaries, prediction-before-target
dates, exact sign-label construction and finite weights are asserted.

For native comparability, missing held returns are still treated as zero.
Affected OOS months are June 2015, January 2017, December 2021, June 2022,
May 2023 and February 2025. Excluding these six dates for every strategy leaves
119 common months, with Sharpe 0.076 original, 0.028 residual mix and 0.105
sign mix. Results remain weak. These strict paths chain retained months and
do not reconstruct missing P&L, so their CAGR/drawdown are sensitivities rather
than a repaired continuous investment history.

The original engine's target-weight-difference turnover and zero-filled risk
history are retained rather than silently changing execution assumptions.
Large observed returns, missing/discontinued contracts, historical-universe
selection, continuous-contract construction and absent market-impact costs
remain data/implementation risks. The data are historical returns, not a live
execution record. The post-2014 sample was not used for these choices in this
session; previous collaborators may already have examined it, so independence
from the team's broader research history is not guaranteed. Now that it has
been inspected, subsequent tuning on it is development work, not a fresh test.

Artifacts: `outputs/full_sample_oos/` contains the input audit/hash, frozen model
configuration, coverage, OOS forecasts, positions, monthly net returns, full and
subperiod summaries, strict sensitivity and PNG/PDF P&L/drawdown plots.
