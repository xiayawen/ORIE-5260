# ORIE 5260 Futures Momentum Project

## Project overview

This project studies time-series momentum (TSMOM) across a diversified futures universe. The work has three stages:

1. **Understand and validate the data** through exploratory data analysis.
2. **Construct two baseline versions**: the course PPT / adjusted baseline (`strategy_backtest_adj.py`) and the rolling baseline (`rolling_backtest.py`).
3. **Evaluate the strategies** through performance and costs, then use the adjusted baseline for the standardized signal, attribution, risk-validation, and SG Trend analysis pipeline.

The repository includes both baseline backtests, the adjusted-baseline analysis pipeline, and four completed enhancement experiments (E1–E4). The next stage is covariance-aware risk estimation, portfolio-level volatility targeting, and walk-forward evaluation.

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

**The two project baselines are `strategy_backtest_adj.py` and `rolling_backtest.py`.**

| Design | Course PPT / adjusted baseline | Rolling baseline |
| --- | --- | --- |
| Script | `strategy_backtest_adj.py` | `rolling_backtest.py` |
| Signal | Sign of summed trailing 12 monthly returns | Sign of compounded trailing 12-month returns |
| Instrument volatility | Expanding history; at least 36 valid months | Trailing 12 months; valid consecutive window |
| Main evaluation | January 1976–December 2014 | February 1970–December 2014 |
| Gross TSMOM CAGR / Sharpe | 10.64% / 0.97 | 19.12% / 1.06 |
| Correlation with own static | 0.080 | 0.385 |

Both use historical inputs at formation, execute weights in the following month, compound portfolio wealth, and use annualized arithmetic mean divided by annualized volatility for zero-RF Sharpe. Both have their own always-long static benchmark. Signal aggregation, volatility estimation, eligibility, and evaluation samples differ; these figures do not isolate the effect of a single design choice. SG Trend is a separate external comparator.

#### `strategy_backtest_adj.py`

Implements baseline A, following the course PPT approach:

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
- Equal allocation across valid asset classes, with equal allocation within each class. This does not solve covariance-aware equal risk contributions.
- A signal averaging multiple momentum horizons.
- A combined EWMA, asset-class-budget, and multi-lookback strategy.

Results are written to `outputs/strategy_backtest_adj_output/`.

#### `rolling_backtest.py`

Implements baseline B using compounded 12-month momentum and trailing 12-month volatility. TSMOM and static use the same eligible universe. It tests costs of 0, 5, 10, and 25 basis points per one-way weight change and reports cumulative performance, turnover, missing-held-return diagnostics, peak gross exposure, static correlation, HAC static-return regressions, and six-factor excess-return regressions.

The rolling baseline record uses the `rolling_tsmom` and `rolling_static` rows and corresponding monthly-return columns. Other diagnostic comparisons produced by this script are not additional project baselines.

This script does not use the adjusted-baseline output pipeline and writes to `outputs/rolling_backtest_output/`. It imports shared data and signal helpers from the retained `strategy_backtest.py` module; that module is a code dependency, not one of the two project baselines.

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

This script is the single source for standardized **adjusted-baseline** returns, instrument contributions, executed weights, volatility estimates, exposures, turnover, rolling results, and drawdown events. These files are stored in `outputs/baseline_performance_output/` and are reused by the remaining analyses.

#### `baseline_output_loader.py`

Loads the standardized performance files for downstream scripts. It also converts execution-month weights back to formation-date alignment when the risk-validation analysis requires it.

### 5. Explain where the returns come from

#### `baseline_return_attribution.py`

Attributes baseline returns by instrument, asset class, long versus short positions, decade, major drawdown event, and S&P 500 futures proxy bull/bear regime.

Regimes use compounded SP futures proxy wealth. For a peak-to-recovery episode reaching a drawdown of at least 20%, all months after the peak through recovery are retrospectively labeled Bear. Unrecovered episodes continue to sample end; other observed months are Bull. Recovery means wealth reaches or exceeds the prior peak. This is an ex-post internal futures proxy, not an official cash-index classification or a live trading signal. Results are written to `outputs/baseline_return_attribution_output/`.

### 6. Measure and validate baseline risk

#### `baseline_risk_analysis.py`

Uses the existing diagonal risk model to calculate variance contributions by instrument and asset class, risk concentration, and the effective number of risk positions. It does not add covariance or change the strategy weights. Results are written to `outputs/baseline_risk_analysis_output/`.

#### `validate_diagonal_risk_model.py`

Tests whether the diagonal model predicts subsequent portfolio risk. Formation-date predicted volatility is compared with fixed-weight realized volatility over the following 12 months, with a three-month robustness check. Monthly forecasts are saved, and the analysis reports bias, MAE, RMSE, correlation, and exceedance frequency by period and asset class. High-volatility evaluation labels use the upper quintile of subsequent fixed-weight realized volatility; these are ex-post labels. Exceedance means realized risk exceeds the model prediction, not an intended portfolio target, since no portfolio target is implemented. Repeat this validation for each future enhanced risk model.

