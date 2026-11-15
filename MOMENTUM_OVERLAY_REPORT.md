# Keep momentum and add a factor overlay

**Baseline clarification:** Mom here is class-neutral cross-sectional momentum
(XSMOM), not the project's original directional price-trend TSMOM in
`economic_trend.py`. Results here do not establish an improvement to that original
baseline. See `compare_momentum_definitions.py` and
`outputs/momentum_definition_comparison/` for the definition comparison.

Run `MPLCONFIGDIR=/private/tmp/orie-mpl python3 momentum_overlay.py` after
`select_factor_subset.py` has produced its training-only screening table.

## Construction and selection

Core is the direct XSMOM_12_1 strategy, not a tree prediction. Signals form at
month t and earn t+1 returns, with monthly rebalancing. Each sleeve is ranked
and centered within asset class, allocated equally across active classes and
gross-normalized. Blend core and overlay at 90/10, 80/20, 70/30 or 60/40, then
normalize the netted instrument weights to total gross exposure one. Reported
fractions describe sleeve budgets before netting; they are not a decomposition
of the final netted holdings. Equal gross is not equal realized volatility.

Predefined non-trend overlay candidates: mild worst monthly loss, low downside
risk, shallow drawdown, low tail loss, low volatility, low kurtosis and negative
skewness. All pass the prior train-only positive IC / HAC t>=1 gate, using
labels through November 1994. An equal-weight basket of those seven is another
candidate. This gives 32 overlay configurations plus a Mom-only option.
Select once by net Sharpe on the **1995–2004 validation period**, using a common
117-month intersection. No 2005 onward returns enter selection. Negative
skewness means ranking higher instruments with more negative trailing
12-month sample skewness; it is a hypothesis, not a hedging guarantee.

Validation selected **80% Mom + 20% negative-skewness sleeve**: net Sharpe
0.9046 versus 0.8809 for Mom. This small selection margin across 33 candidates
is vulnerable to estimation noise and multiple comparisons.

## Later-period comparison: 2005–2014

| Portfolio | Net annualized mean | Net CAGR | Net Sharpe | Net max drawdown | Annual turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mom | 0.57% | 0.54% | 0.22 | -6.14% | 4.74 |
| Selected 80/20 Mom + negative skew | **0.84%** | **0.81%** | **0.33** | **-5.68%** | 5.13 |
| Prespecified 80/20 Mom + equal defensive basket | 0.61% | 0.58% | 0.23 | -6.52% | 4.74 |

All have mean gross exposure 1. The selected mix improves annualized net mean
by about **0.26 percentage points**, with net volatility 2.51% versus 2.59%
for Mom. These are unlevered research portfolios; the result is not a claim
about a higher-volatility implementation or the original course TSMOM strategy.

| Period | Mom net Sharpe | Selected mix net Sharpe |
| --- | ---: | ---: |
| 2005–2009 | 0.32 | 0.40 |
| 2010–2014 | 0.13 | 0.27 |

Both descriptive subperiods improve. This alone is insufficient to establish
statistical significance or future performance. The equal defensive basket
does not deliver a comparable improvement, so adding arbitrary factors is not
supported by this experiment.

## Accounting, checks and limits

Costs are 10 bps per dollar of actual netted trade, using drifted previous
holdings; costs are not computed by summing sleeve costs. Tests checked unit
gross after netting, one-month execution lag, entry costs and invalidation
when a held return is missing. Formation uses causal signal functions already
checked by future-data perturbation in preceding experiments.

Portfolios run continuously through history and retain their positions at the
start of 2005, rather than restart from cash on that date. This explains a small
Mom return difference versus the earlier tree comparison, which entered from
cash. Here both core and overlay use the same accounting and date sample.
Metrics use 116 common valid months; missing held returns or prior held returns
invalidate a month. Compounded paths chain valid observations without filling
missing months, so CAGR and drawdown do not reconstruct missing calendar P&L.

The 2005–2014 period and full-history candidate factors were previously
inspected. This is a development comparison, not a pristine holdout. The cost
model omits full roll/impact details; continuous-futures and historical-universe
biases remain. Validation selection is weakly separated and should be frozen
before any future post-2014 evaluation. No significance or robust alpha claim
is made.

Artifacts: `outputs/momentum_overlay/selection.json`, validation candidates,
comparison summaries/subperiods, net monthly returns, selected formation weights
and all-candidate returns for audit. The latter must not be used to retrospectively
pick a different winner on the comparison period.
