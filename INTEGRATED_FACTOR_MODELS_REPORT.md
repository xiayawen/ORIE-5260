# Integrating our factors and Extra Trees into the team pipeline

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 integrate_team_factor_models.py`.
Tests: `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 -m unittest test_combined_factor_models -v`.

## What is now integrated

`combined_strategy.Pipeline` now accepts two optional ML components:

| Component key | Model / features |
| --- | --- |
| `extratrees_overlay` | Frozen Extra Trees; original31 signals +31 class-relative ranks +4 class indicators (66) |
| `extratrees_crossasset_overlay` | Same Extra Trees; above plus10 cross-asset raw signals and10 class-relative ranks (86) |

All 31 original signals are used as model inputs, including TSMOM, relative and
residual momentum, reversal, seasonality, volatility/distribution, peer beta
and correlation signals. The extra10 are equity/bond/dollar exposure,
downside equity sensitivity, equity coskewness and equity/bond/dollar/commodity
lag-response signals from `cross_asset_factor_research.py`. No factor names,
signs, horizons or thresholds are changed for integration.

The existing negative-skew factor sleeve is retained separately when the all-team
configuration requests it. This duplicates some information already in ML
inputs, but does not double-count realized P&L: final instrument holdings are
netted before actual trading costs are charged. Original HistGB remains an
alternative/control. A single ML slot has a30% budget; the pipeline rejects
stacking HistGB, ExtraTrees66 and ExtraTrees86 together.

`combined_factor_models.py` computes probabilities and caches them for both
versions, rather than loading previous result CSVs or substituting a standalone
strategy's realized P&L. This makes risk sizing and costs genuinely integrated.
The new components are deliberately outside the old `COMPONENTS`/`CLEAN_POOL`
default search pools, so this change does not silently alter historical stepwise
selection or replace the team's selected final strategy. Labels/logging support
the optional names; they can be explicitly passed to `Pipeline.run`.

Example complete continuous-core configuration:

```python
config = {
    "continuous_signal", "economic_trend", "factor_overlay",
    "extratrees_crossasset_overlay", "turning_point", "half_short",
    "net_cap", "smooth_leverage_imbalance", "band_25",
}
result = pipe.run(config)
```

For class risk budgeting, replace `continuous_signal` with `risk_budget`; these
two cores remain mutually exclusive. Weekly/daily rebalancing remains outside
this monthly integration because post-2014 daily input is missing.

## Model fitting and sizing

Extra Trees uses the same 200 trees, depth6, leaf30, max_features.7, seed5260
and training-only median imputation as our fixed-holdout studies. An initial
pre-2005 fit supplies genuinely out-of-training development forecasts. Refit
once before 2015 on all available nonzero observed labels strictly preceding
December2014 formation (through November2014), then freeze through2025.
No annual Extra Trees retraining or OOS feature/threshold selection occurs.
HistGB retains the existing branch's annual15-year rolling scheme as a control;
the algorithms and training schedules therefore differ intentionally.

The input panel is the current combined branch's full Excel data, not cached
forecasts from the old standalone scripts. Earlier standalone studies preserved
original CSV history; full Excel includes small rounding/missingness differences.
Consequently integrated results should be compared to the controls recomputed
here, not assumed to equal earlier standalone results.

Probabilities become directional scores `2*p(up)-1`, then reuse the branch's
EWMA instrument volatility, live-market mask, covariance-based sleeve scaling,
blend retargeting, caps and execution. The previous standalone trailing-realized
portfolio scaling is not applied a second time. Latest-month inference pads a
blank future row; unknown future returns never become training labels or P&L.
Thus the last May2025 formation forecast may appear in the audit as a June2025
return forecast, while evaluated performance ends at May2025.

When all sleeves are active, budgets before risk retargeting are30% core,
20% macro,20% negative skewness,30% selected ML. An inactive ML sleeve returns
its budget to the core. HistGB begins earlier; Extra Trees is inactive before
2005. Full-history IS metrics are therefore descriptive and not an equal-model-
availability contest. All displayed later-period variants have active models.

## Results: January2015–May2025,125 months

Lecture11 trading/roll costs and the same instrument return panel:

| Context | ML slot | Net CAGR | Net Sharpe | Max drawdown |
| --- | --- | ---: | ---: | ---: |
| Continuous core only | HistGB15y | 1.87% | .308 | -8.28% |
| Continuous core only | Extra Trees66 | 1.22% | .214 | -9.44% |
| Continuous core only | Extra Trees86 | 1.47% | .252 | -9.44% |
| All team modules, continuous core | HistGB15y | .74% | .217 | -6.61% |
| All team modules, continuous core | Extra Trees66 | .69% | .196 | -7.31% |
| All team modules, continuous core | Extra Trees86 | .71% | .204 | -7.76% |
| All team modules, risk-budget core | HistGB15y | .34% | .114 | -8.18% |
| All team modules, risk-budget core | Extra Trees66 | .19% | .069 | -8.09% |
| All team modules, risk-budget core | Extra Trees86 | .32% | .106 | -7.81% |

The no-ML selected-final reference is CAGR.65%, Sharpe.124 and drawdown-11.93%.
Our integrated classifiers improve on that reference in the continuous-core
context, but do not beat the original HistGB control. Added cross-asset features
help Extra Trees modestly. Once all controls are applied, return differences
become small; full continuous-core volatility is3.73–3.86%, average gross1.65–1.68,
versus core-only model variants around6.7% vol and3.76–3.78gross. The modules
are not equal-volatility allocations and these numbers do not establish alpha.

No later-period winner is selected or tuned here. The2015–2025 period has been
repeatedly inspected, and several team controls were developed after viewing
it. These are integration ablations, not a new pristine OOS test. Native missing
return handling, cost proxies, universe/contract construction, macro revisions,
leverage and the fixed order of risk controls remain inherited limitations.

## Verification and artifacts

Four dedicated tests passed: optional models do not change original selection
pools; alternative ML sleeves cannot be stacked; inactive models are an exact
no-op even if retargeting would otherwise alter the core; extending data from
2014 to2025 leaves every old probability and training sample unchanged,
including the terminal December2014 inference row. Probability bounds, feature
counts, label-date boundaries and latest-month inference are checked.

All three legacy controls exactly reproduce earlier IS/OOS CAGR, net annual
return, Sharpe, drawdown and gross exposure under both cost conventions.
All executed weights are finite and obey the4x gross cap.

`outputs/integrated_factor_models/` contains10 variant configurations, training
audits,66/86 probability panels, coverage, executed holdings, both-cost summaries,
subperiods, stage exposures, net returns and a cumulative P&L/drawdown chart.
