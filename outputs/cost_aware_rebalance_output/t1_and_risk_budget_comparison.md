# T1 cost-aware rebalancing and with/without risk-budgeting comparison

All returns are net of the Lecture 8 cost model at $1bn AUM unless stated (commission, roll, spread, square-root impact, financing). IS = Jan 1976-Dec 2014, OOS = Jan 2015-May 2025. Rules are described in `cost_aware_rebalance.py`.

**Execution timing convention (main results).** Trades fill at the signal close while Lecture 8 impact assumes 5-day execution; `alpha_decay_execution.py` shows this overstates in-sample net Sharpe by about 0.07-0.09.

## In-sample rule comparison

Median change in IS net Sharpe across the six TSMOM strategies:

| Rule | Median IS net Sharpe change |
|---|---:|
| band_10 | +0.010 |
| band_25 | +0.004 |
| none | +0.000 |
| partial_50 | -0.089 |

**Adopted rule: `band_25`.** Its median IS net Sharpe effect is about zero (band_10 is similar); it is kept because it removes the most turnover without lowering IS net Sharpe. OOS numbers were not used to choose it.

## Findings

1. band_25 cuts IS turnover by roughly 30-40% for every strategy and IS cost drag by 0.3-0.9% a year. IS net Sharpe is roughly unchanged for the 1/N and enhanced variants and rises for R2, whose turnover is highest.
2. OOS net Sharpe rises for every TSMOM variant. Part of this exceeds the cost saving: slower trading also helped gross returns in the choppy 2015-2025 period, which is a regime effect that reversed IS.
3. partial_50 is the worst rule IS and the best OOS; choosing it after seeing OOS would be research look-ahead.
4. The band under-allocates: entries are made at 75% of target and exits in full, so average exposure, volatility and CAGR fall. Compare Sharpe, Sortino and Calmar rather than CAGR or cumulative return.

## Net Sharpe by rule

| Strategy | IS none | IS band_10 | IS band_25 | IS partial_50 | OOS none | OOS band_10 | OOS band_25 | OOS partial_50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.89 | 0.89 | 0.85 | 0.79 | -0.09 | -0.03 | 0.00 | 0.10 |
| class_count | 0.76 | 0.76 | 0.75 | 0.67 | -0.00 | 0.04 | 0.06 | 0.16 |
| ewma_vol | 1.03 | 1.02 | 0.98 | 0.91 | 0.03 | 0.09 | 0.14 | 0.22 |
| ewma_cov_target | 0.96 | 0.99 | 0.99 | 0.90 | -0.08 | -0.03 | 0.02 | 0.14 |
| enhanced | 1.02 | 1.04 | 1.03 | 0.91 | -0.01 | 0.03 | 0.11 | 0.21 |
| rb_class | 0.77 | 0.84 | 0.91 | 0.81 | -0.10 | -0.09 | -0.07 | 0.19 |

## IS annual turnover by rule

| Strategy | none | band_10 | band_25 | partial_50 |
|---|---:|---:|---:|---:|
| baseline | 8.3 | 6.9 | 5.7 | 5.6 |
| class_count | 10.9 | 9.0 | 7.4 | 7.4 |
| ewma_vol | 14.1 | 11.4 | 9.2 | 9.4 |
| ewma_cov_target | 9.4 | 7.3 | 5.7 | 5.8 |
| enhanced | 9.6 | 7.6 | 6.1 | 6.2 |
| rb_class | 25.6 | 21.0 | 15.8 | 13.2 |

## Group averages: without vs with risk budgeting

Simple average of the five non-risk-budget TSMOM variants vs R2.

### Monthly full rebalancing (`none`)

| Period | Group | cagr | annual_volatility | sharpe_0rf | sortino_0rf | max_drawdown | calmar | annual_turnover | annual_cost_drag | average_gross_exposure |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IS 1976-2014 | with risk budgeting (R2) | 7.8% | 10.5% | 0.77 | 1.40 | -13.1% | 0.60 | 25.58 | 2.4% | 3.67 |
| IS 1976-2014 | without risk budgeting (5) | 10.6% | 11.8% | 0.93 | 1.61 | -20.7% | 0.55 | 10.47 | 1.0% | 3.66 |
| OOS 2015-2025 | with risk budgeting (R2) | -0.7% | 5.3% | -0.10 | -0.13 | -15.5% | -0.04 | 33.86 | 1.6% | 4.00 |
| OOS 2015-2025 | without risk budgeting (5) | -0.9% | 10.5% | -0.03 | -0.04 | -25.9% | -0.03 | 17.01 | 0.9% | 5.53 |

