# T3 alpha decay and execution horizon (daily closes, 1976-2014)

Weights: band_25 execution (T1), 12-month sign signal. Daily data end in Dec 2014, so T3 has no out-of-sample period. Method in `alpha_decay_execution.py`.

## Findings

1. With d = 0 and D = 1 the daily engine reproduces the monthly backtest (see reconciliation), so the curves are comparable with every monthly result.
2. Alpha decays slowly but measurably: about 0.05-0.06 gross Sharpe for the first day and roughly 0.01 per day afterwards; a 20-day delay loses about a quarter of gross Sharpe.
3. The monthly backtests fill at the signal close (d = 0) while Lecture 8 impact assumes 5-day execution. With a feasible schedule (start day 1, best D at $1bn) net Sharpe is about 0.07-0.09 lower than the monthly-convention figure. This is an optimistic timing assumption, not data look-ahead; main results keep the monthly convention and report the overstatement.
4. The optimal horizon grows with AUM and turnover (AQR alpha-decay vs impact trade-off): a few days for the 1/N and enhanced strategies at $100m-$1bn, longer for the higher-turnover risk-budget strategy and at $10bn.

## Reconciliation with the monthly file (d = 0, D = 1)

| strategy | monthly_file_gross_sharpe | daily_d0_gross_sharpe | correlation | average_gross_weight_with_daily_quotes |
|---|---|---|---|---|
| baseline | 0.912 | 0.906 | 0.997 | 0.999 |
| enhanced | 1.104 | 1.111 | 0.997 | 0.999 |
| rb_class | 1.075 | 1.077 | 0.998 | 0.999 |

## Alpha decay: gross Sharpe by execution delay (D = 1)

| delay_days | baseline | enhanced | rb_class |
|---|---|---|---|
| 0.000 | 0.906 | 1.111 | 1.077 |
| 1.000 | 0.850 | 1.055 | 1.026 |
| 2.000 | 0.835 | 1.038 | 1.004 |
| 3.000 | 0.816 | 1.012 | 0.976 |
| 5.000 | 0.784 | 0.984 | 0.979 |
| 10.000 | 0.741 | 0.944 | 0.940 |
| 15.000 | 0.707 | 0.891 | 0.828 |
| 20.000 | 0.668 | 0.783 | 0.796 |

## Execution horizon trade-off (start day 1)

| strategy | execution_days | gross_sharpe | net_sharpe_$100m | net_sharpe_$1bn | net_sharpe_$10bn | annual_impact_$1bn | annual_impact_$10bn |
|---|---|---|---|---|---|---|---|
| baseline | 1 | 0.850 | 0.798 | 0.741 | 0.559 | 0.80% | 2.52% |
| baseline | 2 | 0.844 | 0.799 | 0.759 | 0.631 | 0.56% | 1.78% |
| baseline | 3 | 0.836 | 0.794 | 0.762 | 0.657 | 0.46% | 1.45% |
| baseline | 5 | 0.818 | 0.780 | 0.755 | 0.673 | 0.36% | 1.13% |
| baseline | 10 | 0.783 | 0.748 | 0.730 | 0.672 | 0.25% | 0.80% |
| baseline | 15 | 0.765 | 0.731 | 0.716 | 0.669 | 0.21% | 0.65% |
| baseline | 20 | 0.752 | 0.719 | 0.706 | 0.664 | 0.18% | 0.56% |
| enhanced | 1 | 1.055 | 0.994 | 0.931 | 0.728 | 0.75% | 2.38% |
| enhanced | 2 | 1.048 | 0.995 | 0.951 | 0.809 | 0.53% | 1.69% |
| enhanced | 3 | 1.038 | 0.988 | 0.952 | 0.836 | 0.44% | 1.38% |
| enhanced | 5 | 1.024 | 0.978 | 0.949 | 0.859 | 0.34% | 1.07% |
| enhanced | 10 | 0.987 | 0.945 | 0.924 | 0.860 | 0.24% | 0.75% |
| enhanced | 15 | 0.966 | 0.925 | 0.909 | 0.856 | 0.19% | 0.62% |
| enhanced | 20 | 0.943 | 0.902 | 0.888 | 0.842 | 0.17% | 0.53% |
| rb_class | 1 | 1.026 | 0.891 | 0.720 | 0.172 | 2.27% | 7.17% |
| rb_class | 2 | 1.017 | 0.906 | 0.787 | 0.402 | 1.60% | 5.07% |
| rb_class | 3 | 1.005 | 0.904 | 0.807 | 0.494 | 1.31% | 4.14% |
| rb_class | 5 | 0.998 | 0.906 | 0.831 | 0.587 | 1.01% | 3.21% |
| rb_class | 10 | 0.975 | 0.892 | 0.838 | 0.664 | 0.72% | 2.27% |
| rb_class | 15 | 0.951 | 0.872 | 0.826 | 0.682 | 0.59% | 1.85% |
| rb_class | 20 | 0.932 | 0.855 | 0.815 | 0.688 | 0.51% | 1.60% |

## Best execution horizon (in-sample)

| strategy | aum | best_execution_days | best_net_sharpe | net_sharpe_1_day | net_sharpe_5_days |
|---|---|---|---|---|---|
| baseline | $100m | 2 | 0.799 | 0.798 | 0.780 |
| baseline | $1bn | 3 | 0.762 | 0.741 | 0.755 |
| baseline | $10bn | 5 | 0.673 | 0.559 | 0.673 |
| enhanced | $100m | 2 | 0.995 | 0.994 | 0.978 |
| enhanced | $1bn | 3 | 0.952 | 0.931 | 0.949 |
| enhanced | $10bn | 10 | 0.860 | 0.728 | 0.859 |
| rb_class | $100m | 5 | 0.906 | 0.891 | 0.906 |
| rb_class | $1bn | 10 | 0.838 | 0.720 | 0.831 |
| rb_class | $10bn | 20 | 0.688 | 0.172 | 0.587 |
