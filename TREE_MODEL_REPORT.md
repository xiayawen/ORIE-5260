# Next-month futures return prediction with a tree model

**Baseline clarification:** the XSMOM control is cross-sectional momentum, not
the project's original directional price-trend TSMOM in `economic_trend.py`.
Model comparisons here must not be presented as comparisons with that original
baseline.

## Design

Run `MPLCONFIGDIR=/private/tmp/orie-mpl python3 tree_factor_prediction.py`.
Each row is one instrument at formation month t. The target is its **raw return
in t+1**, not a return direction or volatility-normalized return. Features are
the 25 previously constructed signals plus static asset-class indicators.
Models pool instruments. Rebalancing and forecasts are monthly.

| Stage | Realized target dates | Labeled observations |
| --- | --- | ---: |
| Selection training | January 1976–November 1994 | 5,928 |
| Validation | January 1995–December 2004 | 5,788 |
| Final development refit | January 1976–November 2004 | 11,702 |
| Test | January 2005–December 2014 | 6,861 |

Split membership is determined by target dates. Earlier-stage labels must be
strictly earlier than the next stage's first formation date. Thus December
1994 and December 2004 labels are purged from the respective preceding fits.
Every instrument in a month stays in the same time partition. Training medians
impute missing features; test observations never set preprocessing statistics.
Eligibility uses only expanding volatility available at formation. Missing test
targets are excluded from forecast metrics but never used to select holdings.

Random forest: 200 trees, seed 5260, feature fraction 0.7. A fixed validation
grid of (depth, minimum leaf size) = (3,100), (6,100), (6,30) selects **(6,30)**
by validation MSE. The selected specification is refit once on development data
and remains frozen throughout the test. A fixed-alpha Ridge (100) is a linear
control; zero and development-period historical mean are constant controls.
There is no test-based tuning, feature selection or sign reversal.

## Held-out-time results

| Forecast | Test MSE | Test R² | Class-averaged Rank IC | Rank IC HAC(3) t |
| --- | ---: | ---: | ---: | ---: |
| Random forest | 0.004200 | -0.0105 | 0.0185 | 0.99 |
| Ridge | 0.004169 | -0.0030 | 0.0206 | 1.23 |
| Historical mean | 0.004158 | -0.0005 | undefined | undefined |
| Zero | 0.004166 | -0.0024 | undefined | undefined |
| XSMOM score | not a raw-return forecast | not applicable | 0.0341 | 1.56 |

IC uses the raw next-month return and the same at-least-four-markets-per-class,
at-least-two-valid-classes rule as the factor diagnostics. All three nonconstant
scores have 120 valid test IC months. Constant forecasts have undefined
cross-sectional IC. Raw-return MSE favors predicting larger-volatility markets
well, while class-averaged IC measures relative ranking; these are different
objectives. No test objective was used to choose the final model.

For a trading diagnostic, each score is ranked and centered within asset class,
then normalized to unit total gross exposure with equal active-class budgets.
These are class dollar-neutral portfolios, not beta-neutral portfolios. Costs
are 10 bps per dollar traded, including the first entry and drift-adjusted
rebalances, without the full futures roll/impact cost model.

| Strategy | Gross Sharpe | Net Sharpe | Net annualized arithmetic return | Net max drawdown |
| --- | ---: | ---: | ---: | ---: |
| Random forest | 0.26 | -0.14 | -0.34% | -12.16% |
| Ridge | 0.37 | 0.06 | 0.14% | -10.53% |
| XSMOM | 0.40 | 0.22 | 0.57% | -6.14% |

Portfolio comparisons use 116 common valid test months. Missing held returns
and missing prior held returns for drift/cost calculations invalidate a month;
they are not silently set to zero. Return paths chain the retained months;
drawdown/CAGR do not reconstruct missing months. All portfolios use the same
gross exposure constraint, not equal realized volatility. The last available
target month is December 2014. Subperiod prediction metrics are also exported.

The tree model does not beat simple controls in raw-return prediction and its
net trading result is negative under these assumptions. Ranking IC is positive
but weak. Training impurity importance is exported for inspection; correlated
features and differing split opportunities make it unsuitable as evidence of
independent alpha or causal importance.

## Bias checks and limits

Checks passed: perturbing all future returns leaves historical features
unchanged; label-date boundaries are strictly purged; fitted imputation medians
equal training-only medians; test predictions are finite. The data are monthly,
so this assumes month-end signals can earn the following supplied monthly return.
Actual next-session fills, data publication delays, roll construction and
historical universe selection require separate execution/data validation.

Importantly, these candidate factors were previously examined on the full
1969–2014 panel. This test is held out from **model fitting and model selection**,
but not a pristine holdout from the overall factor research process. No available
post-2014 data have been added to this experiment. The historical universe may
also carry survivorship/selection bias. Results are exploratory.

Artifacts in `outputs/tree_factor_prediction/`: split audit, model configuration,
validation grid, instrument-level test predictions, forecast metrics, monthly
and summary IC, weights, portfolio returns/summary and feature importance.