### Adopted rule (`band_25`)

| Period | Group | cagr | annual_volatility | sharpe_0rf | sortino_0rf | max_drawdown | calmar | annual_turnover | annual_cost_drag | average_gross_exposure |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IS 1976-2014 | with risk budgeting (R2) | 8.3% | 9.2% | 0.91 | 1.72 | -12.1% | 0.68 | 15.81 | 1.5% | 3.24 |
| IS 1976-2014 | without risk budgeting (5) | 9.1% | 10.3% | 0.92 | 1.62 | -18.7% | 0.53 | 6.83 | 0.7% | 3.01 |
| OOS 2015-2025 | with risk budgeting (R2) | -0.5% | 4.9% | -0.07 | -0.10 | -13.6% | -0.04 | 21.71 | 1.0% | 3.50 |
| OOS 2015-2025 | without risk budgeting (5) | 0.2% | 8.9% | 0.07 | 0.10 | -21.2% | 0.01 | 11.34 | 0.6% | 4.58 |

## Full metrics, rule `none`, IS 1976-2014

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | 3573.3% | 6602.6% | 11556.8% | 3136.1% | 3455.5% | 1786.7% | 754.9% |
| cagr | 9.7% | 11.4% | 13.0% | 9.3% | 9.6% | 7.8% | 5.7% |
| annual_volatility | 11.1% | 16.0% | 12.7% | 9.8% | 9.4% | 10.5% | 14.5% |
| sharpe_0rf | 0.89 | 0.76 | 1.03 | 0.96 | 1.02 | 0.77 | 0.45 |
| sortino_0rf | 1.51 | 1.26 | 1.81 | 1.67 | 1.82 | 1.40 | 0.66 |
| max_drawdown | -26.2% | -29.1% | -19.0% | -14.9% | -14.2% | -13.1% | -67.8% |
| calmar | 0.37 | 0.39 | 0.68 | 0.63 | 0.67 | 0.60 | 0.08 |
| skewness | -0.07 | 0.12 | -0.03 | -0.11 | 0.01 | 0.57 | -0.58 |
| cvar_95_monthly | -6.3% | -9.3% | -6.9% | -5.5% | -5.1% | -5.8% | -9.5% |
| hit_rate | 63.2% | 61.8% | 64.3% | 63.0% | 64.5% | 59.6% | 59.6% |
| annual_turnover | 8.34 | 10.94 | 14.07 | 9.38 | 9.64 | 25.58 | 1.66 |
| annual_cost_drag | 0.9% | 0.9% | 1.3% | 0.9% | 0.9% | 2.4% | 0.2% |
| average_gross_exposure | 3.13 | 4.19 | 4.92 | 2.92 | 3.13 | 3.67 | 3.20 |
| corr_static | 0.08 | 0.06 | 0.07 | 0.11 | 0.08 | 0.10 | 1.00 |
| cum_return_at_10pct_vol_expost | 2507.5% | 1471.2% | 4330.1% | 3372.8% | 4247.8% | 1554.5% | 380.1% |

## Full metrics, rule `none`, OOS 2015-2025

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | -15.8% | -8.5% | -3.6% | -10.8% | -3.4% | -6.6% | 61.8% |
| cagr | -1.6% | -0.9% | -0.4% | -1.1% | -0.3% | -0.7% | 4.7% |
| annual_volatility | 11.1% | 12.8% | 12.5% | 8.8% | 7.1% | 5.3% | 14.7% |
| sharpe_0rf | -0.09 | -0.00 | 0.03 | -0.08 | -0.01 | -0.10 | 0.39 |
| sortino_0rf | -0.13 | -0.00 | 0.05 | -0.11 | -0.02 | -0.13 | 0.58 |
| max_drawdown | -33.1% | -28.1% | -28.4% | -25.0% | -15.0% | -15.5% | -28.6% |
| calmar | -0.05 | -0.03 | -0.01 | -0.04 | -0.02 | -0.04 | 0.17 |
| skewness | 0.02 | 0.28 | 0.13 | 0.11 | 0.17 | -0.60 | -0.39 |
| cvar_95_monthly | -7.1% | -7.8% | -7.3% | -5.2% | -4.8% | -3.9% | -9.4% |
| hit_rate | 47.2% | 47.2% | 45.6% | 47.2% | 45.6% | 45.6% | 52.8% |
| annual_turnover | 13.32 | 17.18 | 28.65 | 13.11 | 12.81 | 33.86 | 2.01 |
| annual_cost_drag | 0.8% | 0.8% | 1.3% | 0.7% | 0.6% | 1.6% | 0.3% |
| average_gross_exposure | 4.35 | 5.85 | 9.89 | 3.69 | 3.86 | 4.00 | 4.75 |
| corr_static | -0.30 | -0.40 | -0.21 | -0.27 | -0.29 | -0.10 | 1.00 |
| cum_return_at_10pct_vol_expost | -13.9% | -5.3% | -1.6% | -12.7% | -6.2% | -14.2% | 42.2% |

