# Fair Comparisons, Ablations, and Return-Cost-Risk Optimization

Chinese version: [PORTFOLIO_OPTIMIZATION_REPORT.md](PORTFOLIO_OPTIMIZATION_REPORT.md)

## Collaborator contribution map

The selected portfolio combines strategy modules and shared portfolio infrastructure submitted by several collaborators. “Contributor” below refers to Git commit authorship for the code used by the current implementation; it does not assign ownership of the underlying academic ideas.

| Portfolio component | Role in the selected portfolio | Code contributor(s) | Main implementation |
| --- | --- | --- | --- |
| Continuous price-trend sleeve | 30% return sleeve | **Minxi-Lin** for the continuous signal; **Betty Lyu** for the underlying volatility/risk-weighting utilities | `combined_strategy.py`, `strategy_backtest_adj.py`, `economic_trend.py` |
| Economic-trend sleeve | 20% return sleeve using five macro themes | **Betty Lyu** | `economic_trend.py` |
| Negative-skew factor sleeve | 20% return sleeve using within-asset-class `NegativeSkew_12m` ranks | **xiayawen** | `futures_factor_backtest.py` |
| Extra Trees 66 sleeve | 30% ML return sleeve | **xiayawen** | `sign_return_prediction.py`, `fixed_2015_holdout.py`, `combined_factor_models.py` |
| EWMA covariance risk model | Shared risk normalization and portfolio constraints for all four sleeves | **JodieeT** | `covariance_risk_validation.py` |
| Combined-strategy framework | Original common pipeline for combining and testing team modules | **Minxi-Lin** | `combined_strategy.py` |
| Final fixed allocation, validation and cost-aware execution | Selects the fixed 30/20/20/30 Extra Trees 66 portfolio and implements the current execution comparison | **xiayawen** | `optimize_combined_portfolio.py`, `unified_portfolio.py` |

The four return sleeves are therefore not four entirely separate end-to-end submissions. They share JodieeT's covariance risk engine and the final integration and execution layer. The slow-fast/turning-point extension in Section 9 modifies only the trend sleeve and retains this common infrastructure.

Run: `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 optimize_combined_portfolio.py`.

Test: `python3 -m unittest test_unified_portfolio -v`.

After the selection has been saved, use `--reuse-frozen-selection` to rebuild diagnostics without selecting parameters again.

## 1. The optimization objective is implemented without claiming a globally optimal instrument portfolio

The implementation has two layers: constrained allocation across four signal strategies and cost-aware execution. Costs, leverage, and rebalancing rules are not treated as additional return-generating strategies. Multiple position-reduction rules are also not stacked. Taxes are set to zero. This experiment does not overwrite the legacy portfolio code or its default selected strategy.

The allocation-layer objective is:

`50% * calibration annual gross mean - c2/2 * average forecast variance`

`- c1 * annual net trading and roll cost - 0.01 * ||a - pure trend||^2`

Expected returns are estimated only from the calibration sample and shrunk by 50% to reduce mean-estimation noise. Risk uses the EWMA covariance matrix available at each month-end. Costs are calculated after offsetting trades across sleeves in the final portfolio.

The allocation coefficients must be nonnegative and sum to one. Trend must receive at least 30%, while every other sleeve is capped at 30%. Pure trend and the fixed 30/20/20/30 allocation are both feasible starting points. SLSQP searches from both and retains the better feasible result. All calibration optimizations report convergence, but this does not guarantee a global optimum. Higher estimated utility also does not guarantee a higher Sharpe ratio.

The search space consists of constrained combinations of four strategy portfolios. It does not freely optimize the weights of all 58 instruments. The binary baseline is evaluated as another feasible model-selection alternative, but it is not another direction within the continuous-trend four-strategy allocation space.

## 2. One common risk-control layer: identical constraints do not imply identical realized volatility

All fair comparisons use the same contemporaneous covariance estimate, tradability history, and portfolio limits:

- The covariance engine comes from JodieeT's `covariance_risk_validation.py`. The current portfolio uses a six-month half-life EWMA covariance matrix. Each instrument pair requires at least 36 overlapping monthly observations; otherwise, its correlation falls back to zero. The correlation matrix is repaired to be positive semidefinite. This matrix is not a fifth return strategy. It is shared risk infrastructure for the trend, macro, negative-skew, and ML sleeves.
- Each sleeve is first normalized to a common risk unit using the same covariance matrix. After the four sleeves are combined, the same matrix is used to impose portfolio volatility, gross-exposure, net-exposure, and asset-class risk limits. The final 30/20/20/30 allocation is therefore a signal-budget allocation, not a promise that realized risk contributions will equal those percentages.
- Forecast annual portfolio volatility is capped at 10%, gross exposure at 4x, and absolute net exposure at 1x.
- Standalone predicted volatility for each asset class is capped at 5%. EC Eurodollar is assigned to fixed income for risk grouping.
- One radial scaling factor is used to satisfy all limits simultaneously. The implementation does not sequentially trim long and short exposures and does not add the previous 2x scaling cap.

