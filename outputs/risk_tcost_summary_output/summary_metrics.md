# Summary metrics (net of Lecture 8 costs at $1bn, monthly execution convention)

T1 = band_25 no-trade band. Enhanced = EWMA instrument volatility + EWMA covariance targeting. R2 = equal (25%) ex-ante risk per asset class. See README for the execution-timing caveat (T3).

### IS 1976-2014

| Configuration | net_cagr | avg_annual_gross_return | avg_annual_net_return | annual_volatility | net_sharpe | gross_sharpe | max_drawdown | calmar | annual_turnover | annual_cost_drag | avg_gross_exposure | cumulative_net_return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 9.7% | 10.8% | 9.9% | 11.1% | 0.89 | 0.97 | -26.2% | 0.37 | 8.34 | 0.9% | 3.13 | 3573.3% |
| Enhanced | 9.6% | 10.5% | 9.6% | 9.4% | 1.02 | 1.11 | -14.2% | 0.67 | 9.64 | 0.9% | 3.13 | 3455.5% |
| R2 risk budget | 7.8% | 10.5% | 8.1% | 10.5% | 0.77 | 1.00 | -13.1% | 0.60 | 25.58 | 2.4% | 3.67 | 1786.7% |
| Baseline + T1 | 8.0% | 8.8% | 8.2% | 9.7% | 0.85 | 0.91 | -24.0% | 0.33 | 5.70 | 0.6% | 2.53 | 1937.2% |
| Enhanced + T1 | 8.6% | 9.2% | 8.6% | 8.3% | 1.03 | 1.10 | -12.8% | 0.67 | 6.07 | 0.6% | 2.63 | 2376.3% |
| R2 + T1 | 8.3% | 9.9% | 8.4% | 9.2% | 0.91 | 1.08 | -12.1% | 0.68 | 15.81 | 1.5% | 3.24 | 2107.4% |
| Static long | 5.7% | 6.8% | 6.6% | 14.5% | 0.45 | 0.47 | -67.8% | 0.08 | 1.66 | 0.2% | 3.20 | 754.9% |

### OOS 2015-2025

| Configuration | net_cagr | avg_annual_gross_return | avg_annual_net_return | annual_volatility | net_sharpe | gross_sharpe | max_drawdown | calmar | annual_turnover | annual_cost_drag | avg_gross_exposure | cumulative_net_return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | -1.6% | -0.3% | -1.0% | 11.1% | -0.09 | -0.02 | -33.1% | -0.05 | 13.32 | 0.8% | 4.35 | -15.8% |
| Enhanced | -0.3% | 0.5% | -0.1% | 7.1% | -0.01 | 0.07 | -15.0% | -0.02 | 12.81 | 0.6% | 3.86 | -3.4% |
| R2 risk budget | -0.7% | 1.0% | -0.5% | 5.3% | -0.10 | 0.19 | -15.5% | -0.04 | 33.86 | 1.6% | 4.00 | -6.6% |
| Baseline + T1 | -0.4% | 0.6% | 0.0% | 9.3% | 0.00 | 0.06 | -27.2% | -0.01 | 9.25 | 0.5% | 3.47 | -3.9% |
| Enhanced + T1 | 0.5% | 1.1% | 0.6% | 6.1% | 0.11 | 0.18 | -10.8% | 0.04 | 8.39 | 0.4% | 3.26 | 5.0% |
| R2 + T1 | -0.5% | 0.7% | -0.4% | 4.9% | -0.07 | 0.13 | -13.6% | -0.04 | 21.71 | 1.0% | 3.50 | -4.9% |
| Static long | 4.7% | 6.0% | 5.7% | 14.7% | 0.39 | 0.41 | -28.6% | 0.17 | 2.01 | 0.3% | 4.75 | 61.8% |

### Full 1976-2025

| Configuration | net_cagr | avg_annual_gross_return | avg_annual_net_return | annual_volatility | net_sharpe | gross_sharpe | max_drawdown | calmar | annual_turnover | annual_cost_drag | avg_gross_exposure | cumulative_net_return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 7.2% | 8.4% | 7.6% | 11.2% | 0.68 | 0.75 | -33.1% | 0.22 | 9.39 | 0.9% | 3.39 | 2993.7% |
| Enhanced | 7.4% | 8.4% | 7.6% | 9.1% | 0.84 | 0.93 | -15.0% | 0.50 | 10.31 | 0.8% | 3.28 | 3333.8% |
| R2 risk budget | 6.0% | 8.5% | 6.3% | 9.7% | 0.65 | 0.87 | -15.5% | 0.39 | 27.33 | 2.3% | 3.74 | 1662.0% |
| Baseline + T1 | 6.2% | 7.1% | 6.5% | 9.6% | 0.67 | 0.74 | -27.2% | 0.23 | 6.45 | 0.6% | 2.73 | 1858.4% |
| Enhanced + T1 | 6.8% | 7.5% | 6.9% | 8.0% | 0.87 | 0.94 | -12.8% | 0.53 | 6.55 | 0.6% | 2.76 | 2499.0% |
| R2 + T1 | 6.4% | 8.0% | 6.5% | 8.5% | 0.77 | 0.93 | -13.6% | 0.47 | 17.05 | 1.4% | 3.30 | 1999.3% |
| Static long | 5.5% | 6.6% | 6.4% | 14.5% | 0.44 | 0.46 | -67.8% | 0.08 | 1.73 | 0.2% | 3.53 | 1283.1% |
