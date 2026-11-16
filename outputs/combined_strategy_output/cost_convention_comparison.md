# Like-for-like comparison with the Lecture 11 baseline

Lecture 11 reports the course baseline OOS (Jan 2015 - Jun 2025) at Sharpe 0.31 with 7.9x leverage, 2.7x net long and turnover 30, net of 2 bps per unit turnover plus 4 rolls a year at 2 bps. `slide_baseline` replicates its construction on our monthly data (12-month sign, 1/(12m vol) with no floor, 10% target on trailing 36-month realized vol). It matches the slide's IS profile (Sharpe 1.13-1.22, leverage 4.6x, net long 1.5x) but not its OOS Sharpe: the slide uses daily data and a different OOS panel (56 active names), which we do not have.

Selection always used the Lecture 8 model at $1bn; the 2 bps convention is reporting only.

## Net of Lecture 8 model, $1bn

| Strategy | IS Sharpe | OOS Sharpe | OOS gross Sharpe | IS vol | OOS vol | OOS Max DD | OOS gross exp. | OOS net exp. | OOS turnover | OOS cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| slide_baseline | 1.15 | 0.08 | 0.20 | 10.2% | 10.6% | -22.2% | 9.2x | +4.0x | 29.1 | 1.24% |
| baseline | 0.89 | -0.09 | -0.02 | 11.1% | 11.1% | -33.1% | 4.4x | +0.7x | 13.3 | 0.78% |
| enhanced | 1.02 | -0.01 | 0.07 | 9.4% | 7.1% | -15.0% | 3.9x | +0.8x | 12.8 | 0.60% |
| continuous_signal | 1.10 | 0.13 | 0.20 | 10.1% | 7.5% | -12.3% | 3.7x | +0.9x | 15.3 | 0.59% |
| band_25 | 1.03 | 0.11 | 0.18 | 8.3% | 6.1% | -10.8% | 3.3x | +0.7x | 8.4 | 0.42% |
| histgb_overlay | 1.02 | 0.19 | 0.29 | 9.4% | 6.5% | -10.9% | 3.9x | +1.8x | 17.5 | 0.69% |
| final | 1.10 | 0.13 | 0.20 | 10.1% | 7.5% | -12.3% | 3.7x | +0.9x | 15.3 | 0.59% |
| walk_forward_clean | 1.03 | 0.13 | 0.20 | 9.9% | 7.5% | -12.3% | 3.7x | +0.9x | 15.3 | 0.59% |

## Net of Lecture 11: 2 bps + 4 rolls/yr

| Strategy | IS Sharpe | OOS Sharpe | OOS gross Sharpe | IS vol | OOS vol | OOS Max DD | OOS gross exp. | OOS net exp. | OOS turnover | OOS cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| slide_baseline | 1.18 | 0.08 | 0.20 | 10.2% | 10.6% | -22.5% | 9.2x | +4.0x | 29.1 | 1.32% |
| baseline | 0.93 | -0.08 | -0.02 | 11.1% | 11.1% | -32.6% | 4.4x | +0.7x | 13.3 | 0.61% |
| enhanced | 1.07 | -0.01 | 0.07 | 9.5% | 7.1% | -14.4% | 3.9x | +0.8x | 12.8 | 0.56% |
| continuous_signal | 1.13 | 0.12 | 0.20 | 10.1% | 7.5% | -11.9% | 3.7x | +0.9x | 15.3 | 0.60% |
| band_25 | 1.06 | 0.11 | 0.18 | 8.3% | 6.1% | -10.5% | 3.3x | +0.7x | 8.4 | 0.43% |
| histgb_overlay | 1.07 | 0.19 | 0.29 | 9.4% | 6.5% | -10.5% | 3.9x | +1.8x | 17.5 | 0.66% |
| final | 1.13 | 0.12 | 0.20 | 10.1% | 7.5% | -11.9% | 3.7x | +0.9x | 15.3 | 0.60% |
| walk_forward_clean | 1.07 | 0.12 | 0.20 | 10.0% | 7.5% | -11.9% | 3.7x | +0.9x | 15.3 | 0.60% |

Rows other than the two baselines, `enhanced`, `final` and `walk_forward_clean` are `enhanced` plus that one component. † = not a clean out-of-sample test.
