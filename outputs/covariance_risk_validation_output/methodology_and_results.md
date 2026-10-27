# Covariance risk validation

Unchanged adjusted-baseline weights; formation-month information only.

All models use identical evaluation dates within each horizon. Historical estimates are expanding; EWMA has a fixed six-month half-life. Shrinkage is fixed at 50% toward the historical diagonal, not fitted to these results.

Pairwise estimates use available observations, require 36 overlapping months for correlations, and assume zero correlation otherwise. Correlation matrices are projected to PSD and renormalized to preserve marginal variances. Repair diagnostics are exported. EWMA changes both variances and correlations, so its comparison does not isolate correlation alone.

Future fixed-weight realized returns fill missing observations with zero, matching existing validation. Forecast windows overlap; statistics are descriptive, not independent observations or an out-of-sample model-selection exercise. Last formation dates without a complete future horizon are excluded. No portfolio targeting or leverage changes are introduced.

| Horizon | Model | Predicted vol | Realized vol | MAE | RMSE | Exceedance |
|---|---|---:|---:|---:|---:|---:|
| 3 | diagonal | 6.79% | 8.87% | 4.53% | 6.61% | 54.6% |
| 3 | ewma_covariance | 10.60% | 8.87% | 4.67% | 6.18% | 32.3% |
| 3 | expanding_covariance | 10.66% | 8.87% | 4.74% | 6.02% | 28.2% |
| 3 | shrunk_covariance | 8.99% | 8.87% | 4.30% | 5.85% | 40.4% |
| 12 | diagonal | 6.82% | 9.78% | 3.64% | 5.38% | 74.8% |
| 12 | ewma_covariance | 10.68% | 9.78% | 2.81% | 3.86% | 33.1% |
| 12 | expanding_covariance | 10.70% | 9.78% | 3.01% | 3.75% | 28.7% |
| 12 | shrunk_covariance | 9.03% | 9.78% | 2.72% | 3.90% | 45.6% |