The fair binary baseline still uses the 12-month direction and 12-month instrument volatility. An EWMA instrument-volatility control and a continuous-signal version are also evaluated. All use a common 36-month estimation threshold and require 12 consecutive months of current observations. These controlled baselines are no longer equivalent to the unconstrained lecture baseline, so their performance should not be compared directly with the lecture's reported 0.31 Sharpe ratio.

## 3. Cost-aware execution does not treat cost savings as new alpha

Executed holdings first drift with realized returns and NAV. If the drifted portfolio violates a current limit, or an instrument is no longer eligible, the violation must be repaired immediately. Risk repair cannot be postponed to save transaction costs.

The execution layer then chooses a trading fraction `u` between the feasible prior portfolio and the feasible target to minimize:

`gamma/2 * monthly predicted tracking-error variance + 2 bps * actual net turnover + quarterly roll cost`

This corresponds to an alpha-risk-cost objective in which the execution proxy for alpha is `gamma * Sigma * target / 12`. It is a risk-tracking proxy for implementing the target signal, not evidence of a true expected-return estimate. The optimal trading fraction is solved exactly along this one-dimensional feasible segment. Convexity ensures that the resulting portfolio remains feasible. This is not a global optimization across arbitrary trades in 58 instruments.

The baseline, pure-trend, fixed-allocation, and optimized-allocation portfolios are each compared under full rebalancing, `gamma=5`, and `gamma=20`. This prevents the benefit of execution optimization from being attributed entirely to signal allocation.

Costs are 2 bps per unit of net turnover plus four annual futures rolls. Both purchase and sale trades incur costs. Offset trades across sleeves are not charged twice. NAV-drift accounting differs from the older unnormalized lecture convention. Sensitivities using the legacy Lecture 11 and Lecture 8 conventions are exported, and the qualitative conclusions remain unchanged.

## 4. Data split and frozen decisions

The four sleeves are continuous trend, macro, negative skew, and machine learning. The ML comparison is restricted to the existing Extra Trees 66- and 86-feature specifications. Their settings remain fixed: 200 trees, depth 6, minimum leaf size 30, `max_features=0.7`, seed 5260, and train-sample median imputation.

An initial pre-2005 model produces development forecasts. The classifier is fitted once again before 2015 and then frozen. There is no annual ML retraining.

- **2005-2009:** Calibrate allocation utility. Earlier ML results are not backfilled because there are no genuinely out-of-training-sample predictions before this period.
- **January 2010-November 2014:** Validate the model, utility parameters, and execution strength. Boundary labels are separated to prevent leakage.
- Allocation candidates use `c2 in {2, 8}` and `c1 in {1, 3}`. Execution candidates are full rebalance, `gamma=5`, and `gamma=20`.
- The 42 candidate rows include both feature sets, fixed allocation, pure trend, and binary baselines. The optimized allocation is not forced to win.
- For optimization diagnostics, the utility parameters selected on validation are recalibrated using January 2005-November 2014.
- The selected specification, parameters, and allocation are saved before the post-2014 evaluation returns are loaded. Nothing is reselected based on later performance.

Under these rules, validation selects **Extra Trees 66 + fixed 30/20/20/30 allocation + gamma=5 cost-aware execution**. Its validation Sharpe ratio is 1.3365, compared with 0.9257 for the same signal portfolio under full rebalancing. The fitted allocation does not win.

The best optimized candidate uses 86 features, `c2=2`, `c1=1`, and `gamma=5`. Its recalibrated diagnostic allocation is:

| Trend | Macro | Negative skew | ML |
| ---: | ---: | ---: | ---: |
| 65.18% | 16.96% | 8.40% | 9.46% |

This fitted allocation is not the formally selected strategy.

## 5. The in-sample question is clarified, but the training period is not enough

### Lecture slide baseline reference

The course baseline screenshots provide the following reference metrics. They report average annual return, not CAGR, and do not report maximum drawdown.

