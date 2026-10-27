# Gross exposure cap ablation

Same 1976–2014 sample, original signals and one-month execution lag. Cap-only scales all baseline positions proportionally only when gross exposure exceeds 4x; otherwise positions are unchanged. It uses no risk forecast and never increases baseline exposure.

## Results at 10 bps per one-way target-weight change

| Strategy | CAGR | Annual volatility | Sharpe (RF=0) | Maximum drawdown | Annual turnover |
|---|---:|---:|---:|---:|---:|
| baseline | 9.85% | 11.12% | 0.903 | -26.10% | 7.24 |
| cap_only | 9.56% | 10.66% | 0.913 | -24.25% | 6.93 |
| diagonal | 11.25% | 11.77% | 0.968 | -24.25% | 7.85 |
| expanding_covariance | 9.15% | 9.74% | 0.951 | -17.44% | 8.26 |
| ewma_covariance | 9.34% | 9.79% | 0.965 | -14.24% | 8.96 |
| shrunk_covariance | 10.03% | 10.67% | 0.953 | -22.68% | 7.95 |

Cap-only reduces exposure in 33.1% of evaluation months.

At 10 bps costs, maximum drawdown is -26.10% for baseline, -24.25% for cap-only, and -14.24% for EWMA targeting. The cap improves drawdown by 1.84 percentage points; EWMA targeting improves it by a further 10.02 percentage points relative to cap-only. The gross cap alone therefore does not reproduce the full EWMA result in this historical sample.

Baseline vs cap-only isolates the 4x cap intervention. Cap-only vs full targeting measures the additional effect of forecast-based scaling and its multiplier limit under the same gross cap. Diagonal vs covariance targeting compares risk models under identical targeting rules; EWMA changes variances as well as correlations.

Differences are descriptive strategy comparisons, not an additive attribution of drawdown or proof of a causal covariance mechanism. Risk levels differ, parameters were not optimized here, and the historical sample is not an untouched holdout. Costs and missing-return assumptions match the main methodology.
