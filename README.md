# ORIE 5260 Futures Momentum Project

This project studies time-series momentum (TSMOM) across a diversified futures universe. It builds a lecture-style baseline, compares it with an always-long benchmark, and tests alternative signals, risk estimates, portfolio allocations, transaction costs, and factor explanations.

## Data

- `MonthlyReturns.csv`: monthly returns for 58 futures series from January 1969 to December 2014.
- `AssetMapCsv.csv`: instrument names, currencies, and asset classes: commodities, equity indices, fixed income, and FX.
- `FuturesUnderlyingData/`: daily price, volume, and open-interest files used for data checks and return reconstruction.
- `Lecture3_livedata.xlsx`: monthly SG Trend, GSCI, risk-free rate, and equity-factor data from 2000 to 2014.

The strategy backtests use monthly returns and rebalance monthly. Weights formed using information through month `t` are applied to returns in month `t+1`.

## Strategies and experiments

The core TSMOM strategy takes a long position when an instrument's trailing momentum is positive and a short position when it is negative. Positions are scaled inversely to estimated volatility and diversified across eligible instruments.

The always-long static benchmark uses similar volatility scaling and diversification but does not use the momentum direction.

The main experiments are:

- Different momentum horizons: 1, 3, 6, and 12 months.
- EWMA volatility with a six-month half-life.
- Equal risk budgets across asset classes instead of equal allocation across instruments.
- A multi-lookback signal averaging 1-, 3-, 6-, and 12-month momentum.
- A combined strategy using EWMA volatility, asset-class allocation, and the multi-lookback signal.
- Rolling-volatility portfolios with transaction-cost scenarios of 0, 5, 10, and 25 basis points.
- Exploratory regressions against the static benchmark and six equity factors.

## Python files

### `strategy_backtest.py`

Implements the original classroom-style baseline:

- Uses the sign of compounded trailing 12-month returns as the TSMOM signal.
- Scales each instrument using its full-sample annualized volatility and a 40% instrument-level volatility parameter.
- Compares TSMOM with an always-long static benchmark.
- Reports performance, turnover, correlations, and return differences by asset class and instrument.

Because volatility is estimated from the full sample, this version contains look-ahead bias. It is best treated as an initial retrospective benchmark.

### `strategy_backtest_adj.py`

Implements the adjusted baseline and the main strategy experiments:

- Replaces full-sample volatility with expanding-window volatility using only information available through each month.
- Requires at least 36 valid monthly observations for the volatility estimate.
- Uses the sign of the sum of trailing monthly returns for its momentum signals.
- Reproduces the 1-, 3-, 6-, and 12-month lookback comparison.
- Tests EWMA volatility, asset-class risk budgets, multi-lookback momentum, and their combination.
- Evaluates results from January 1976 through December 2014.

This is the project's main script for comparing the baseline with the four strategy experiments.

### `rolling_backtest.py`

Runs a separate rolling-volatility robustness analysis:

- Imports data loading, compounded momentum, and the original comparison strategies from `strategy_backtest.py`; it does not run `strategy_backtest_adj.py`.
- Uses trailing 12-month volatility and a matched eligibility universe for TSMOM and the static benchmark.
- Compares the rolling portfolios with the original and matched full-sample-volatility controls.
- Applies transaction costs based on monthly changes in target weights.
- Runs exploratory regressions against the static benchmark and the six factors in `Lecture3_livedata.xlsx`, using HAC standard errors.

This script focuses on avoiding full-sample volatility look-ahead, aligning the comparison universes, and measuring sensitivity to trading costs.

### `analysis_eda.py`

Performs data-quality and exploratory analysis, including coverage, missingness, summary statistics, robust outlier detection, correlations, and a comparison of supplied monthly returns with returns reconstructed from daily closes.

### `generate_strategy_analysis.py`

Generates descriptive statistics for instruments and equal-weighted asset-class return series. It also compares the adjusted TSMOM baseline with SG Trend over their common 2000–2014 sample, including performance statistics, HAC regressions, cumulative growth, and rolling correlation. The script loads saved adjusted-strategy returns when available and otherwise rebuilds the baseline from `strategy_backtest_adj.py`.

## Outputs

The scripts write tables, figures, and short reports under `outputs/` and `reports/` when run. Asset-class and SG Trend comparison outputs are written to `outputs/analysis/`. The saved root-level CSV files contain selected strategy summaries and monthly return series.

## Important limitations

- The source and adjustment method for the continuous futures series are not documented in the repository.
- Missing realized returns for held instruments are filled with zero in the backtests.
- The 40% scaling parameter applies at the instrument level before diversification; it is not a portfolio volatility target.
- The original baseline uses future information in its full-sample volatility estimate.
- Transaction costs are illustrative scenarios rather than estimates from contract-level execution data.
- No leverage cap, margin model, financing cost, or contract-roll cost is included.