| Metric | In sample, approximately 1973-2014 | Out of sample, 2015-2025 |
| --- | ---: | ---: |
| Average annual return | 13.2% | 3.0% |
| Annual volatility (`Std Ret`) | 10.8% | 9.5% |
| Sharpe ratio | 1.22 | .31 |
| Annual turnover | 17.79 | 30.46 |
| Gross leverage | 4.62x | 7.94x |
| Average number of names | 41.4 | 56.3 |
| `Imbalance$`, as reported in the screenshots | 1.5 | 2.7 |

These values are external reference results from the supplied course images, not metrics recomputed by this repository. The slide baseline starts earlier than the four-sleeve IS sample, uses substantially more leverage and turnover, and may use different return frequency, continuous-contract construction, and cost accounting. The values are therefore useful for context but are not a controlled head-to-head test. The screenshots do not provide enough information to add slide-baseline CAGR or maximum drawdown without substituting results from a different implementation.

Descriptive 1976-2014 IS Sharpe ratios under the same new constraints and costs are:

| Strategy | IS Sharpe |
| --- | ---: |
| Fair constrained binary baseline | 1.055 |
| Continuous trend | 1.072 |
| Fixed four-sleeve allocation, 86 features and full rebalance | 1.122 |
| Optimized allocation, 86 features and full rebalance | 1.145 |
| Validation-selected fixed 66-feature allocation + cost-aware execution | .983 |

Allocation fitting can improve the fitted in-sample result, but the gain does not carry through proportionally to later periods. The validation-selected portfolio performs particularly well during 2010-2014 but does not raise the Sharpe ratio for the entire 1976-2014 period.

The utility objective does not directly maximize full-sample Sharpe. Constraints and costs also differ from the old unconstrained baseline, so not every controlled version should be expected to outperform that baseline in sample. Full-sample in-sample results contain dates used for fitting and selection and are not walk-forward evidence.

## 6. Later-period results: January 2015-May 2025 (125 months)

| Strategy | Reported annual return | Return definition | Sharpe | Maximum drawdown | Annual turnover |
| --- | ---: | --- | ---: | ---: | ---: |
| Course slide baseline, reference only | 3.00% | Average annual return from the supplied screenshot | .310 | Not reported | 30.46 |
| Fair binary 12-month baseline, full rebalance | -0.92% | Net CAGR | -.208 | -10.76% | 11.06 |
| Fair binary 12-month baseline, cost-aware `gamma=5` | approximately 0.00% | Net CAGR | .017 | -9.50% | 2.97 |
| Pure continuous trend, cost-aware `gamma=5` | 1.24% | Net CAGR | .338 | -7.04% | 2.86 |
| Fixed 66-feature four-sleeve, full rebalance | .53% | Net CAGR | .144 | -8.80% | 12.35 |
| **Validation-selected fixed 66-feature allocation + `gamma=5`** | **1.34%** | Net CAGR | **.356** | **-8.28%** | **3.09** |
| Optimized 86-feature allocation, full rebalance | .28% | Net CAGR | .090 | -7.65% | 9.70 |
| Optimized 86-feature allocation + `gamma=5`, diagnostic | 1.21% | Net CAGR | .356 | -6.42% | 2.50 |

The slide baseline row is included for context but is not a matched comparison. Its 3.00% figure is an average annual return, whereas the repository strategies report compounded net returns after the stated transaction costs. The screenshot also reports 9.5% volatility, 7.94x gross leverage, 56.3 names, and `Imbalance$` of 2.7, but no maximum drawdown.

The selected portfolio earns a 14.85% cumulative net return, a 1.41% annual arithmetic net return, and 3.96% realized volatility. Applying cost-aware execution to the same fixed 66-feature portfolio reduces annual cost from 0.42% to 0.19% and turnover by approximately 75%.

The difference in annual arithmetic net return is approximately 0.78 percentage points. Cost savings explain approximately 0.23 percentage points. The remainder comes from changes in the holdings path and trade timing, so the full return difference should not be described as a simple reduction in fees.

Pure continuous trend with the same execution already achieves a 0.338 Sharpe ratio, which indicates that the incremental benefit from more complex signals remains limited.

The fixed 86-feature portfolio with cost-aware execution reaches a later-period Sharpe ratio of 0.399, but it underperforms the 66-feature version during validation and therefore does not replace the selected specification.

These results also do not prove superiority over the lecture's 0.31 OOS Sharpe ratio. Frequency, sample end date, risk limits, and accounting conventions differ. In addition, the 2015-2025 period has been inspected repeatedly and is no longer a fresh independent test.

## 7. Conditional ablations show why not every module has persistent incremental value

