# Train-only factor subset experiment

Run `MPLCONFIGDIR=/private/tmp/orie-mpl python3 select_factor_subset.py`.
The panel, chronological splits, boundary purging and raw next-month return
target match `tree_factor_prediction.py`. This is an additional development
experiment: the 2005–2014 period has already been inspected.

## Selection rule

Only selection-training labels (January 1976–November 1994) enter screening.
Each candidate's monthly within-class Spearman IC is averaged across at least
two valid classes, each containing at least four paired markets. Keep positive
mean IC and HAC(3) t >= 1. Order by training mean IC, then greedily accept at
most six features with absolute training rank correlation below 0.8 against
every already selected feature. Correlations pool date/class-centered percentile
ranks of available training observations; missing pairs are omitted and at least
500 paired observations are required. This is a screening heuristic, not proof
of statistical significance or independence. Per-factor IC months may differ.

Selected features:

1. NearWealthHigh_12m — proximity to a synthetic return-wealth high.
2. MedianReturn_12m — median return divided by volatility.
3. TSMOM — sign of summed 12-month returns.
4. TrendEfficiency_12m — signed path efficiency.
5. MildWorstReturn_12m — prefer smaller worst monthly losses.
6. ShallowDrawdown_12m — prefer shallower local wealth drawdowns.

Several remain trend-related. Positive-month share, mean/volatility, low
downside risk and XSMOM are removed as redundant with already selected signals.
No negative IC factor is retrospectively sign-flipped.

## Model comparison

All forests have depth 6, minimum leaf size 30, 200 trees, feature fraction 0.7
and seed 5260, with static asset-class indicators and train-only median
imputation. MomOnly uses XSMOM_12_1 as its sole price signal. Models train on
raw returns with MSE; only feature sets change. Parameters were carried over
from the prior experiment, not retuned here. The feature-set winner is chosen
by validation mean within-class Rank IC before inspecting comparison metrics.

| Tree model | Validation Rank IC, 1995–2004 | Comparison Rank IC, 2005–2014 | Comparison net Sharpe |
| --- | ---: | ---: | ---: |
| Mom-only tree | 0.0635 | 0.0159 | -0.33 |
| Six-feature tree | 0.0581 | 0.0097 | -0.20 |
| All-factor tree | 0.1007 | 0.0185 | -0.14 |

Validation selects **AllFactors**, so there is no basis here to replace the
existing all-factor model with the screened subset. The six-feature tree also
does not improve the later-period result. Both periods have 120 IC months;
portfolio Sharpe uses 116 common valid months with 10 bps per dollar traded,
class-neutral rank weights, unit gross exposure and drift-adjusted turnover.
It chains valid months rather than reconstructing missing calendar returns.
These are not equal-volatility portfolios.

Mom-only **tree** is different from trading the raw Mom score. The previous
raw XSMOM strategy had comparison Rank IC 0.0341 and net Sharpe 0.22. Thus a
tree can degrade even a single good signal through its learned nonlinear
mapping. Feature selection alone has not resolved this model/target issue.

Selection constraints were checked against saved training correlations and IC
statistics. Split purging and causal feature construction are inherited from
the checked panel helpers. All decisions, scores, correlations, validation
results, later-period predictions and trading results are saved under
`outputs/factor_selection/`. No new untouched holdout is claimed.