## Full metrics, rule `none`, Full 1976-2025

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | 2993.7% | 6031.3% | 11138.2% | 2786.7% | 3333.8% | 1662.0% | 1283.1% |
| cagr | 7.2% | 8.7% | 10.0% | 7.0% | 7.4% | 6.0% | 5.5% |
| annual_volatility | 11.2% | 15.4% | 12.8% | 9.7% | 9.1% | 9.7% | 14.5% |
| sharpe_0rf | 0.68 | 0.62 | 0.81 | 0.75 | 0.84 | 0.65 | 0.44 |
| sortino_0rf | 1.11 | 1.01 | 1.39 | 1.26 | 1.46 | 1.15 | 0.64 |
| max_drawdown | -33.1% | -29.1% | -28.4% | -25.0% | -15.0% | -15.5% | -67.8% |
| calmar | 0.22 | 0.30 | 0.35 | 0.28 | 0.50 | 0.39 | 0.08 |
| skewness | -0.05 | 0.18 | 0.01 | -0.04 | 0.10 | 0.66 | -0.54 |
| cvar_95_monthly | -6.6% | -9.1% | -7.1% | -5.5% | -5.1% | -5.6% | -9.6% |
| hit_rate | 59.9% | 58.7% | 60.4% | 59.7% | 60.5% | 56.7% | 58.2% |
| annual_turnover | 9.39 | 12.26 | 17.14 | 10.16 | 10.31 | 27.33 | 1.73 |
| annual_cost_drag | 0.9% | 0.9% | 1.3% | 0.9% | 0.8% | 2.3% | 0.2% |
| average_gross_exposure | 3.39 | 4.54 | 5.97 | 3.09 | 3.28 | 3.74 | 3.53 |
| corr_static | -0.00 | -0.02 | 0.01 | 0.03 | 0.02 | 0.07 | 1.00 |
| cum_return_at_10pct_vol_expost | 2117.4% | 1555.1% | 4235.7% | 3123.6% | 4745.0% | 1812.2% | 583.4% |

## Full metrics, rule `band_25`, IS 1976-2014

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | 1937.2% | 3451.1% | 5268.9% | 2471.7% | 2376.3% | 2107.4% | 754.9% |
| cagr | 8.0% | 9.6% | 10.8% | 8.7% | 8.6% | 8.3% | 5.7% |
| annual_volatility | 9.7% | 13.4% | 11.1% | 8.8% | 8.3% | 9.2% | 14.5% |
| sharpe_0rf | 0.85 | 0.75 | 0.98 | 0.99 | 1.03 | 0.91 | 0.45 |
| sortino_0rf | 1.44 | 1.24 | 1.73 | 1.79 | 1.89 | 1.72 | 0.66 |
| max_drawdown | -24.0% | -26.5% | -17.4% | -12.6% | -12.8% | -12.1% | -67.8% |
| calmar | 0.33 | 0.36 | 0.62 | 0.69 | 0.67 | 0.68 | 0.08 |
| skewness | -0.03 | 0.03 | 0.11 | 0.12 | 0.18 | 0.47 | -0.58 |
| cvar_95_monthly | -5.6% | -7.9% | -5.9% | -4.7% | -4.4% | -4.9% | -9.5% |
| hit_rate | 63.0% | 61.5% | 62.8% | 63.0% | 63.9% | 61.3% | 59.6% |
| annual_turnover | 5.70 | 7.40 | 9.23 | 5.74 | 6.07 | 15.81 | 1.66 |
| annual_cost_drag | 0.6% | 0.7% | 0.9% | 0.6% | 0.6% | 1.5% | 0.2% |
| average_gross_exposure | 2.53 | 3.41 | 4.02 | 2.47 | 2.63 | 3.24 | 3.20 |
| corr_static | 0.16 | 0.11 | 0.14 | 0.18 | 0.15 | 0.09 | 1.00 |
| cum_return_at_10pct_vol_expost | 2144.7% | 1441.7% | 3577.8% | 3823.0% | 4469.2% | 2764.5% | 380.1% |

