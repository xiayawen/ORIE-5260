# Out-of-sample rebalance frequency comparison with a smaller short budget

Evaluation covers 2015-01-01 through 2025-05-31, with 125 complete months. The last available quote is dated 2025-06-13. The earlier price history warms up signals and positions before the start date.

This repeats the earlier frequency experiment on the uploaded continuous futures closes. All three schedules share the same 12-month momentum rule, expanding instrument volatility, eligibility checks and close-to-close simulation. Within a month the signal combines 11 completed monthly returns and the current month-to-date return. Risk estimates update at month-end. Monthly targets form on the last weekday, weekly targets on Fridays and daily targets on weekdays. Orders fill at the next quoted close per instrument. Positions drift between fills. Each schedule keeps its original positive target weights and multiplies negative targets by 50% before orders are generated. The rule followed attribution on the same post-2014 data, so the results are exploratory.

Trading costs are charged per unit of drift-adjusted turnover. Cost scenarios are 0, 2, 5, 10 and 25 bps. They exclude separate roll, funding and market impact charges. Assets without a quote retain their last price and, if a trade remains pending, their existing holding. Some series stop before the end of the sample. The daily output reports unquoted gross exposure. The frequency results use this daily execution model and should be compared across schedules.

| Frequency | Cost (bps) | CAGR | Annualized mean return | Sharpe | Daily max drawdown | Annual turnover |
|---|---:|---:|---:|---:|---:|---:|
| monthly | 0 | +0.07% | +0.39% | 0.05 | -23.41% | 10.30× |
| monthly | 2 | -0.14% | +0.18% | 0.02 | -24.15% | 10.30× |
| monthly | 5 | -0.44% | -0.13% | -0.02 | -25.26% | 10.30× |
| monthly | 10 | -0.96% | -0.64% | -0.08 | -27.07% | 10.30× |
| monthly | 25 | -2.48% | -2.19% | -0.28 | -32.48% | 10.31× |
| weekly | 0 | +1.17% | +1.49% | 0.18 | -18.54% | 18.40× |
| weekly | 2 | +0.80% | +1.12% | 0.14 | -19.37% | 18.40× |
| weekly | 5 | +0.24% | +0.57% | 0.07 | -21.13% | 18.40× |
| weekly | 10 | -0.67% | -0.34% | -0.04 | -25.02% | 18.40× |
| weekly | 25 | -3.38% | -3.10% | -0.38 | -35.89% | 18.41× |
| daily | 0 | +1.84% | +2.13% | 0.27 | -12.94% | 35.61× |
| daily | 2 | +1.12% | +1.42% | 0.18 | -15.22% | 35.61× |
| daily | 5 | +0.04% | +0.35% | 0.04 | -19.60% | 35.61× |
| daily | 10 | -1.72% | -1.42% | -0.18 | -26.57% | 35.62× |
| daily | 25 | -6.85% | -6.73% | -0.82 | -56.18% | 35.64× |

Highest CAGR by cost assumption
- 0 bps. Daily at +1.84%.
- 2 bps. Daily at +1.12%.
- 5 bps. Weekly at +0.24%.
- 10 bps. Weekly at -0.67%.
- 25 bps. Monthly at -2.48%.

At 10 bps, a sensitivity approximates liquidation after 10 weekdays without a quote, using the last observed mark and charging trading costs. That mark can differ from an executable exit price. The resulting CAGRs are -0.97% for monthly, -0.68% for weekly, -1.73% for daily.
