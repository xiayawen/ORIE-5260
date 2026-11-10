# Enhanced strategy: EWMA risk model + Lecture 8 transaction costs

Evaluation January 1976–December 2014; identical dates for every strategy. Same 12-month sign signal; formation-date information only; one-month execution lag.

## Strategies

- `baseline`: expanding-vol sizing (40%/σ, 1/N), no portfolio target.
- `ewma_vol`: EWMA instrument volatility (6-month half-life, 36-month entry rule).
- `ewma_cov_target`: baseline weights scaled so EWMA-covariance forecast vol = 10% (4x gross cap, 2x scale cap).
- `enhanced`: EWMA vol sizing, then EWMA-covariance targeting with the same limits.
- `static_bmk`: always-long course static benchmark (reference only).

## Cost model (fixed in advance, not fitted)

- Explicit — commission/fees 1.0 bp per unit notional traded; futures roll 1.0 bp of held notional per roll, rolls/year by contract cycle (energy 12, grains/livestock 5-8, financials 4; class fallback {'EQ': 4, 'FI': 4, 'FX': 4, 'COMM': 6}); margin rates {'EQ': 0.06, 'FI': 0.03, 'FX': 0.04, 'COMM': 0.08}, financing at 50.0 bps/yr only on margin above 100% of equity; no borrow fee for futures shorts.
- Implicit — half-spread {'EQ': 1.0, 'FI': 0.5, 'FX': 1.0, 'COMM': 2.5} bps per unit traded; square-root impact MI = 0.5 × σ_daily × √(trade USD / (ADV USD × 5 execution days)). ADV by class {'EQ': 5000000000.0, 'FI': 10000000000.0, 'FX': 5000000000.0, 'COMM': 1000000000.0} (USD/day), cut to 10% when trailing 252-day median contract volume < 2,000. σ is the formation-date EWMA instrument vol for all strategies.
- Turnover: drift-adjusted, i.e. trades from last month's weights after they drifted with last month's returns. The same turnover is used by every cost case and in the Turnover/yr column; the target-weight change used elsewhere in the repo is shown alongside for reference.
- Flat cases (`flat_Nbps`, slide 32's simple rule): N bps per unit of turnover plus the same futures roll cost; 2 bps is the lecture's figure. They do not depend on AUM.
- Classification: slide 32 lists futures roll under implicit costs; it is reported here as explicit because each roll is a commission-bearing trade. Totals are unaffected.

## Results

| Strategy | Costs | CAGR | Vol | Sharpe | Max DD | Turnover/yr (drift) | Turnover/yr (target) |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | gross | 10.64% | 11.15% | 0.966 | -26.03% | 8.34 | 7.24 |
| baseline | flat_2bps | 10.30% | 11.14% | 0.939 | -26.14% | 8.34 | 7.24 |
| baseline | flat_10bps | 9.57% | 11.12% | 0.880 | -26.32% | 8.34 | 7.24 |
| baseline | lecture8_$1bn | 9.68% | 11.13% | 0.889 | -26.23% | 8.34 | 7.24 |
| ewma_vol | gross | 14.38% | 12.76% | 1.122 | -18.88% | 14.07 | 13.23 |
| ewma_vol | flat_2bps | 13.82% | 12.75% | 1.084 | -18.97% | 14.07 | 13.23 |
| ewma_vol | flat_10bps | 12.56% | 12.73% | 0.997 | -19.11% | 14.07 | 13.23 |
| ewma_vol | lecture8_$1bn | 12.98% | 12.74% | 1.026 | -19.04% | 14.07 | 13.23 |
| ewma_cov_target | gross | 10.32% | 9.81% | 1.054 | -13.64% | 9.38 | 8.96 |
| ewma_cov_target | flat_2bps | 9.97% | 9.80% | 1.022 | -13.81% | 9.38 | 8.96 |
| ewma_cov_target | flat_10bps | 9.15% | 9.79% | 0.947 | -14.42% | 9.38 | 8.96 |
| ewma_cov_target | lecture8_$1bn | 9.32% | 9.79% | 0.963 | -14.91% | 9.38 | 8.96 |
| enhanced | gross | 10.57% | 9.46% | 1.114 | -13.68% | 9.64 | 9.42 |
| enhanced | flat_2bps | 10.20% | 9.45% | 1.079 | -13.84% | 9.64 | 9.42 |
| enhanced | flat_10bps | 9.37% | 9.43% | 0.999 | -14.20% | 9.64 | 9.42 |
| enhanced | lecture8_$1bn | 9.59% | 9.44% | 1.021 | -14.24% | 9.64 | 9.42 |
| static_bmk | gross | 5.91% | 14.52% | 0.470 | -67.54% | 1.66 | 0.41 |
| static_bmk | flat_2bps | 5.72% | 14.52% | 0.457 | -67.74% | 1.66 | 0.41 |
| static_bmk | flat_10bps | 5.58% | 14.52% | 0.448 | -67.90% | 1.66 | 0.41 |
| static_bmk | lecture8_$1bn | 5.66% | 14.52% | 0.453 | -67.85% | 1.66 | 0.41 |

## Annual cost by component (bps/yr)

| Strategy | AUM | Commission | Roll | Financing | Half-spread | Impact | Total | Avg margin/equity |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | $100m | 8.3 | 14.4 | 0.0 | 11.4 | 17.0 | 51.2 | 15.3% |
| baseline | $1bn | 8.3 | 14.4 | 0.0 | 11.4 | 53.8 | 87.9 | 15.3% |
| baseline | $10bn | 8.3 | 14.4 | 0.0 | 11.4 | 170.1 | 204.3 | 15.3% |
| ewma_vol | $100m | 14.1 | 22.1 | 0.0 | 17.7 | 22.6 | 76.4 | 22.9% |
| ewma_vol | $1bn | 14.1 | 22.1 | 0.0 | 17.7 | 71.5 | 125.3 | 22.9% |
| ewma_vol | $10bn | 14.1 | 22.1 | 0.0 | 17.7 | 226.2 | 280.0 | 22.9% |
| ewma_cov_target | $100m | 9.4 | 13.5 | 0.0 | 13.0 | 17.6 | 53.4 | 14.4% |
| ewma_cov_target | $1bn | 9.4 | 13.5 | 0.0 | 13.0 | 55.7 | 91.5 | 14.4% |
| ewma_cov_target | $10bn | 9.4 | 13.5 | 0.0 | 13.0 | 176.0 | 211.8 | 14.4% |
| enhanced | $100m | 9.6 | 14.3 | 0.0 | 13.5 | 16.7 | 54.1 | 15.3% |
| enhanced | $1bn | 9.6 | 14.3 | 0.0 | 13.5 | 52.7 | 90.2 | 15.3% |
| enhanced | $10bn | 9.6 | 14.3 | 0.0 | 13.5 | 166.7 | 204.2 | 15.3% |
| static_bmk | $100m | 1.7 | 14.6 | 0.0 | 2.3 | 1.7 | 20.3 | 15.5% |
| static_bmk | $1bn | 1.7 | 14.6 | 0.0 | 2.3 | 5.3 | 23.9 | 15.5% |
| static_bmk | $10bn | 1.7 | 14.6 | 0.0 | 2.3 | 16.8 | 35.4 | 15.5% |

## Capacity (net Sharpe by AUM)

| Strategy | $10m | $100m | $300m | $1bn | $3bn | $10bn | $30bn | $100bn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.931 | 0.921 | 0.910 | 0.889 | 0.854 | 0.785 | 0.672 | 0.450 |
| ewma_vol | 1.075 | 1.063 | 1.051 | 1.026 | 0.985 | 0.904 | 0.773 | 0.514 |
| ewma_cov_target | 1.013 | 1.001 | 0.988 | 0.963 | 0.922 | 0.841 | 0.708 | 0.445 |
| enhanced | 1.070 | 1.058 | 1.045 | 1.021 | 0.981 | 0.901 | 0.771 | 0.513 |
| static_bmk | 0.456 | 0.456 | 0.455 | 0.453 | 0.451 | 0.445 | 0.437 | 0.420 |

## Execution-horizon sensitivity ($1bn)

Impact scales with 1/√(execution days); trading the whole rebalance in one day is the upper bound.

| Strategy | Days | Net Sharpe | Impact bps/yr | Total bps/yr | Median max participation |
|---|---:|---:|---:|---:|---:|
| baseline | 1 | 0.830 | 120.3 | 154.5 | 23.1% |
| baseline | 5 | 0.889 | 53.8 | 87.9 | 4.6% |
| baseline | 21 | 0.913 | 26.3 | 60.4 | 1.1% |
| ewma_vol | 1 | 0.957 | 159.9 | 213.7 | 33.5% |
| ewma_vol | 5 | 1.026 | 71.5 | 125.3 | 6.7% |
| ewma_vol | 21 | 1.054 | 34.9 | 88.7 | 1.6% |
| ewma_cov_target | 1 | 0.893 | 124.5 | 160.3 | 25.8% |
| ewma_cov_target | 5 | 0.963 | 55.7 | 91.5 | 5.2% |
| ewma_cov_target | 21 | 0.991 | 27.2 | 63.0 | 1.2% |
| enhanced | 1 | 0.953 | 117.9 | 155.3 | 24.6% |
| enhanced | 5 | 1.021 | 52.7 | 90.2 | 4.9% |
| enhanced | 21 | 1.049 | 25.7 | 63.2 | 1.2% |
| static_bmk | 1 | 0.449 | 11.9 | 30.5 | 4.1% |
| static_bmk | 5 | 0.453 | 5.3 | 23.9 | 0.8% |
| static_bmk | 21 | 0.455 | 2.6 | 21.2 | 0.2% |

## Cost-input sensitivity ($1bn, 5 execution days)

σ in the impact model describes the market, not the strategy, so one estimate (EWMA) is used for every strategy; the expanding-window row checks that conclusions do not depend on that choice. ADV is a class-level assumption, so it is halved and doubled.

| Strategy | Case | Net Sharpe | Impact bps/yr | Total bps/yr |
|---|---|---:|---:|---:|
| baseline | base (EWMA sigma, ADV x1) | 0.889 | 53.8 | 87.9 |
| baseline | sigma = expanding vol | 0.884 | 59.1 | 93.2 |
| baseline | ADV x0.5 | 0.869 | 76.1 | 110.2 |
| baseline | ADV x2 | 0.903 | 38.0 | 72.2 |
| ewma_vol | base (EWMA sigma, ADV x1) | 1.026 | 71.5 | 125.3 |
| ewma_vol | sigma = expanding vol | 1.009 | 92.2 | 146.0 |
| ewma_vol | ADV x0.5 | 1.002 | 101.2 | 155.0 |
| ewma_vol | ADV x2 | 1.042 | 50.6 | 104.4 |
| ewma_cov_target | base (EWMA sigma, ADV x1) | 0.963 | 55.7 | 91.5 |
| ewma_cov_target | sigma = expanding vol | 0.955 | 62.5 | 98.3 |
| ewma_cov_target | ADV x0.5 | 0.940 | 78.7 | 114.5 |
| ewma_cov_target | ADV x2 | 0.979 | 39.4 | 75.2 |
| enhanced | base (EWMA sigma, ADV x1) | 1.021 | 52.7 | 90.2 |
| enhanced | sigma = expanding vol | 1.005 | 67.7 | 105.2 |
| enhanced | ADV x0.5 | 0.998 | 74.5 | 112.0 |
| enhanced | ADV x2 | 1.037 | 37.3 | 74.7 |
| static_bmk | base (EWMA sigma, ADV x1) | 0.453 | 5.3 | 23.9 |
| static_bmk | sigma = expanding vol | 0.454 | 4.9 | 23.5 |
| static_bmk | ADV x0.5 | 0.452 | 7.5 | 26.1 |
| static_bmk | ADV x2 | 0.454 | 3.8 | 22.4 |

## Limitations

- Cost parameters are illustrative class-level assumptions; contract multipliers are unavailable, so contract volume only flags thin markets. ADV is not scaled back in time, so early-sample impact is likely understated.
- Positions are rebalanced to target each month from drifted weights; missing returns are zero-filled; Sharpe uses RF = 0 and no collateral yield.
- The full 1976–2014 sample was already examined; subperiods are descriptive, not an untouched holdout.