## Full metrics, rule `band_25`, OOS 2015-2025

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | -3.9% | 0.9% | 10.5% | -1.1% | 5.0% | -4.9% | 61.8% |
| cagr | -0.4% | 0.1% | 1.0% | -0.1% | 0.5% | -0.5% | 4.7% |
| annual_volatility | 9.3% | 10.4% | 11.0% | 7.6% | 6.1% | 4.9% | 14.7% |
| sharpe_0rf | 0.00 | 0.06 | 0.14 | 0.02 | 0.11 | -0.07 | 0.39 |
| sortino_0rf | 0.01 | 0.09 | 0.22 | 0.04 | 0.16 | -0.10 | 0.58 |
| max_drawdown | -27.2% | -22.9% | -24.6% | -20.7% | -10.8% | -13.6% | -28.6% |
| calmar | -0.01 | 0.00 | 0.04 | -0.01 | 0.04 | -0.04 | 0.17 |
| skewness | 0.12 | 0.31 | 0.27 | 0.16 | 0.42 | -0.25 | -0.39 |
| cvar_95_monthly | -5.6% | -6.2% | -6.2% | -4.4% | -3.9% | -3.3% | -9.4% |
| hit_rate | 46.4% | 48.0% | 48.0% | 47.2% | 48.0% | 44.0% | 52.8% |
| annual_turnover | 9.25 | 11.85 | 18.77 | 8.41 | 8.39 | 21.71 | 2.01 |
| annual_cost_drag | 0.5% | 0.6% | 1.0% | 0.5% | 0.4% | 1.0% | 0.3% |
| average_gross_exposure | 3.47 | 4.62 | 8.56 | 3.00 | 3.26 | 3.50 | 4.75 |
| corr_static | -0.25 | -0.36 | -0.22 | -0.23 | -0.28 | -0.21 | 1.00 |
| cum_return_at_10pct_vol_expost | -4.5% | 1.1% | 10.1% | -2.6% | 6.1% | -12.2% | 42.2% |

## Full metrics, rule `band_25`, Full 1976-2025

| Metric | baseline | class_count | ewma_vol | ewma_cov_target | enhanced | rb_class | static_bmk |
|---|---:|---:|---:|---:|---:|---:|---:|
| cumulative_return | 1858.4% | 3484.4% | 5833.1% | 2443.7% | 2499.0% | 1999.3% | 1283.1% |
| cagr | 6.2% | 7.5% | 8.6% | 6.8% | 6.8% | 6.4% | 5.5% |
| annual_volatility | 9.6% | 12.9% | 11.1% | 8.6% | 8.0% | 8.5% | 14.5% |
| sharpe_0rf | 0.67 | 0.63 | 0.80 | 0.81 | 0.87 | 0.77 | 0.44 |
| sortino_0rf | 1.11 | 1.02 | 1.38 | 1.40 | 1.56 | 1.41 | 0.64 |
| max_drawdown | -27.2% | -26.5% | -24.6% | -20.7% | -12.8% | -13.6% | -67.8% |
| calmar | 0.23 | 0.28 | 0.35 | 0.33 | 0.53 | 0.47 | 0.08 |
| skewness | 0.01 | 0.11 | 0.14 | 0.16 | 0.28 | 0.57 | -0.54 |
| cvar_95_monthly | -5.7% | -7.6% | -6.0% | -4.7% | -4.4% | -4.7% | -9.6% |
| hit_rate | 59.5% | 58.7% | 59.7% | 59.7% | 60.5% | 57.7% | 58.2% |
| annual_turnover | 6.45 | 8.34 | 11.24 | 6.30 | 6.55 | 17.05 | 1.73 |
| annual_cost_drag | 0.6% | 0.6% | 0.9% | 0.6% | 0.6% | 1.4% | 0.2% |
| average_gross_exposure | 2.73 | 3.67 | 4.97 | 2.58 | 2.76 | 3.30 | 3.53 |
| corr_static | 0.08 | 0.03 | 0.07 | 0.10 | 0.08 | 0.05 | 1.00 |
| cum_return_at_10pct_vol_expost | 2080.0% | 1639.3% | 3920.4% | 4037.8% | 5598.2% | 3343.5% | 583.4% |

`cum_return_at_10pct_vol_expost` rescales each strategy to 10% realised volatility over the period itself. It uses ex-post information, is descriptive only, and is shown because the risk-budget strategy runs near 5% volatility when the 4x gross cap binds. Sharpe, Sortino and Calmar are unaffected by that scale difference.
