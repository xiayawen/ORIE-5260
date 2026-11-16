# Cost-convention comparison

`slide_baseline` is the official baseline (Lecture 11 replica: binary 12-month signal, 1/(12-month vol)/N with no floor, 10% target on trailing 36-month realized vol, no caps). `slide_baseline_exante` is the literal slide-21 reading (11% ex-ante target on the EWMA-covariance forecast); it overshoots slide 21 on vol, turnover and leverage. `baseline` is the Lecture 6 course baseline used in the midterm.

Selection used Lecture 11: 2 bps + 4 rolls/yr; Lecture 8 model, $1bn is a robustness check.

## Net of Lecture 11: 2 bps + 4 rolls/yr

| Strategy | IS Sharpe | OOS Sharpe | OOS gross Sharpe | IS vol | OOS vol | OOS Max DD | OOS leverage | OOS imbalance | OOS names | OOS turnover | OOS cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| slide_baseline | 1.18 | 0.08 | 0.20 | 10.2% | 10.6% | -22.5% | 9.2x | +4.0x | 56.1 | 28.6 | 1.30% |
| slide_baseline_exante | 1.23 | 0.04 | 0.18 | 12.5% | 12.6% | -24.6% | 11.0x | +4.3x | 56.1 | 43.7 | 1.75% |
| baseline | 0.93 | -0.08 | -0.02 | 11.1% | 11.1% | -32.6% | 4.4x | +0.7x | 56.1 | 12.5 | 0.60% |
| enhanced | 1.07 | -0.01 | 0.07 | 9.5% | 7.1% | -14.4% | 3.9x | +0.8x | 56.1 | 12.8 | 0.56% |
| continuous_signal | 1.13 | 0.12 | 0.20 | 10.1% | 7.5% | -11.9% | 3.7x | +0.9x | 56.1 | 15.3 | 0.60% |
| band_25 | 1.06 | 0.10 | 0.18 | 8.3% | 6.1% | -10.5% | 3.3x | +0.7x | 56.1 | 8.7 | 0.43% |
| histgb_overlay | 1.07 | 0.19 | 0.29 | 9.4% | 6.5% | -10.5% | 3.9x | +1.8x | 56.1 | 17.5 | 0.66% |
| final | 1.13 | 0.12 | 0.20 | 10.1% | 7.5% | -11.9% | 3.7x | +0.9x | 56.1 | 15.3 | 0.60% |
| sensitivity_cont_econ | 1.15 | 0.12 | 0.20 | 10.2% | 7.6% | -14.7% | 3.7x | +0.5x | 56.1 | 15.3 | 0.60% |
| walk_forward_clean | 1.00 | 0.12 | 0.20 | 9.7% | 7.5% | -11.9% | 3.7x | +0.9x | 56.1 | 15.3 | 0.60% |

## Net of Lecture 8 model, $1bn

| Strategy | IS Sharpe | OOS Sharpe | OOS gross Sharpe | IS vol | OOS vol | OOS Max DD | OOS leverage | OOS imbalance | OOS names | OOS turnover | OOS cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| slide_baseline | 1.15 | 0.08 | 0.20 | 10.2% | 10.6% | -22.2% | 9.2x | +4.0x | 56.1 | 29.1 | 1.24% |
| slide_baseline_exante | 1.18 | 0.03 | 0.18 | 12.5% | 12.7% | -24.7% | 11.0x | +4.3x | 56.1 | 43.7 | 1.84% |
| baseline | 0.89 | -0.09 | -0.02 | 11.1% | 11.1% | -33.1% | 4.4x | +0.7x | 56.1 | 13.3 | 0.78% |
| enhanced | 1.02 | -0.01 | 0.07 | 9.4% | 7.1% | -15.0% | 3.9x | +0.8x | 56.1 | 12.8 | 0.60% |
| continuous_signal | 1.10 | 0.13 | 0.20 | 10.1% | 7.5% | -12.3% | 3.7x | +0.9x | 56.1 | 15.3 | 0.59% |
| band_25 | 1.03 | 0.11 | 0.18 | 8.3% | 6.1% | -10.8% | 3.3x | +0.7x | 56.1 | 8.4 | 0.42% |
| histgb_overlay | 1.02 | 0.19 | 0.29 | 9.4% | 6.5% | -10.9% | 3.9x | +1.8x | 56.1 | 17.5 | 0.69% |
| final | 1.10 | 0.13 | 0.20 | 10.1% | 7.5% | -12.3% | 3.7x | +0.9x | 56.1 | 15.3 | 0.59% |
| sensitivity_cont_econ | 1.12 | 0.12 | 0.20 | 10.2% | 7.6% | -15.2% | 3.7x | +0.5x | 56.1 | 15.2 | 0.60% |
| walk_forward_clean | 0.96 | 0.13 | 0.20 | 9.7% | 7.5% | -12.3% | 3.7x | +0.9x | 56.1 | 15.3 | 0.59% |

Rows other than the two baselines, `enhanced`, `final`, `walk_forward_clean` and the sensitivity row are `enhanced` plus that one component. † = not a clean out-of-sample test.

`sensitivity_cont_econ` = enhanced + continuous signal + economic trend. Its IS gain over `final` is +0.020, below the 0.05 threshold, so the selection rule did not choose it; it was run on request after the final strategy was known. Its OOS column is information, not evidence for adopting it.
