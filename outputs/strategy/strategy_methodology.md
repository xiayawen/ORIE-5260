# TSMOM Baseline vs Static Benchmark

## Baseline
- TSMOM baseline: 12-month time-series momentum for each futures underlying.
- TSMOM position: long if trailing 12-month return is positive, short if negative.
- Sizing: each instrument is scaled to 40% annualized volatility using full-sample realized volatility, then averaged across active instruments.
- Timing: signals are computed using information through month t and traded in month t+1.
- Static benchmark: same volatility-scaled instruments, but always long and equally averaged.
- Full-sample volatility contains future information; this is a retrospective classroom baseline, not an out-of-sample backtest.
- No transaction costs, slippage, financing costs, or cash interest are included.

## Alpha illustration
- Portfolio alpha is measured as monthly TSMOM return minus monthly Static benchmark return.
- Asset-class and instrument tables compare TSMOM and Static contribution streams.
- Alpha here is a return difference, not a factor-regression intercept. Low correlation alone does not establish added value.
- TSMOM requires 12 valid months while Static starts earlier, so their active universes can differ.
