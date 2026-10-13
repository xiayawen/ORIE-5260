# ORIE 5260 Futures Momentum Project

## Project overview

This project studies time-series momentum (TSMOM) across a diversified futures universe. The work has three stages:

1. **Understand and validate the data** through exploratory data analysis.
2. **Construct a transparent baseline strategy** using past returns and expanding volatility estimates.
3. **Evaluate the baseline** through signal diagnostics, performance analysis, return and risk attribution, risk-model validation, and benchmark comparisons.

The current repository completes these baseline analyses. The next stage is to enhance the risk model with cross-market covariance and introduce portfolio-level volatility targeting.

For a concise discussion of the methodology, evidence, findings, and proposed enhancements, see [`midterm_report.md`](midterm_report.md).

## Data

- `MonthlyReturns.csv`: monthly returns for 58 futures markets from January 1969 to December 2014.
- `AssetMapCsv.csv`: instrument names, currencies, and asset-class classifications.
- `FuturesUnderlyingData/`: daily price, volume, and open-interest files used for data validation and monthly-return reconstruction.
- `Lecture3_livedata.xlsx`: SG Trend, GSCI, risk-free rate, and Mkt-RF, SMB, HML, Mom, RMW, and CMA factor returns from January 2000 to December 2014.

The futures universe contains commodities, equity indices, fixed income, and FX. The panel is unbalanced because markets begin at different dates.

## Project workflow and scripts

### 1. Explore and validate the data

#### `analysis_eda.py`

Performs the initial data review:

- Summarizes return distributions and coverage by instrument and asset class.
- Measures missingness and flags unusually large monthly returns.
- Calculates the cross-market correlation matrix.
- Reconstructs monthly returns from daily closing prices and compares them with the supplied monthly file.

Outliers are flagged for review rather than automatically removed. EDA tables, figures, and a short report are written to `outputs/eda_output/`.

### 2. Construct the baseline strategies

#### `strategy_backtest.py`

Implements the original classroom-style 12-month TSMOM strategy and an always-long static benchmark. It uses full-sample volatility, so its volatility scaling contains look-ahead bias. This version is retained as a classroom reference rather than the primary baseline.

#### `strategy_backtest_adj.py`

Implements the main adjusted baseline and removes the full-sample-volatility look-ahead:

- **Signal:** sign of the sum of the previous 12 monthly returns.
- **Instrument risk estimate:** expanding annualized volatility with at least 36 valid monthly observations.
- **Position scaling:** signal multiplied by `40% / instrument volatility`.
- **Portfolio allocation:** equal allocation across eligible instruments.
- **Timing:** information through month `t` forms weights that earn returns in month `t+1`.
- **Rebalancing:** monthly.

The 40% value is an instrument-level scaling parameter before diversification. It is not a portfolio volatility target. The baseline risk model is diagonal and assumes zero covariance between instruments.

This script also runs the existing strategy experiments:

- 1-, 3-, 6-, and 12-month momentum lookbacks.
- EWMA volatility with a six-month half-life.
- Equal risk budgets across asset classes.
- A signal averaging multiple momentum horizons.
- A combined EWMA, asset-class-budget, and multi-lookback strategy.

Results are written to `outputs/strategy_backtest_adj_output/`.

#### `rolling_backtest.py`

Provides a separate robustness backtest using compounded 12-month momentum and trailing 12-month volatility. It compares rolling and full-sample volatility estimates, keeps the TSMOM and static benchmark universes aligned, and tests transaction costs of 0, 5, 10, and 25 basis points per one-way change in target weight.

This script is independent of `strategy_backtest_adj.py` and writes to `outputs/rolling_backtest_output/`.

### 3. Test whether the signal predicts returns

#### `signal_diagnostics.py`

Tests the economic basis of the strategy before evaluating the complete portfolio:

- Return autocorrelation at lags 1–12.
- Absolute- and squared-return autocorrelation as measures of volatility persistence.
- Next-month returns following positive and negative momentum signals.
- Return spreads and directional hit rates for 1-, 3-, 6-, and 12-month lookbacks.
- Stability by instrument, asset class, and period.

