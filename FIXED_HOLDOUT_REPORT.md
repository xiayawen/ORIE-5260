# Fixed 2015–2025 holdout, no walk-forward refitting

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 fixed_2015_holdout.py`.

## Interpretation of the requested split

All data before 2015 are development/in-sample data. Split that development
period chronologically to choose a classifier and overlay share, then refit
the chosen classifier **once on all eligible pre-test labels**. Freeze both
the classifier and its fitted imputer throughout January 2015–May 2025.
There is no annual retraining, rolling training window or OOS model update.

Monthly features, positions and trailing risk estimates still update using
observed returns. They are components of the predeclared trading rule, not
supervised model refitting. This distinction matters for volatility targeting.

## Exact splits

All dates below describe realized labels unless noted otherwise:

| Stage | Dates | Nonzero observed labels |
| --- | --- | ---: |
| Initial classifier fitting | February 1970–November 2004 | 13,191 |
| Validation model selection | January 2005–November 2014 | 6,811 |
| Final classifier refit | February 1970–November 2014 | 20,059 |
| Fixed test | January 2015–May 2025 | 6,919 |

1969 observations initialize signals and volatility; first eligible formation
is January 1970. The final refit includes the earlier validation data, which
is standard once model/share choices are fixed. November 2004 is the last
label before the first validation formation (December 2004). November 2014
is the last final-training/selection label before first test formation
(December 2014); December 2014 labels are conservatively embargoed. Thus the
phrase "all pre-2015 data" means all usable history subject to feature warmup,
observed nonzero labels and the one-month boundary embargo.

Use original MonthlyReturns.csv through 2014 and append only later workbook
months to avoid retroactively revising historical inputs. Data audit/hash and
missingness comparisons are exported.

## Choices made exclusively inside development data

Compare fixed-specification logistic regression, random forest, Extra Trees
and HistGB classifiers. Features are the same 31 raw signals, 31 class-relative
rank signals and four class indicators. Label is next-month raw return >0 vs
<0; zero/missing returns are excluded from classification training/metrics.

Validation log loss selects **Extra Trees**, 200 trees, depth6, minimum leaf30,
feature fraction .7, seed5260; validation log loss .68673, AUC .54893. Each
initial model has training-only median imputation; logistic also standardizes
from its training data. No test thresholding or calibration is performed.

The selected model's 2005–2007 out-of-training predictions warm up portfolio
risk history. Compare 0%, 10%, 20% and 30% classifier sleeve budgets using
January 2008–November 2014 validation net Sharpe. Select **30%** (Sharpe .947
versus .800 for original TSMOM in that same interval). Thus final strategy is
70% original TSMOM plus 30% soft classifier direction, then native blend risk
scaling. Direction = 2*p(up)-1. Final imputation and Extra Trees are then fitted
anew using the 20,059 development labels, with no further refitting after 2014.

Avoid in-sample risk initialization: splice the earlier model's genuinely
out-of-training validation forecasts into the final model's test forecasts.
The earlier model also makes the December 2014 return forecast; its outcome
may inform the December 2014 risk estimate once observed, but it never enters
classifier fitting/selection. A model switch at the first test formation is
charged through ordinary target-weight-change turnover.

## Fixed-test results: January 2015–May 2025

Original trading rules and costs are unchanged: monthly rebalancing, 10%
portfolio volatility targeting, 2 bps per dollar of target-weight changes and
quarterly rolls at 2 bps of gross exposure. Risk targeting permits leverage.

| Strategy | Annual mean net | Net CAGR | Cumulative net | Net Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original TSMOM | 0.40% | -0.16% | -1.61% | .038 | -24.71% |
| Selected 70/30 TSMOM + Extra Trees | 0.94% | 0.45% | 4.74% | .094 | -19.43% |
| Extra Trees sleeve standalone, diagnostic | 2.14% | 1.61% | 18.11% | .206 | -19.30% |

Selected strategy realized volatility is 10.01%, average gross leverage 4.48
and annual native costs about .68%. Original TSMOM is 10.59%, 4.44 gross and
.64% costs. Standalone results do not authorize choosing a new strategy on
the test sample; the allocation selected before test was the 70/30 mix.

The classifier's test accuracy is 52.04%, balanced accuracy 51.52%, AUC .5226
and log loss .6952. Always-up accuracy is 52.03%; the final-training-prior
constant probability has lower test log loss .6924. Predictive improvement
is therefore weak and does not establish robust alpha.

## Checks and limitations

Checks passed: training and selection labels strictly precede test formation;
imputer statistics equal training-only medians; replacing every post-2014
return leaves final training features/labels and January 2015 probabilities
unchanged; saved first-month probabilities are reproducible. Weights are finite
and prediction formation dates strictly precede return realization dates.

Native missing-held-return zero treatment is retained for comparability.
Excluding the six common affected test months gives 119 retained observations
and Sharpe .160 for the selected strategy versus .076 for original TSMOM.
These retained-month paths are sensitivities, not reconstructed continuous
P&L. Full impact/slippage, historical-universe and continuous-contract risks
remain. Models fixed before 2015 may still become stale during the decade.

This is a fixed, chronological train/test separation by fitting rules. The
2015–2025 sample has already been examined in prior experiments in this
conversation, so it cannot be made statistically pristine by relabeling it
"OOS". Subsequent choices based on this result would consume the same sample
again. Do not compare this with the rolling-model experiment as a pure change
in retraining alone: this experiment also selects Extra Trees using a different
internal validation interval and includes earlier eligible training history.

Artifacts under `outputs/fixed_2015_holdout/`: exact split audit, selection
rankings/config, fixed-test probabilities, performance/subperiod summaries,
net returns, holdings, strict sensitivity, data audit and P&L/drawdown chart.
