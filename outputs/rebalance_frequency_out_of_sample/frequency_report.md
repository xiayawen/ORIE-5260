# Out-of-sample rebalance frequency comparison

Evaluation covers 2015-01-01 through 2025-05-31, with 125 complete months. The last available quote is dated 2025-06-13. The earlier price history warms up signals and positions before the start date.

This repeats the earlier frequency experiment on the uploaded continuous futures closes. All three schedules share the same 12-month momentum rule, expanding instrument volatility, eligibility checks and close-to-close simulation. Within a month the signal combines 11 completed monthly returns and the current month-to-date return. Risk estimates update at month-end. Monthly targets form on the last weekday, weekly targets on Fridays and daily targets on weekdays. Orders fill at the next quoted close per instrument. Positions drift between fills.

Trading costs are charged per unit of drift-adjusted turnover. Cost scenarios are 0, 2, 5, 10 and 25 bps. They exclude separate roll, funding and market impact charges. Assets without a quote retain their last price and, if a trade remains pending, their existing holding. Some series stop before the end of the sample. The daily output reports unquoted gross exposure. The frequency results use this daily execution model and should be compared across schedules.

| Frequency | Cost (bps) | CAGR | Annualized mean return | Sharpe | Daily max drawdown | Annual turnover |
|---|---:|---:|---:|---:|---:|---:|
| monthly | 0 | -1.85% | -1.24% | -0.11 | -38.41% | 14.12× |
| monthly | 2 | -2.13% | -1.52% | -0.14 | -39.25% | 14.12× |
| monthly | 5 | -2.54% | -1.94% | -0.17 | -40.49% | 14.13× |
| monthly | 10 | -3.23% | -2.65% | -0.24 | -42.52% | 14.13× |
| monthly | 25 | -5.27% | -4.77% | -0.43 | -49.83% | 14.15× |
| weekly | 0 | -0.44% | +0.17% | 0.01 | -32.76% | 25.17× |
| weekly | 2 | -0.94% | -0.33% | -0.03 | -34.42% | 25.17× |
| weekly | 5 | -1.69% | -1.09% | -0.10 | -36.82% | 25.18× |
| weekly | 10 | -2.92% | -2.34% | -0.21 | -40.63% | 25.18× |
| weekly | 25 | -6.53% | -6.10% | -0.54 | -55.43% | 25.20× |
| daily | 0 | +0.47% | +1.09% | 0.10 | -26.03% | 48.86× |
| daily | 2 | -0.51% | +0.12% | 0.01 | -29.44% | 48.86× |
| daily | 5 | -1.96% | -1.35% | -0.12 | -34.27% | 48.86× |
| daily | 10 | -4.33% | -3.78% | -0.33 | -43.61% | 48.87× |
| daily | 25 | -11.11% | -11.05% | -0.95 | -73.64% | 48.92× |

Highest CAGR by cost assumption
- 0 bps. Daily at +0.47%.
- 2 bps. Daily at -0.51%.
- 5 bps. Weekly at -1.69%.
- 10 bps. Weekly at -2.92%.
- 25 bps. Monthly at -5.27%.

At 10 bps, a sensitivity approximates liquidation after 10 weekdays without a quote, using the last observed mark and charging trading costs. That mark can differ from an executable exit price. The resulting CAGRs are -3.26% for monthly, -2.94% for weekly, -4.34% for daily.
