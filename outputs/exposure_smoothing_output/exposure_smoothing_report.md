# Out-of-sample leverage and imbalance smoothing

Evaluation covers 2015-01 through 2025-05, with 125 monthly returns.
The shared price trend baseline uses the original 12-month momentum signal, a rolling volatility estimate, and a 10% portfolio volatility target. Its weights form the starting point for both variants.

Gross exposure is the sum of absolute weights. Net share is signed net exposure divided by gross exposure. The first variant smooths gross exposure with a trailing 3-month average and scales both books proportionally. The second also smooths net share over the same window, then sets long and short notionals from gross exposure and the smoothed share. Each side may use up to 1.25 times its baseline notional. Existing assets retain their direction and their relative weights within each book. The two variants match on gross exposure every month.

Recorded targets use information through formation month and earn returns the following month. All variants use the team cost model with 2 bps per unit of turnover and 2 bps per roll at 4 rolls annually. The parameters were fixed for this run. The evaluation period had already been examined for other specifications.

| Strategy | Gross CAGR | Net CAGR | Annualized mean net return | Max drawdown | Annual turnover | Avg. gross | Avg. absolute net |
|---|---:|---:|---:|---:|---:|---:|---:|
| Shared price trend baseline | +0.23% | -0.42% | +0.13% | -26.33% | 14.70× | 4.57× | 1.79× |
| Smooth leverage only | +0.27% | -0.39% | +0.17% | -27.71% | 14.75× | 4.60× | 1.81× |
| Smooth leverage and imbalance | +0.76% | +0.04% | +0.63% | -24.95% | 17.40× | 4.60× | 1.77× |

Smoothing leverage alone changes net CAGR by +0.03 percentage points versus the baseline. At the same monthly gross exposure, smoothing imbalance as well changes net CAGR by +0.43 points and maximum drawdown by +2.76 points. A positive drawdown difference corresponds to a shallower loss.

The cost model uses monthly target-weight turnover. Missing returns follow the shared baseline convention and contribute zero realized P&L. The performance table and monthly returns are provided as CSV files.