Signals use only information available before the return being predicted. Newey–West HAC statistics are based on monthly aggregated signed returns. Results are written to `outputs/signal_diagnostics_output/`.

### 4. Establish the baseline performance record

#### `baseline_performance_analysis.py`

Produces the main performance analysis for the adjusted baseline and static benchmark:

- Cumulative and annualized performance, volatility, Sharpe ratio, and drawdowns.
- Rolling 12-, 36-, and 60-month performance.
- Turnover, signal changes, and transaction-cost sensitivity.
- Gross, net, long, and short exposure.
- Timing checks for the one-month execution lag.

This script is the single source for standardized baseline returns, instrument contributions, executed weights, volatility estimates, exposures, turnover, rolling results, and drawdown events. These files are stored in `outputs/baseline_performance_output/` and are reused by the remaining analyses.

#### `baseline_output_loader.py`

Loads the standardized performance files for downstream scripts. It also converts execution-month weights back to formation-date alignment when the risk-validation analysis requires it.

### 5. Explain where the returns come from

#### `baseline_return_attribution.py`

Attributes baseline returns by instrument, asset class, long versus short positions, decade, major drawdown event, and S&P 500 futures proxy bull/bear regime.

A bear regime begins after an S&P 500 futures peak when the subsequent drawdown reaches 20% and continues through recovery. This is an internal futures-based proxy rather than an official cash-index classification. Results are written to `outputs/baseline_return_attribution_output/`.

### 6. Measure and validate baseline risk

#### `baseline_risk_analysis.py`

Uses the existing diagonal risk model to calculate variance contributions by instrument and asset class, risk concentration, and the effective number of risk positions. It does not add covariance or change the strategy weights. Results are written to `outputs/baseline_risk_analysis_output/`.

#### `validate_diagonal_risk_model.py`

Tests whether the diagonal model predicts subsequent portfolio risk. Formation-date predicted volatility is compared with fixed-weight realized volatility over the following 12 months, with a three-month robustness check. The analysis reports forecast bias, error, correlation, and exceedance frequency by period and asset class.

Results are written to `outputs/risk_model_validation_output/`.

### 7. Compare the baseline with benchmarks and factors

#### `generate_strategy_analysis.py`

Compares the baseline with:

- The always-long static futures benchmark over 1976–2014.
- SG Trend over the available 2000–2014 overlap.
- Six equity factors: Mkt-RF, SMB, HML, Mom, RMW, and CMA.

The analysis includes raw and volatility-matched performance, rolling statistics, drawdowns, correlation, tracking error, and HAC regressions. Volatility matching uses full-sample realized volatility and is descriptive rather than tradable. The equity factors are also an incomplete risk model for a diversified futures strategy.

Results are written to `outputs/strategy_analysis_output/`.

## Recommended run order

```bash
python analysis_eda.py
python strategy_backtest_adj.py
python signal_diagnostics.py
python baseline_performance_analysis.py
python baseline_return_attribution.py
python baseline_risk_analysis.py
python validate_diagonal_risk_model.py
python generate_strategy_analysis.py
```

Run `baseline_performance_analysis.py` before the attribution, risk, validation, and benchmark scripts because those analyses use its standardized outputs.

## Important assumptions and limitations

- Backtests use monthly data and rebalance monthly.
- Sharpe ratios generally use a zero risk-free rate unless an excess-return regression is explicitly reported.
- The baseline assumes zero covariance across instruments.
- The strategy has no explicit portfolio volatility target or leverage cap.
- Missing realized returns for held instruments are filled with zero.
- Transaction costs are illustrative and do not include contract-specific spreads, futures roll costs, financing, margin requirements, or liquidity constraints.
- SG Trend may use different instruments, fees, signals, and risk targets, so it is a comparator rather than an exact replication target.

## Planned enhancements

The main next steps are:

1. Add expanding, rolling, EWMA, and shrinkage covariance estimates.
2. Validate each risk model against subsequent realized volatility.
3. Add portfolio-level volatility targeting with leverage and scaling limits.
4. Improve asset-class risk diversification.
5. Evaluate the enhanced strategies with walk-forward tests and more realistic transaction costs.
