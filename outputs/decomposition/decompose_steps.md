# Step-by-step decomposition

21-business-day period endpoints; IS = 1976-2014, OOS = 2015-May 2025. Net of 2 bps per unit traded + 4 rolls a year at 2 bps.

| Step | Construction | IS Net ret | IS Vol | IS Sharpe | IS Max DD | IS Turnover | IS Cost | IS Gross | IS |Net| | OOS Net ret | OOS Vol | OOS Sharpe | OOS Max DD | OOS Turnover | OOS Cost | OOS Gross | OOS |Net| |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Trend sleeve only, 10% scaling, no limits, full rebalance | 14.0% | 11.4% | 1.222 | -16.6% | 19.3 | 0.83% | 5.60x | 2.78x | 2.9% | 12.1% | 0.243 | -23.2% | 39.4 | 1.62% | 10.47x | 5.51x |
| 2 | Four-sleeve blend, 10% scaling, no limits, full rebalance (selected final) | 14.1% | 11.0% | 1.285 | -21.3% | 25.1 | 0.89% | 4.92x | 2.39x | 3.6% | 10.4% | 0.343 | -13.6% | 49.0 | 1.89% | 11.30x | 6.66x |
| 2b | Four-sleeve blend, not re-scaled, no limits, full rebalance | 9.6% | 7.7% | 1.248 | -17.1% | 17.0 | 0.61% | 3.36x | 1.63x | 2.0% | 6.4% | 0.317 | -8.2% | 31.9 | 1.24% | 7.52x | 4.63x |
| 3 | Blend + four limits, full rebalance | 6.4% | 5.7% | 1.124 | -12.5% | 11.6 | 0.39% | 1.95x | 0.72x | 0.5% | 4.3% | 0.115 | -7.7% | 11.4 | 0.40% | 2.17x | 0.73x |
| 4 | Blend + four limits + gamma=5 cost-aware execution | 5.0% | 5.2% | 0.964 | -12.1% | 3.5 | 0.19% | 1.47x | 0.62x | 2.1% | 4.1% | 0.501 | -5.5% | 2.4 | 0.15% | 1.30x | 0.61x |