Results are written to `outputs/risk_model_validation_output/`.

#### `covariance_risk_validation.py`

Compares the existing diagonal forecast with expanding covariance, six-month
half-life EWMA covariance, and fixed 50% shrinkage toward the expanding diagonal.
Uses unchanged adjusted-baseline weights and identical evaluation dates within
each 3- or 12-month horizon. Pairwise missing-history estimates require 36
overlapping months for correlations, with zero-correlation fallback and PSD
correlation repair. No portfolio volatility targeting is applied. EWMA changes
both marginal variances and correlations. Results are descriptive, with overlapping
forward windows; parameters are fixed rather than optimized on these results.

Run after `baseline_performance_analysis.py`. Forecasts, overall and decade-level
accuracy, matrix diagnostics, a comparison plot, and methodology are written to
`outputs/covariance_risk_validation_output/`.

#### `portfolio_volatility_targeting.py`

Compares unchanged baseline weights with portfolio targeting under all four risk
models. Fixed parameters are a 10% annual portfolio volatility target, 4x gross
exposure cap, and 2x maximum multiplier on baseline weights. Formation-date risk
forecasts scale next-month positions. Reports 0/5/10/25 bps costs, rolling realized
risk, exposure, binding limits, executed weights, and descriptive subperiods.
No performance-based parameter fitting or untouched holdout claim is made.

Includes a cap-only control that proportionally reduces baseline positions above
4x gross exposure without forecasting risk or amplifying positions. The cap
ablation report and differences table distinguish the cap effect from additional
dynamic targeting and compare risk models under common targeting rules.

Run after `baseline_performance_analysis.py`; covariance forecasts are recomputed
using full formation-date history. Results go to
`outputs/portfolio_volatility_targeting_output/`. Synthetic timing and limit
checks: `python -m unittest test_portfolio_volatility_targeting.py`.

### 7. Compare the baseline with benchmarks and factors

#### `generate_strategy_analysis.py`

Compares the **adjusted baseline** with:

- The always-long static futures benchmark over 1976–2014.
- SG Trend over the available 2000–2014 overlap.
- Six equity factors: Mkt-RF, SMB, HML, Mom, RMW, and CMA.

The analysis includes raw and volatility-matched performance, rolling statistics, drawdowns, correlation, tracking error, and HAC regressions. Volatility matching uses full-sample realized volatility and is descriptive rather than tradable. The equity factors are also an incomplete risk model for a diversified futures strategy.

Results are written to `outputs/strategy_analysis_output/`.

## Recommended run order

```bash
python analysis_eda.py
python strategy_backtest_adj.py
python rolling_backtest.py
python signal_diagnostics.py
python baseline_performance_analysis.py
python baseline_return_attribution.py
python baseline_risk_analysis.py
python validate_diagonal_risk_model.py
python covariance_risk_validation.py
python portfolio_volatility_targeting.py
python generate_strategy_analysis.py
```

`rolling_backtest.py` can run separately and does not require the adjusted performance outputs.

Run `baseline_performance_analysis.py` before the attribution, risk, validation, and benchmark scripts because those analyses use its standardized outputs.

## Important assumptions and limitations

- Backtests use monthly data and rebalance monthly.
- Sharpe ratios generally use a zero risk-free rate unless an excess-return regression is explicitly reported.
- The adjusted baseline risk analysis assumes zero covariance across instruments; neither baseline uses covariance-aware position construction.
- Neither baseline has an explicit portfolio volatility target, leverage cap, or volatility floor. Rolling peak gross exposure is approximately 29.75, versus 4.60 for adjusted; compare implementation risk as well as headline Sharpe.
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

## Coverage and scope

The scripts cover return and volatility autocorrelation at lags 1–12; signal predictiveness across horizons, instruments, classes, and periods; cumulative and rolling performance; drawdown depth and recovery; exposure and trading costs; return attribution by market, class, direction, decade, regime, and drawdown event; diagonal risk concentration; future-risk validation; and static / SG Trend / factor comparisons.

Detailed return attribution, diagonal risk validation, and SG Trend results use the standardized adjusted-baseline outputs. They have not all been repeated for the rolling baseline. Rolling has its own performance, cost, static-correlation, diagnostics, and regression outputs. Completed E1–E4 experiments should be distinguished from planned full-covariance, portfolio-targeting, and walk-forward enhancements.

## Dependencies

Use Python with `numpy`, `pandas`, `matplotlib`, `scipy`, `statsmodels`, and `openpyxl` available. Run commands from the project root so the supplied data files and output folders resolve correctly.
