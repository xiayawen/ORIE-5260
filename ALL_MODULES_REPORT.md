# Combining every compatible team module

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 all_modules_comparison.py`.
This is an integration comparison on the `combined-strategy` branch, not a new
strategy selection or parameter search. All component settings and native
Lecture 11 / Lecture 8 cost implementations reuse `combined_strategy.Pipeline`.

## How the existing work connects

| Function | Module / original work | Position in combined pipeline |
| --- | --- | --- |
| Price trend | Binary or continuous signal in `combined_strategy.py` | Core direction |
| Volatility/covariance | EWMA instrument vol and `portfolio_volatility_targeting.py` | Core sizing, covariance target, scale/gross limits |
| Risk allocation | `risk_budgeting.py` | Alternative core: equal ex-ante class risk budgets |
| Macro signal | `economic_trend.py` | 20% economic-trend sleeve |
| Price-distribution factor | `tsmom_factor_overlay.py` | 20% negative-skewness sleeve |
| Machine learning | `rolling_sign_prediction.py` | 30% HistGB sign-probability sleeve; 15-year annual refits |
| Turning point | `turning_point_model/` | Halve positions when short/long trends disagree and macro opposition confirms |
| Short allocation | `short_budget_backtest.py` | Half-size short positions |
| Net exposure | `net_exposure_backtest.py` | Net exposure cap |
| Exposure stability | `exposure_smoothing_backtest.py` | Either gross-only or gross/net smoothing |
| Trading restraint | `cost_aware_rebalance.py` | 25% no-trade band, drift-aware execution |
| Cost accounting | `transaction_cost_model.py` and Lecture 11 implementation | Charged on final executed holdings/trades, not summed sleeve P&L |

Risk decomposition, attribution and execution-timing diagnostics help assess
the strategy but are not additional return sleeves. Post-2014 daily prices
are unavailable, so weekly/daily rebalancing and daily execution-horizon rules
cannot be faithfully switched on in this monthly test.

Two pairs are mutually exclusive in the current implementation: risk-budget
core versus continuous-signal core; gross-only versus gross/net smoothing.
Therefore "everything" is represented by **four complete variants**, rather
than silently running incompatible sizing rules in an arbitrary order.
Each includes macro, factor, ML, turning-point reduction, half-short, net cap,
one smoothing alternative and the no-trade band. Covariance targeting and
4x gross cap remain active. The two cores and two smoothers form the four rows.

Pipeline order:

`core -> blend sleeves -> covariance retarget -> turning reduction -> half-short
-> net cap -> smoothing -> gross cap -> no-trade-band execution -> costs`

When all sleeves are active, pre-target sleeve budgets are 30% trend core,
20% macro, 20% negative skewness and 30% ML. If a sleeve has no positions,
its budget returns to the core, as in the existing pipeline. Final holdings
are not simply a sum of standalone strategy returns.

## Results: January 2015–May 2025

Net of Lecture 11 2 bps trading + four annual rolls; all 125 months:

| Combination | Net CAGR | Net annual mean | Realized vol | Net Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Existing selected final | 0.65% | 0.93% | 7.46% | .124 | -11.93% |
| All earlier compatible candidates, continuous core | 0.83% | 0.92% | 4.31% | .213 | -8.74% |
| Complete: continuous core + gross smoothing | 0.50% | 0.56% | 3.64% | .155 | -7.02% |
| Complete: continuous core + gross/net smoothing | 0.74% | 0.81% | 3.73% | .217 | -6.61% |
| Complete: risk-budget core + gross smoothing | 0.10% | 0.16% | 3.56% | .045 | -8.40% |
| Complete: risk-budget core + gross/net smoothing | 0.34% | 0.40% | 3.53% | .114 | -8.18% |

The complete continuous/gross-net variant has a higher later-period Sharpe
than existing final, but essentially no meaningful increase in absolute
return. In-sample Sharpe is .933 versus selected final 1.128. The full risk
stack shrinks the book: average gross exposure for the continuous/gross-net
variant is 3.77 after the sleeve mix, 1.91 after risk controls and 1.68 after
band execution. The selected final averages 3.69 executed gross. Thus lower
drawdowns partly reflect substantially lower risk deployment, not proven
independent alpha from every module.

Risk targeting occurs before turning/short/net/smoothing controls and the
trading band. There is deliberately no new final volatility re-targeting after
these controls; adding one would partially undo them and could breach limits.
An equal-risk comparison would require a separately specified leverage/cap
policy, not multiplying observed returns by a full-period realized-vol ratio.

The Lecture 8 $1bn cost sensitivity preserves the qualitative result: complete
continuous/gross-net Sharpe .219 versus selected final .126; complete risk-budget
variants .032–.100. These include historical/default daily-liquidity assumptions
and are not new post-2014 daily execution evidence.

## Checks and interpretation

All six configurations respect mutual-exclusion constraints, and all shared
modules are enabled in each complete variant. Executed weights are finite and
respect the 4x gross cap. The selected-final control exactly reproduces the
committed reference's IS/OOS CAGR, annual net return, Sharpe and drawdown.
The earlier-compatible row reproduces its stored OOS figures; its recomputed
IS figures differ slightly from the earlier artifact (CAGR 6.79% vs 6.83%),
so this report uses the current input/code run rather than mixing artifacts.

These are descriptive integration results. Half-short and smoothing rules
were designed after viewing 2015–2025. Other components and the later sample
have also been repeatedly examined. No row here is a new pristine OOS test,
and the best-looking later row is not selected as a new production strategy.
Macro revisions/availability, missing returns, historical-universe selection,
costs and the fixed pipeline order remain inherited limitations.

Outputs: `outputs/all_modules_comparison/` contains exact configurations,
component sets, IS/OOS metrics under both cost conventions, stage-by-stage
exposure, final executed holdings, monthly net returns and a log-P&L chart.
