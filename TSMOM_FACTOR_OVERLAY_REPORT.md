# Factor overlays on the original project TSMOM

Run `MPLCONFIGDIR=/private/tmp/orie-mpl python3 tsmom_factor_overlay.py` after
the training-only screen has been produced by `select_factor_subset.py`.

This experiment returns to `economic_trend.py`'s price-trend baseline, not
the XSMOM control used in earlier experiments. Baseline formation weights
exactly match `price_trend_weights`: sign of summed 12-month own returns,
inverse trailing 12-month instrument volatility with a 1% annual floor,
equal active-instrument denominator and lagged-history portfolio scaling
to a 10% annual volatility target (36-month window, minimum 24 observations).
Weights execute next month and rebalance monthly.

## Comparable sleeve construction

Each new factor's scores become centered percentile ranks within asset class,
with four valid instruments required. The continuous direction then goes through
the original inverse-volatility sizing and portfolio target-volatility scaling.
Blend 60–90% original TSMOM with 40–10% sleeve, and apply the original blend
scaling again, exactly as the economic-trend extension does. The equal defensive
basket is also scaled before blending. Fractions are pre-rescaling sleeve
budgets, not fractions of final gross exposure. TSMOM-only and a rescaled-only
TSMOM control are included to distinguish signal changes from extra risk scaling.

The same seven predefined non-trend families from the preceding overlay study
pass the train-only IC screen (labels through November 1994). Select among 32
blends plus the two TSMOM controls using 1995–2004 net Sharpe. The winner is
**80% TSMOM + 20% negative skewness** (validation net Sharpe 1.5252).
No new model, signal sign or parameter was chosen on the 2005–2014 results.

## Results

All accounting matches the original script: 2 bps per dollar of weight change,
four annual rolls charged at 2 bps of gross exposure per roll, and continuous
positions across period boundaries. These are different costs and risk budgets
from the earlier unit-gross XSMOM experiment, so do not compare their numbers
as if only the signal changed.

| 2005–2014, 120 months | Net annual mean | Net volatility | Net Sharpe | Net max drawdown |
| --- | ---: | ---: | ---: | ---: |
| Original TSMOM | 9.12% | 10.23% | 0.891 | -10.73% |
| Rescaled-only TSMOM control | 9.68% | 10.85% | 0.892 | -12.65% |
| Validation-selected negative-skew mix | 10.21% | 10.77% | 0.948 | -10.48% |
| Fixed 80/20 defensive-basket mix | 10.55% | 10.72% | 0.985 | -13.37% |

The selected blend improves net annual mean by 1.09 percentage points and
Sharpe by about 0.057 over original TSMOM. Its realized volatility is higher;
the rescaled-only control already raises mean return without improving Sharpe.
Thus the entire return difference cannot be attributed to new predictive alpha.
The basket's later-period performance is descriptive: it was not the validation
winner and must not replace the selected strategy based on this comparison.

The native baseline reproduces 1980–2014 annual mean 12.03%, volatility 10.20%
and Sharpe 1.179. Full-period curves include model-development dates; only the
right-hand chart isolates the later comparison window. Local inputs end in
December 2014, so the teammate's 2015–2025 extension cannot be reproduced here.

## Accounting limitations and checks

For exact comparability, native missing-return behavior is retained:
`economic_trend.py` fills missing held returns with zero and uses direct target
weight differences for turnover rather than drift-adjusted holdings. This is
a compatibility choice, not an endorsement of those missing values as true zero
returns. Missing held months are exported; there are two in the later period.
Excluding those two months for every displayed strategy yields baseline Sharpe
0.858 and selected-blend Sharpe 0.912, preserving the qualitative improvement.

Checks passed: baseline weights exactly reproduce the original helper;
perturbing future returns leaves all historical baseline, sleeve and blend
weights unchanged; weights are finite. Scaling only uses returns known at
formation, never future realized volatility. Native costs include rolls but
omit full spread/market-impact details. Risk targeting permits gross leverage
(about 4.18 baseline and 4.30 selected mix on average in the later period).

The full factor history and the 2005–2014 comparison period have previously
been inspected. These are research/development results, not a pristine holdout
or a statistical-significance claim. Actual execution, data revisions and
historical-universe selection remain separate limitations.

Artifacts under `outputs/tsmom_factor_overlay/`: selection configuration,
validation grid, net returns, summaries/subperiods, formation weights,
missing-return coverage/sensitivity and PNG/PDF log cumulative P&L charts.
