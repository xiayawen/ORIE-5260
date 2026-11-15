# Predicting the sign of next month's futures return

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 sign_return_prediction.py`.

## Target and chronology

The label is 1 if raw next-month return is positive, 0 if negative. Exact zero
and missing returns are excluded from classification training and metrics;
zero is not silently relabeled down. Tradable eligible observations with zero
future return still enter portfolio P&L as observed zero. Eligibility uses the
original TSMOM 12-month instrument-volatility history, so observation counts
differ from the earlier 36-month-eligibility regression experiment.

Features comprise 31 raw signals, their current-month within-class percentile
ranks and four static asset-class indicators. Raw signals preserve absolute
directional information that class rankings alone discard. All transforms
use information through formation month t; labels realize in t+1.

Training realized labels run January 1976–November 1994 (6,637 nonzero observed
returns). The first forecast forms in December 1994 for January 1995, strictly
after the last training-label date. Models remain frozen. 1995–1997 predictions
warm up live risk estimates; validation is 1998–2004; 2005–2014 is the already
inspected later comparison period. There is no random row split, test tuning,
test calibration, test imputation or test-dependent threshold choice.

Models are logistic regression (C=.1, standardized), random forest and Extra
Trees (200 trees, depth6, leaf30, feature fraction .7), and histogram gradient
boosting (100 rounds, depth3, 8 leaves, leaf100, L2=10, learning rate .05,
early stopping disabled). Seed 5260. Missing-feature medians and logistic
scaling fit training data only. Classes are not artificially balanced.

## Classification results

Validation log loss selects **HistGB**: log loss 0.6836 and AUC 0.5785.
The later period has 6,863 labeled instrument-months, 54.63% positive:

| Forecast | Accuracy | Balanced accuracy | AUC | Log loss |
| --- | ---: | ---: | ---: | ---: |
| Logistic | 51.87% | 51.39% | 0.5165 | 0.7012 |
| Random forest | 52.98% | 52.43% | 0.5358 | 0.6922 |
| Extra Trees | 53.43% | 53.05% | 0.5352 | 0.6915 |
| HistGB (validation selected) | 53.17% | 52.67% | 0.5359 | 0.6940 |
| Always up (hard forecast) | 54.63% | 50.00% | 0.5000 | not a calibrated probability |
| Original TSMOM sign | 53.55% | 52.18% | 0.5218 | not a calibrated probability |

Always-up accuracy benefits from positive class prevalence and is not evidence
of discrimination. The frozen training positive fraction was 49.62%, so the
training-prior constant probability predicts down at the fixed .5 threshold;
its later accuracy is 45.37%, AUC .5 and log loss .6939. The sign distribution
shift is one reason to inspect balanced accuracy and probability metrics.
Hard controls' clipped log losses are exported for audit, not interpreted as
probability calibration. No claim of significant superiority is made from these
pooled metrics, whose observations share market/month dependence.

## Trading diagnostics using original TSMOM rules

Soft direction = 2*p(up)-1; hard direction = sign(p(up)-.5). These are
directional portfolios, not cross-sectionally neutral ones. No test-fitted
probability threshold is used. Apply original inverse-volatility sizing and
10% portfolio volatility targeting. Require 24 actual live monthly returns
before sleeve scaling, avoiding in-sample history or prelaunch zero risk.
Blend at 10%, 20% or 30% with original TSMOM, then apply original blend scaling.
Trading and quarterly roll costs exactly reuse `economic_trend.py`.

Validation selects HistGB soft with a 30% share among classifier overlays.
Including original TSMOM, rescaled-only TSMOM and the frozen prior residual
momentum combination, the overall validation winner remains the prior residual
momentum strategy. Later-period results:

| Strategy | Net annual mean | Net volatility | Net Sharpe | Net max drawdown |
| --- | ---: | ---: | ---: | ---: |
| Original TSMOM | 9.12% | 10.23% | 0.891 | -10.73% |
| Prior 70/30 TSMOM + residual momentum | 11.74% | 10.63% | 1.104 | -9.35% |
| 70/30 TSMOM + HistGB soft direction | 9.04% | 10.40% | 0.869 | -12.48% |
| HistGB soft direction alone | 5.96% | 10.22% | 0.583 | -13.75% |
| Vol-scaled always-long control | 7.76% | 10.85% | 0.715 | -27.70% |

Classifier probability vs next-month raw-return class-average Rank IC is
0.0093 for HistGB (HAC t .54), 0.0091 for RF, 0.0059 for Extra Trees and
-0.0255 for logistic. Predicting signs discards gain/loss size, so small
classification discrimination need not translate to profitable allocation.

## Checks and limitations

Checks passed: exact sign labels; exclusion of zero/missing targets from
classification; future-return perturbations leave historical raw/ranked
features and risk scaling unchanged; >=24 live observations before sleeve
launch; simple metric sanity checks. Strict split purging is asserted.

For native-method comparability, held missing returns are filled with zero
and turnover uses target-weight changes, matching the original engine.
Excluding two affected months on a matched basis yields original TSMOM
Sharpe .858, classifier blend .840 and prior residual mix 1.067, preserving
the conclusion. Gross leverage differs, native roll costs omit full market
impact, and historical-universe/continuous-contract construction can bias
results. Models frozen before 1995 may become stale. The comparison sample
has already been repeatedly inspected and is not an untouched holdout.

Artifacts in `outputs/sign_return_prediction/`: config, classification metrics,
instrument-level probabilities/labels, probability IC, validation portfolio
ranking, net return paths, holdings, subperiod results, missing-return sensitivity
and cumulative net P&L chart. All candidate returns are for audit, not for
retrospective selection on the later comparison period.