The following comparison keeps the selected fixed 66-feature and `gamma=5` rules. Removing one sleeve returns its budget to trend without refitting:

| Strategy | Validation Sharpe, 2010-November 2014 | Later-period Sharpe, 2015-2025 |
| --- | ---: | ---: |
| Complete selected portfolio | 1.337 | .356 |
| Without macro | 1.334 | .329 |
| Without negative skew | .894 | .491 |
| Without ML | .874 | .133 |

Negative skew contributes strongly during validation but detracts in the later period. ML contributes conditionally in both periods. Macro provides a small incremental benefit.

These results cannot be addressed by automatically stacking every module. Nor should the later-period 0.491 Sharpe ratio be used to remove the negative-skew sleeve and claim a newly validated strategy.

The broader module ablation also covers EWMA instrument volatility, standalone macro, factor and ML sleeves, turning-point reduction, half-sized shorts, and exposure smoothing. The final three modify the target once and then enter the unified risk stage. They are not repeatedly stacked in the primary strategy.

## 8. Validation, risk interpretation, and limitations

Seven tests pass: simultaneous satisfaction of every limit and convex-combination feasibility; execution lag and first-trade cost; no duplicate cost after netting offsetting trades; superiority of the one-dimensional execution solution over a dense grid; invariance of execution to future changes; allocation boundaries and the feasible-starting-point utility lower bound; and invariance of fitted results to changes in future data outside the calibration period. The main runner also verifies that development-period base strategies are identical when built from complete and truncated datasets, and it checks the risk, gross, net, and asset-class limits of every output weight.

After consistently excluding the six months with missing returns on held positions, the selected portfolio's Sharpe ratio is .366, compared with .142 for full rebalancing and .046 for the cost-aware binary baseline. The primary native results retain the project convention of treating missing held returns as zero. The strict path compounds only the retained months and cannot reconstruct genuinely unknown P&L.

Under the legacy Lecture 11 cost convention, the selected portfolio has a 0.355 later-period Sharpe ratio. Under the Lecture 8 USD 1 billion cost model, it has a 0.360 Sharpe ratio. The result is therefore not driven by small differences in NAV-drift cost accounting.

The asset-class standalone volatility limits are not exact Euler equal-risk budgets. Limits are guaranteed only at monthly decision dates, not continuously within each month.

Remaining limitations include macro-data revisions, data and universe selection, continuous-futures construction, the feasibility of trading missing or discontinued contracts, incomplete impact costs, and statistical uncertainty. Static allocation is optimized only in a low-dimensional sleeve space. Cost-aware execution is exact only along a feasible one-dimensional path and is not a global solution in the full instrument space.

This experiment was proposed after later-period data had already been examined. Although calibration and selection strictly exclude labels after 2014, the research process is not a blind test of an untouched holdout. The higher observed Sharpe ratio should not be presented as evidence of robust alpha.

Outputs under `outputs/portfolio_optimization/` include the frozen selection, complete validation candidates, solver states, fair and module-level comparisons, conditional ablations, realized weights and net returns, two legacy-cost sensitivities, asset-class risk, the quarterly worst-S&P-decile smile, and figures. The quarterly diagnostic excludes incomplete 2025 Q2; the primary monthly performance includes data through May 2025.

## 9. Risk-reducing variant: Four-sleeve + slow-fast/turning point

### 9.1 Role in the project

This version is a **risk-reducing extension** of the selected four-sleeve portfolio. It is not a fifth alpha sleeve. The selected portfolio remains:

| Sleeve | Signal | Fixed budget |
| --- | --- | ---: |
| Trend | Continuous 12-month price trend | 30% |
| Macro | Directional signals from five economic themes | 20% |
| Factor | Within-asset-class cross-sectional `NegativeSkew_12m` | 20% |
| ML | Frozen 66-feature Extra Trees directional probability | 30% |

The slow-fast version replaces only the 30% trend sleeve. The macro, negative-skew, and Extra Trees sleeves remain unchanged. It also retains the common EWMA covariance model, portfolio limits, `gamma=5` cost-aware execution, and transaction-cost assumptions. This isolates the effect of state-dependent trend speed from changes to other portfolio components.

### 9.2 Mechanism

Each instrument has two month-end directional signals:

- **Slow signal:** Sign of the cumulative return over the previous 12 months.
- **Fast signal:** Sign of the cumulative return over the previous two months.

When they agree, the state is Bull or Bear, and the trend sleeve continues to follow the slow signal. When they disagree:

- Positive 12-month signal and negative two-month signal: **Correction**.
- Negative 12-month signal and positive two-month signal: **Rebound**.

During Correction and Rebound states, the direction becomes:

`dynamic direction = (1 - a) * slow direction + a * fast direction`

The mixing parameter `a` is estimated separately for every instrument and separately for Correction and Rebound observations. Only history through December 2004 is used, after which the parameters are frozen.

Each state requires at least 12 valid observations. Estimates are clipped to the interval from zero to one. If history is insufficient or the estimator is undefined, the model uses a predefined 0.5 fallback.

The method therefore retains the long-term trend while allowing the short-term direction to reduce or partially reverse risk during potential turning points. It differs from the earlier binary rule that automatically reduced exposure by 50% whenever the two- and 12-month directions disagreed. The slow-fast adjustment uses an instrument- and state-specific mixture and preserves information from both trend horizons.

After constructing the dynamic trend direction, the sleeve is normalized using JodieeT's six-month EWMA covariance model, just like the other three sleeves. The combined portfolio then passes through the same unified risk limits and `gamma=5` cost-aware execution. Formation weights earn returns in the following month, so future returns are not used.

### 9.3 Main results

The return columns below are annual arithmetic mean returns, not CAGR. IS covers 1976-2014. Before 2005, the dynamic version equals the selected four-sleeve portfolio. From 2005 onward, it uses slow-fast parameters frozen at the end of 2004. The OOS/later-period evaluation covers January 2015-May 2025.

| Strategy | IS annual return | IS volatility | IS Sharpe | IS maximum drawdown | OOS annual return | OOS volatility | OOS Sharpe | OOS maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Course slide baseline, reference only | **13.20%** | 10.80% | **1.220** | Not reported | **3.00%** | 9.50% | .310 | Not reported |
| Selected four-sleeve | 5.12% | 5.21% | .983 | -9.96% | **1.41%** | 3.96% | .356 | -8.28% |
| **Four-sleeve + slow-fast/turning point** | **5.16%** | **5.12%** | **1.007** | **-9.96%** | 1.31% | **3.36%** | **.391** | **-7.83%** |

The slide row reproduces the screenshots' average-return, volatility, and Sharpe figures. It is not directly comparable to the controlled four-sleeve rows because of the sample and implementation differences described in Section 5.

In the later period, the slow-fast version reduces volatility from 3.96% to 3.36%, improves maximum drawdown from -8.28% to -7.83%, and increases Sharpe from 0.356 to 0.391.

Average gross exposure falls from 1.61x to 1.33x, while annual cost falls from 0.191% to 0.182%. Annual turnover, however, increases from 3.09 to 3.78. Annual arithmetic return declines from 1.41% to 1.31%, and CAGR declines from 1.34% to 1.26%. Its primary benefit is therefore lower risk rather than higher absolute return.

Subperiod evidence is not fully stable. Sharpe increases from 0.512 to 0.695 during 2005-2009 but declines from 1.337 to 1.256 during the 2010-2014 validation period, even though maximum drawdown improves in both periods.

The annual incremental return relative to the selected four-sleeve portfolio is approximately -0.10 percentage points during 2015-2025, and its HAC 95% confidence interval contains zero. Parameter estimates are also noisy: many instrument-level Correction and Rebound weights reach the zero or one boundaries, and some states require the 0.5 fallback.

### 9.4 Conclusion and presentation

The slow-fast/turning-point version can be presented as a **risk-reducing variant** of the selected four-sleeve portfolio. It lowers volatility in the full IS and 2015-2025 later evaluation and improves Sharpe and maximum drawdown in the later period.

It does not improve later-period absolute returns, does not improve validation Sharpe, and has no statistically significant incremental return. The selected four-sleeve portfolio therefore remains the primary strategy. The slow-fast version is appropriate as an alternative for lower risk tolerance or as a robustness analysis, not as a proven source of additional alpha.

Implementation and outputs:

- `turning_point_model/dynamic_speed.py`: State classification, frozen parameters, and dynamic direction.
- `turning_point_model/tests/test_dynamic_speed.py`: State and no-future-information tests.
- `outputs/portfolio_optimization/dynamic_speed_parameters.csv`: Instrument- and state-level mixing parameters.
- `outputs/portfolio_optimization/dynamic_speed_comparison.csv`: Period-level performance and risk.
- `outputs/portfolio_optimization/dynamic_speed_incremental_hac.csv`: HAC inference for incremental returns.
- `outputs/portfolio_optimization/optimization_comparison.png`: 2015-2025 cumulative-performance and drawdown figure.
