# Lecture 11 baseline on daily data (21-business-day periods)

Lecture 11 baseline on daily data, rebalanced every 21 business days (slides 17-21, 29 and 30).

Slide 21 baseline: binary 12-month signal, 12-month volatility scaling, 11% ex-ante volatility
target, 21-business-day holding periods, net of 2 bps per unit turnover + 4 rolls a year at 2 bps.
Reference statistics: slide 29 (in-sample, 21-business-day returns) and slide 30 (out-of-sample,
1/2015-6/2025). Slide 29 starts in 12/1973; our in-sample row starts in 1976.
This script rebuilds it from the daily back-adjusted closes (`*_RAD.CSV`), which reproduce the
monthly returns in MonthlyReturns_FullSample.xlsx exactly at month ends.

Specification (fixed before any result was computed):
- Universe: the 58 markets of MonthlyReturns_FullSample.xlsx (primary) and, as a check, all 66 markets of the
  course AssetMapCsv.csv (adds BC, BG, EN, ER, ES, FF, SC, ZH); daily return = close-to-close % change.
- Rebalance grid: every 21 rows of the union trading calendar, anchored so 31 Dec 2014 is a rebalance date.
- Signal: sign of the trailing 252-day compounded return. Vol: std of the trailing 252 daily returns x sqrt(252)
  (at least 200 observations). Raw weight = signal / vol / N over markets with both.
- Ex-ante target (primary): book scaled to 11% predicted vol, covariance = trailing 252-day daily sample
  covariance (pairwise) x 252. Variants: EWMA covariance of daily returns (126-day half-life), and the
  realized-vol replica (10% on trailing 36 periods of realized strategy vol). No caps in any version.
- Weights formed at the close of a rebalance date earn the next 21 days' compounded returns.
- Costs as combined_strategy.Pipeline.evaluate: roll = sum|w| x 2bp x 4/12 per period; grown = w x (1 + r - roll);
  turnover = sum|w - grown|; cost = 2bp x turnover + roll. 12 periods a year (252 / 21).


## IS 1976-2014

| | Slide | exante_11_sample_u58 | exante_11_ewma_u58 | realized_10_36p_u58 | exante_11_sample_u66 | exante_11_ewma_u66 | realized_10_36p_u66 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Avg net return | 13.2% | 15.4% | 15.1% | 11.6% | 15.2% | 14.9% | 11.7% |
| Avg gross return | — | 16.3% | 16.0% | 12.3% | 16.7% | 16.4% | 12.8% |
| Std | 10.8% | 12.6% | 12.5% | 10.1% | 12.6% | 12.4% | 10.1% |
| Sharpe | 1.22 | 1.22 | 1.21 | 1.15 | 1.21 | 1.20 | 1.16 |
| Max DD | — | -18.2% | -18.2% | -14.4% | -19.5% | -20.1% | -14.4% |
| Turnover | 17.79 | 21.33 | 20.87 | 14.01 | 32.04 | 31.41 | 20.58 |
| T-costs | — | 0.92% | 0.91% | 0.68% | 1.48% | 1.46% | 1.12% |
| Leverage | 4.62 | 6.19 | 6.11 | 5.01 | 10.54 | 10.37 | 8.81 |
| #Names | 41.4 | 42.5 | 42.5 | 42.5 | 44.7 | 44.7 | 44.7 |
| Imbalance | 1.50 | 2.04 | 2.00 | 1.65 | 4.00 | 3.93 | 3.54 |

## OOS 2015-2025

| | Slide | exante_11_sample_u58 | exante_11_ewma_u58 | realized_10_36p_u58 | exante_11_sample_u66 | exante_11_ewma_u66 | realized_10_36p_u66 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Avg net return | 3.0% | 3.2% | 3.0% | 2.0% | 1.2% | 1.0% | 0.3% |
| Avg gross return | — | 5.0% | 4.7% | 3.4% | 5.4% | 5.0% | 3.7% |
| Std | 9.5% | 13.3% | 13.0% | 11.3% | 13.1% | 12.8% | 10.9% |
| Sharpe | 0.31 | 0.24 | 0.23 | 0.18 | 0.09 | 0.08 | 0.03 |
| Max DD | — | -25.5% | -26.2% | -25.2% | -28.0% | -28.7% | -27.2% |
| Turnover | 30.46 | 43.47 | 40.83 | 29.56 | 121.85 | 115.15 | 90.94 |
| T-costs | — | 1.79% | 1.71% | 1.40% | 4.24% | 4.04% | 3.39% |
| Leverage | 7.94 | 11.54 | 11.19 | 10.07 | 22.54 | 21.76 | 19.66 |
| #Names | 56.3 | 53.9 | 53.9 | 53.9 | 58.9 | 58.9 | 58.9 |
| Imbalance | 2.70 | 3.46 | 3.53 | 3.86 | 3.85 | 4.34 | 3.90 |

## Sensitivity to the rebalance grid (58 markets, net Sharpe)

The same strategies with the 21-business-day grid started 0-18 business days after 31 Dec 2014. Offset 0 is the specification above. Nothing is chosen from this table: it shows how much of a 10-year Sharpe ratio depends on which days the book happens to rebalance.

| Offset (days) | IS exante_11_ewma | IS exante_11_sample | IS realized_10_36p | OOS exante_11_ewma | OOS exante_11_sample | OOS realized_10_36p |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.21 | 1.22 | 1.15 | 0.23 | 0.24 | 0.18 |
| 3 | 1.22 | 1.23 | 1.13 | 0.06 | 0.08 | 0.03 |
| 6 | 1.18 | 1.20 | 1.12 | 0.11 | 0.13 | 0.03 |
| 9 | 1.17 | 1.18 | 1.13 | 0.19 | 0.21 | 0.14 |
| 12 | 1.15 | 1.16 | 1.11 | 0.03 | 0.05 | 0.06 |
| 15 | 1.22 | 1.23 | 1.22 | 0.18 | 0.18 | 0.22 |
| 18 | 1.25 | 1.26 | 1.23 | 0.20 | 0.20 | 0.22 |
| **Mean** | **1.20** | **1.21** | **1.16** | **0.14** | **0.15** | **0.13** |
| Min - max | 1.15 - 1.25 | 1.16 - 1.26 | 1.11 - 1.23 | 0.03 - 0.23 | 0.05 - 0.24 | 0.03 - 0.22 |

## Reading

- With the grid anchored at 31 Dec 2014 (offset 0), OOS net return matches slide 30 (3.2% vs 3.0%), but the OOS Sharpe of the primary version ranges from 0.05 to 0.24 across grid starts (mean 0.15), all below slide 30's 0.31; offset 0 happens to be the highest.
- In sample, the primary version's Sharpe matches slide 29 (1.22 vs 1.22); its volatility, turnover and leverage are about 15-35% above slide 29.
- Out of sample, volatility, turnover and leverage are about 40-45% above slide 30, so the scale of the book (how much low-volatility rate futures it holds) still differs from the professor's.
- The 66-market course asset map adds Fed funds futures (FF), whose tiny volatility pushes leverage to about 22x; the 58-market universe is the closer match.
