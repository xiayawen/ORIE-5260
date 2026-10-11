# ORIE 5260 Futures Momentum Project

This project studies time-series momentum (TSMOM) across a diversified futures universe. It replicates a lecture baseline, corrects its main look-ahead issue, tests several strategy variations, and evaluates the baseline's returns, risk, and relationship with external benchmarks.

## Data used

- `MonthlyReturns.csv`: monthly returns for 58 futures series from January 1969 to December 2014. The universe includes commodities, equity indices, fixed income, and FX.
- `AssetMapCsv.csv`: instrument names, currencies, and asset-class classifications.
- `FuturesUnderlyingData/`: daily price, volume, and open-interest files used for data checks and monthly-return reconstruction.
- `Lecture3_livedata.xlsx`: monthly SG Trend, GSCI, risk-free rate, and Mkt-RF, SMB, HML, Mom, RMW, and CMA factor returns from January 2000 to December 2014.

The strategy backtests use monthly returns and rebalance monthly. Weights formed with information available through month `t` are applied to returns in month `t+1`.

## Scripts

- `analysis_eda.py`: checks data quality and produces descriptive statistics.
- `strategy_backtest.py`: runs the original classroom-style TSMOM baseline and static benchmark using full-sample volatility.
- `strategy_backtest_adj.py`: runs the adjusted expanding-volatility baseline and the main strategy experiments.
- `rolling_backtest.py`: runs a separate rolling-volatility robustness backtest with matched universes and transaction-cost scenarios.
- `generate_strategy_analysis.py`: produces asset-class statistics, benchmark comparisons, and factor regressions.
- `baseline_return_attribution.py`: attributes baseline returns by instrument, asset class, direction, period, drawdown, and market regime.
- `baseline_risk_analysis.py`: describes exposure, realized risk, drawdowns, and diagonal risk concentration.
- `validate_diagonal_risk_model.py`: compares diagonal predicted volatility with subsequent realized volatility.
- `signal_diagnostics.py`: documentation stub for planned autocorrelation and signal-predictiveness analysis.
- `baseline_performance_analysis.py`: documentation stub for a planned consolidated baseline-performance analysis.

Each implemented script writes its tables and figures to a corresponding folder under `outputs/`.

## Exploratory data analysis

`analysis_eda.py` performs the project's data-quality and exploratory analysis. It:

- Summarizes return distributions by instrument and asset class.
- Measures data coverage and missingness.
- Flags unusually large monthly returns using robust outlier rules.
- Calculates the cross-instrument return correlation matrix.
- Reconstructs monthly returns from daily closing prices and compares them with the supplied monthly-return file.

The results are saved in `outputs/eda_output/`.

## Baseline strategies

### Original classroom baseline

`strategy_backtest.py` implements a 12-month TSMOM strategy:

- The signal is the sign of the compounded trailing 12-month return.
- A positive signal is long and a negative signal is short.
- Each instrument is scaled using `40% / annualized instrument volatility`.
- Active positions are equally averaged.
- Signals and weights formed in month `t` earn returns in month `t+1`.

It also constructs an always-long static benchmark using the same volatility scaling and equal allocation. Its volatility estimate uses the full sample, so it contains look-ahead bias and is treated as a retrospective classroom benchmark.

### Adjusted baseline

`strategy_backtest_adj.py` is the main baseline implementation:

- It replaces full-sample volatility with expanding-window volatility using at least 36 valid monthly observations.
- It uses the sign of the sum of trailing 12 monthly returns as the baseline signal.
- It retains the 40% instrument-level scaling and equal allocation across eligible instruments.
- It evaluates the strategy from January 1976 through December 2014.

The 40% value is an instrument-level scaling parameter before diversification. It is not a 40% portfolio-volatility target. The baseline risk model is diagonal and assumes cross-instrument covariances are zero.

`strategy_backtest_adj.py` also tests:

- Momentum lookbacks of 1, 3, 6, and 12 months.
- EWMA volatility with a six-month half-life.
- Equal risk budgets across asset classes.
- A signal averaging 1-, 3-, 6-, and 12-month momentum.
- A combined EWMA, asset-class-budget, and multi-lookback strategy.

## Backtests conducted

`strategy_backtest.py` compares the original 12-month TSMOM baseline with the always-long static benchmark. It reports cumulative performance, annualized return and volatility, Sharpe ratio, maximum drawdown, turnover, and return differences by instrument and asset class.

