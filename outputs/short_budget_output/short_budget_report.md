# Leverage and imbalance with a smaller short budget

Evaluation covers 2015-01 through 2025-05, with 125 months. The strategy starts from the shared 10% price trend targets, keeps each positive weight, and multiplies each negative weight by 50%. The targets earn returns in the next month. This reduces gross exposure and increases signed net exposure. The matched control scales both sides proportionally to the same gross exposure each month, keeping the original long–short proportions.

We use the shared model of 2 bps per unit of target-weight turnover and 2 bps per roll at 4 rolls per year. Missing realized returns are treated as zero, as in the shared baseline.

| Strategy | Gross CAGR | Net CAGR | Annualized mean net return | Max drawdown | Annual turnover | Avg. gross | Avg. signed net |
|---|---:|---:|---:|---:|---:|---:|---:|
| Shared price trend baseline | +0.23% | -0.42% | +0.13% | -26.33% | 14.70× | 4.57× | +0.82× |
| Half-sized short positions | +1.40% | +0.88% | +1.20% | -16.74% | 11.14× | 3.63× | +1.76× |
| Same gross exposure, original long–short proportions | +0.38% | -0.15% | +0.19% | -21.53% | 12.26× | 3.63× | +0.84× |

The half-short strategy improves net CAGR by 1.31 percentage points versus the baseline and 1.03 points versus the control at equal gross exposure.

| Period | Baseline net CAGR | Half-short net CAGR | Matched control net CAGR |
|---|---:|---:|---:|
| 1980–1997 | +12.51% | +10.41% | +9.64% |
| 1998–2014 | +11.75% | +10.68% | +9.81% |
| 2015–2019 | -0.52% | +0.88% | +0.13% |
| 2020–latest | -0.34% | +0.88% | -0.41% |

| Cost per unit traded or rolled | Baseline net CAGR | Half-short net CAGR | Matched control net CAGR |
|---|---:|---:|---:|
| 0 bps | +0.23% | +1.40% | +0.38% |
| 2 bps | -0.42% | +0.88% | -0.15% |
| 5 bps | -1.40% | +0.11% | -0.95% |
| 10 bps | -3.02% | -1.17% | -2.27% |

Short budgets tested on the later sample were 100% (-0.42% net CAGR), 75% (+0.25% net CAGR), 50% (+0.88% net CAGR), 25% (+1.46% net CAGR), 0% (+1.99% net CAGR). We favored the half-short rule to retain meaningful short exposure. The idea followed the earlier return attribution on the same post-2014 period, so this is an exploratory result. The historical comparisons show the trade-off with the original strategy before 2015. The higher net long exposure also increases sensitivity to sustained market declines.

Run `python short_budget_backtest.py` from the repository root to reproduce the comparison.
