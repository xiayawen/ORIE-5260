# Annual rolling-window sign prediction

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 rolling_sign_prediction.py`.
The classifier is the previously fixed HistGB sign model. This experiment
changes its training schedule/window, not features, tree parameters, sign
thresholds, TSMOM baseline or execution/cost rules.

## Rolling procedure

Before forming the first forecast for each calendar return year, refit HistGB
and its median imputer using the preceding **15 or 20 years** of realized
labels. All labels must be strictly earlier than that first formation date.
Hold the model fixed for the next 12 return months, then roll forward and
refit. Features and portfolio volatility estimates still update monthly.
Missing and exact-zero targets are excluded from classification training and
metrics. Previously observed labels are allowed at subsequent annual refits;
future labels and observations outside the rolling window are excluded.

Example for forecasts earning returns in 2015:

| Window | Training label range | First prediction formed | First return realized |
| --- | --- | --- | --- |
| 15 years | December 1999–November 2014 | December 2014 | January 2015 |
| 20 years | December 1994–November 2014 | December 2014 | January 2015 |

December 2014 realized labels are conservatively embargoed at that boundary.
In 2016 the training window advances by one year and includes known 2015 labels
through November. No December/current-month label is taken from the future.

## Validation and portfolio selection

Rolling forecasts start in 1997 so both windows have adequate calendar history.
1997–1999 provides out-of-training sleeve risk history. Validation is
**2000–2004**, kept before 2015; this differs from the earlier frozen-model
validation start because the 20-year window needs its own live warmup.
Both windows and the frozen control share this same forecast launch for risk
warmup. No in-sample forecasts or pre-launch zeros set sleeve volatility.

Compare 10%, 20% and 30% sign-probability sleeves, plus original TSMOM and a
rescaled-only control. Select on validation net Sharpe; there are eight options.
The winner is **70% TSMOM + 30% 15-year rolling HistGB**, validation Sharpe
1.2401 versus 1.2210 for original TSMOM. This is a small validation margin.
2005–2014 is exported as a descriptive intermediate check, never used to
change the selected window. No 2015 onward result selects the configuration.

Soft direction = 2*p(up)-1. Monthly inverse-volatility sizing, a 10% target
portfolio volatility, blend re-scaling, 2 bps target-weight trading costs and
quarterly roll costs reuse the original strategy. The model has 31 raw and
31 relative-rank features plus four class indicators. No classifier probability
threshold, calibration, feature selection or hyperparameter retuning is added.

## Later-period results: January 2015–May 2025

| Strategy | Annual mean net return | Net CAGR | Net Sharpe | Cumulative net return | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original TSMOM | 0.40% | -0.16% | 0.038 | -1.61% | -24.71% |
| Frozen-1994 classifier 30% mix | 0.60% | 0.06% | 0.057 | 0.65% | -20.18% |
| **Selected 15-year rolling 30% mix** | **1.19%** | **0.71%** | **0.121** | **7.61%** | **-21.20%** |
| Fixed 20-year rolling 30% mix | 0.92% | 0.44% | 0.094 | 4.73% | -19.85% |

The selected mix improves on the frozen model in return and Sharpe, but its
drawdown is slightly larger. Realized volatility is 9.84% and mean gross
leverage is 4.41 versus frozen mix 10.38% / 4.23. Performance remains weak.
Standalone 15-year classifier has net Sharpe 0.192 and drawdown -28.14%; this
is diagnostic, not a reason to retrospectively replace the selected blend.

| Classifier | Accuracy | Balanced accuracy | AUC | Log loss |
| --- | ---: | ---: | ---: | ---: |
| Frozen 1994 | 51.05% | 50.98% | 0.5112 | 0.7005 |
| Rolling 15 years | 51.70% | 50.89% | 0.5166 | 0.6963 |
| Rolling 20 years | 51.64% | 50.93% | 0.5165 | 0.6962 |

Positive prevalence is 52.03%, so always-up accuracy is higher than these
models. AUC and probability loss improve slightly, while balanced accuracy
does not. Pooled metrics alone do not establish significant predictive alpha.
Rolling-prior forecasts are also exported as probability baselines.

## Checks and interpretation

All 58 annual fits (1997–2025 for each of two windows) assert correct label
boundaries, rolling lower bounds, disjoint training/forecast samples and
imputer medians equal to training-only medians. Replacing **every post-2014
return** while keeping earlier inputs fixed leaves January 2015 forecasts
unchanged, verifying the first forecast cannot use its outcome or later data.

For compatibility, native missing-held-return zero treatment remains. Excluding
the same six affected later-period months yields net Sharpe 0.198 selected
rolling mix versus 0.105 frozen mix and 0.076 original TSMOM. These sensitivities
chain retained observations rather than repair missing investment P&L.
Costs omit full market impact, leverage is not capped and universe/continuous
contract selection can bias all strategies.

The supplied 2015–2025 period has already been inspected. This is a sequential,
past-only **historical rolling evaluation**, not a new untouched holdout.
Annual retraining is a predeclared rule using newly known historical labels;
that causal updating is distinct from tuning window/share on later outcomes.

Artifacts under `outputs/rolling_sign_prediction/`: annual date/sample audit,
instrument-level out-of-fold probabilities, selected configuration, validation
ranking, classification metrics, return paths, weights, subperiod summaries,
strict missing-return sensitivity and a cumulative P&L/drawdown chart.