`strategy_backtest_adj.py` backtests the adjusted baseline, the four strategy experiments, the four individual momentum lookbacks, and the static benchmark. All strategies use a one-month execution lag. Results include cumulative returns, drawdowns, realized volatility, turnover, and volatility-matched comparisons.

`rolling_backtest.py` is a separate robustness exercise and does not run `strategy_backtest_adj.py`. It:

- Uses compounded 12-month momentum and trailing 12-month volatility.
- Gives TSMOM and the static benchmark the same eligibility universe.
- Compares rolling-volatility portfolios with full-sample-volatility controls.
- Applies illustrative transaction costs of 0, 5, 10, and 25 basis points per one-way change in target weight.
- Runs exploratory HAC regressions against the static benchmark and six equity factors.

Transaction costs are sensitivity assumptions. The backtests do not include contract-specific spreads, roll costs, financing, cash interest, margin requirements, or leverage caps. Missing realized returns for held instruments are filled with zero.

## Analysis completed and planned

The baseline-analysis plan contains seven items.

### 1. Autocorrelation analysis — planned

`signal_diagnostics.py` will calculate return autocorrelation at lags 1–12, autocorrelation of absolute and squared returns, results by instrument and asset class, and stability across periods. The file currently contains documentation comments only.

### 2. Signal-predictiveness analysis — planned

`signal_diagnostics.py` will test next-month returns following positive and negative signals, return spreads, directional hit rates, 1-, 3-, 6-, and 12-month signals, and results by asset class and period. This analysis has not yet been implemented.

### 3. Baseline performance analysis — planned as a consolidated script

`baseline_performance_analysis.py` will consolidate cumulative and rolling performance, drawdown recovery, turnover, transaction costs, and gross, net, long, and short exposure. Several individual measures already appear in the existing backtests, but the dedicated script currently contains documentation comments only.

### 4. Return attribution — completed

`baseline_return_attribution.py` attributes the adjusted baseline by:

- Instrument and asset class.
- Long and short positions.
- Decade.
- Major drawdown event.
- S&P 500 futures proxy bull and bear regime.

The regime definition uses the continuous `SP` futures return series. An episode is classified as bear from the preceding peak through recovery when its drawdown reaches 20%. The regime sample begins in May 1982 and is an internal proxy rather than an official S&P 500 cash-index classification. Results are saved in `outputs/baseline_return_attribution_output/`.

### 5. Baseline risk analysis — completed

`baseline_risk_analysis.py` reports:

- Gross, net, long, and short exposure.
- Rolling 12-, 36-, and 60-month realized volatility.
- Drawdown depth and duration.
- Diagonal variance contribution by instrument and asset class.
- Risk concentration and effective numbers of risk positions.

This analysis describes the existing diagonal model. It does not add covariances or change strategy weights. Results are saved in `outputs/baseline_risk_analysis_output/`.

### 6. Diagonal risk-model validation — completed

`validate_diagonal_risk_model.py` compares formation-date predicted diagonal volatility with fixed-weight realized volatility over:

- The following 12 months as the primary horizon.
- The following three months as a robustness check.

It reports forecast bias, absolute and squared error, forecast-realized correlation, exceedance frequency, and results by decade, asset class, and high-volatility period. It uses the existing diagonal model only; covariance enhancement is deferred. Results are saved in `outputs/risk_model_validation_output/`.

### 7. Benchmark and factor comparison — completed

`generate_strategy_analysis.py` compares the adjusted baseline with:

- The always-long static futures benchmark over the common 1976–2014 sample.
- SG Trend over the available January 2000–December 2014 sample.

It reports raw and volatility-matched results, cumulative growth, drawdowns, rolling 36-month return, volatility and Sharpe ratio, correlation, tracking error, and HAC regression alpha and beta. It also runs separate and joint regressions against Mkt-RF, SMB, HML, Mom, RMW, and CMA and estimates rolling 60-month joint-model betas.

Volatility matching uses full-sample realized volatility and is descriptive rather than tradable. The equity factors are also an incomplete risk model for a diversified futures portfolio. Results are saved in `outputs/strategy_analysis_output/`.

The planned covariance-aware risk model and portfolio-level volatility targeting are later strategy enhancements and are not part of items 1–7 implemented here.
