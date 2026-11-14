# ORIE 5260 Futures Momentum Project

## Project overview

This project studies time-series momentum (TSMOM) across a diversified futures universe. The repository has two parts:

1. **Part 1 — EDA and baseline-strategy analysis:** all work completed before October 27, 2026. This part validates the data, constructs two baseline strategies, and analyzes their signals, performance, return sources, risks, and benchmark relationships.
2. **Part 2 — Strategy enhancements:** work beginning October 27, 2026. This part adds covariance-aware risk forecasts, portfolio volatility targeting, exposure controls, a fuller transaction-cost model, alternative rebalance frequencies, and an economic-trend extension.

The adjusted baseline is the common reference strategy for most attribution, risk-validation, and enhancement experiments. The rolling baseline has its own performance, cost, correlation, and regression analysis.

## Data

- `MonthlyReturns.csv`: monthly returns for 58 futures markets from January 1969 to December 2014.
- `AssetMapCsv.csv`: instrument names, currencies, and asset-class classifications.
- `FuturesUnderlyingData/`: daily price, volume, and open-interest files used for data validation, liquidity diagnostics, and daily-frequency experiments.
- `Lecture3_livedata.xlsx`: SG Trend, GSCI, risk-free rate, and Mkt-RF, SMB, HML, Mom, RMW, and CMA factor returns from January 2000 to December 2014.
- `macro_data/` (not committed): FRED-style CSV inputs expected by the economic-trend scripts, including `INDPRO.csv`, `CPIAUCSL.csv`, and `GS2.csv`; `BAA10Y.csv` is optional. The committed one-byte `macrodata` file is not used by the code.
- `FuturesUnderlyingData_FullSample/.../*_RAD.CSV` (not committed): uploaded continuous-futures closes used for the January 2015–May 2025 extension. The scripts accept another location through `--data-dir`.

The futures universe contains commodities, equity indices, fixed income, and FX. The return panel is unbalanced because instruments begin at different dates.

# Part 1 — EDA and baseline-strategy analysis

Part 1 contains the project through the final commit before October 27. Its purpose is to establish reliable data, define the baseline strategies, and understand their historical behavior before changing the models.

## 1. Data exploration and validation

### `analysis_eda.py`

Performs the initial data review:

- Summarizes coverage and return distributions by instrument and asset class.
- Measures missingness and flags unusually large monthly returns.
- Calculates the cross-market correlation matrix.
- Reconstructs monthly returns from daily closing prices and compares them with `MonthlyReturns.csv`.

Outliers are flagged for review rather than automatically removed. Results are written to `outputs/eda_output/`.

## 2. Baseline strategies

The project has two baseline specifications.

| Design | Adjusted/course baseline | Rolling baseline |
| --- | --- | --- |
| Script | `strategy_backtest_adj.py` | `rolling_backtest.py` |
| Signal | Sign of the sum of the previous 12 monthly returns | Sign of the compounded trailing 12-month return |
| Instrument volatility | Expanding history with at least 36 valid months | Trailing 12-month window |
| Main sample | January 1976–December 2014 | February 1970–December 2014 |
| Gross TSMOM CAGR / Sharpe | 10.64% / 0.97 | 19.12% / 1.06 |
| Correlation with its own static benchmark | 0.080 | 0.385 |

Both strategies use information available at formation and execute weights in the following month. Their signal definitions, volatility estimates, eligibility rules, and evaluation samples differ, so their results do not isolate a single design choice.

### `strategy_backtest_adj.py`

Implements the course-style adjusted baseline:

- Signal: sign of summed trailing returns.
- Risk estimate: expanding annualized instrument volatility.
- Position size: signal multiplied by `40% / instrument volatility`.
- Allocation: equal across eligible instruments.
- Rebalancing: monthly with a one-month execution lag.

The 40% parameter scales individual instruments before diversification; it is not a portfolio volatility target. The baseline risk model is diagonal and assumes zero covariance between instruments.

The script also evaluates the 1-, 3-, 6-, and 12-month lookbacks and the original E1–E4 variants involving EWMA volatility, equal asset-class allocation, multiple lookbacks, and their combination. Results are written to `outputs/strategy_backtest_adj_output/`.

### `rolling_backtest.py`

Implements the rolling baseline using compounded 12-month momentum and trailing 12-month volatility. It reports:

- Gross and net performance under 0, 5, 10, and 25 bps costs.
- Turnover, missing-held-return diagnostics, and gross exposure.
- Correlation and HAC regressions against its static benchmark.
- Six-factor excess-return regressions.

Results are written to `outputs/rolling_backtest_output/`. `strategy_backtest.py` supplies shared helpers for this script and is a dependency rather than a third project baseline.

## 3. Signal diagnostics

### `signal_diagnostics.py`

Tests whether past returns contain information about subsequent returns:

- Raw-return autocorrelation at lags 1–12.
- Absolute- and squared-return autocorrelation as measures of volatility persistence.
- Cross-sectional 95% Student-t intervals around mean autocorrelations.
- Next-month returns after positive and negative signals.
- Return spreads and directional hit rates for 1-, 3-, 6-, and 12-month signals.
- Stability by instrument, asset class, and period.

Signals use only information available before the return being predicted. Newey–West HAC statistics use monthly aggregated signed returns. Results are written to `outputs/signal_diagnostics_output/`.

## 4. Standardized adjusted-baseline performance

### `baseline_performance_analysis.py`

Creates the standardized adjusted-baseline record used by later scripts:

- Cumulative and annualized performance, volatility, Sharpe ratio, and drawdowns.
- Rolling 12-, 36-, and 60-month statistics.
- Turnover and simple transaction-cost sensitivity.
- Gross, net, long, and short exposure.
- One-month execution-timing checks.

Outputs in `outputs/baseline_performance_output/` include returns, executed weights, instrument contributions, volatility estimates, exposures, turnover, and drawdown events.

### `baseline_output_loader.py`

Loads the standardized files for downstream attribution and risk analysis. It also converts execution-month weights to formation-date alignment when required.

## 5. Return attribution

### `baseline_return_attribution.py`

Attributes adjusted-baseline returns by:

- Instrument and asset class.
- Long and short positions.
- Decade and major drawdown event.
- S&P 500 futures proxy bull/bear regime.

A bear regime is a retrospectively identified peak-to-recovery episode that reaches a drawdown of at least 20%. It is an internal futures-based historical label rather than an official cash-index regime or real-time signal. Results are written to `outputs/baseline_return_attribution_output/`.

## 6. Baseline risk analysis and validation

### `baseline_risk_analysis.py`

Uses the diagonal baseline model to calculate variance contributions, risk concentration, and the effective number of risk positions. It does not alter strategy weights or add covariance. Results are written to `outputs/baseline_risk_analysis_output/`.

### `validate_diagonal_risk_model.py`

Compares formation-date predicted portfolio volatility with subsequent fixed-weight realized volatility over 12 months, with a three-month robustness check. It reports forecast bias, MAE, RMSE, correlation, and exceedance frequencies by period and asset class. Results are written to `outputs/risk_model_validation_output/`.

## 7. Benchmark and factor comparisons

### `generate_strategy_analysis.py`

Compares the adjusted baseline with:

- Its always-long static futures benchmark over 1976–2014.
- SG Trend over the 2000–2014 overlap.
- Mkt-RF, SMB, HML, Mom, RMW, and CMA factors.

The analysis includes raw and volatility-matched performance, rolling statistics, drawdowns, correlation, tracking error, and HAC regressions. Results are written to `outputs/strategy_analysis_output/`.

# Part 2 — Implemented strategy enhancements

Part 2 begins with the October 27 commit `24949b5`. Each subsection below describes an enhancement that has been implemented in code. All historical comparisons use an already studied sample and should be interpreted as descriptive rather than untouched out-of-sample evidence.

## 1. Covariance-aware risk forecasting

### `covariance_risk_validation.py`

Adds three covariance-aware forecasts while leaving the adjusted-baseline weights unchanged:

- Expanding sample covariance.
- EWMA covariance with a six-month half-life.
- Fixed 50% shrinkage toward the expanding diagonal matrix.

Pairwise correlations require 36 overlapping observations, otherwise fall back to zero. Correlation matrices are repaired to be positive semidefinite and then rescaled to preserve marginal variances. Forecasts are evaluated over identical three- and 12-month forward windows.

At the 12-month horizon, covariance-aware models reduce RMSE from 5.38% for the diagonal model to 3.75%–3.90%. Fixed shrinkage has the lowest MAE at 2.72%. Forecast tables, matrix diagnostics, methodology, and figures are written to `outputs/covariance_risk_validation_output/`.

## 2. Portfolio volatility targeting and gross-exposure control

### `portfolio_volatility_targeting.py`

Scales the adjusted-baseline positions using diagonal, expanding-covariance, EWMA-covariance, and shrunk-covariance forecasts. The implemented rules are:

- 10% annual portfolio volatility target.
- 4x gross-exposure cap.
- Maximum 2x multiplier on the original baseline weights.
- Formation-date forecasts applied to next-month positions.
- Costs of 0, 5, 10, and 25 bps per one-way target-weight change.

A cap-only control reduces positions above 4x gross exposure without forecasting risk or increasing exposure. This separates the cap effect from forecast-based scaling.

At 10 bps, EWMA-covariance targeting increases Sharpe from 0.903 to 0.965 and reduces maximum drawdown from -26.10% to -14.24%. The cap alone improves the drawdown to -24.25%, so it does not explain the full targeting result. Outputs are written to `outputs/portfolio_volatility_targeting_output/`.

Synthetic timing and limit tests are in `test_portfolio_volatility_targeting.py`. The initial covariance, targeting, and cap results are summarized in [the October 27 group update](outputs/portfolio_volatility_targeting_output/group_update_2026-10-27.md).

## 3. EWMA-enhanced strategy and detailed transaction costs

### `transaction_cost_model.py`

Implements the Lecture 8 futures-cost model with drift-adjusted turnover. It separates:

- Commission and exchange fees.
- Futures roll costs based on contract cycles.
- Margin financing when margin exceeds available equity.
- Asset-class half-spreads.
- Square-root market impact based on volatility, AUM, ADV, and execution days.

Liquidity uses class-level ADV assumptions with an illiquidity haircut when trailing contract volume is low. Parameters are fixed and illustrative rather than estimated from strategy performance.

### `enhanced_strategy_backtest.py`

Compares five strategies over January 1976–December 2014:

- `baseline`: expanding-volatility sizing without portfolio targeting.
- `ewma_vol`: six-month half-life EWMA instrument sizing.
- `ewma_cov_target`: baseline sizing plus EWMA-covariance targeting.
- `enhanced`: EWMA instrument sizing plus EWMA-covariance targeting.
- `static_bmk`: the always-long course benchmark.

It evaluates gross returns, flat 2/10 bps cases, and the detailed model at $100 million, $1 billion, and $10 billion AUM. It also reports capacity, cost components, asset-class costs, execution-horizon sensitivity, and ADV/volatility sensitivity.

At $1 billion under the detailed cost assumptions, the baseline has Sharpe 0.889 and maximum drawdown -26.23%; the combined enhanced strategy has Sharpe 1.021 and maximum drawdown -14.24%. Estimated annual costs are 87.9 and 90.2 bps, respectively. Outputs are written to `outputs/enhanced_strategy_output/`.

### `plot_cost_analysis.py`

Builds the cost-analysis summary figure from the enhanced-strategy outputs, including net Sharpe by cost case, capacity by AUM, asset-class costs, and input sensitivity.

Synthetic cost-model tests are in `test_transaction_cost_model.py`.

## 4. Rebalance-frequency enhancement

### `rebalance_frequency_backtest.py`

Uses reconstructed daily closes to compare monthly, weekly, and daily signal updates. All versions retain the adjusted baseline's 12-month momentum convention and expanding monthly volatility estimate. Positions drift between rebalances and orders execute at the next available close.

At 10 bps, weekly rebalancing has the strongest full-sample result. Daily rebalancing has the highest gross result but annual turnover of approximately 31.7x and deteriorates fastest as assumed costs increase. Outputs and a full methodology report are written to `outputs/rebalance_frequency_output/`.

## 5. Net- and gross-exposure controls

### `net_exposure_backtest.py`

Tests:

- The original adjusted baseline.
- A 4x gross-exposure cap.
- A symmetric ±1x net-exposure cap.
- Both limits together.
- Controls scaled to match the capped strategies' monthly gross exposure.

At 10 bps, the gross cap slightly improves Sharpe and drawdown. The net cap lowers return and produces worse drawdowns than its gross-exposure-matched controls, so the implemented net limit does not improve the historical risk-return tradeoff. Results are written to `outputs/net_exposure_output/`.

## 6. Economic-trend strategy code

### `economic_trend.py`

Implements five macro themes—growth, inflation, trade, monetary policy, and risk aversion—and maps them to directional futures exposures. It constructs price-trend, individual-theme, economic-trend, and blended portfolios. The current configuration includes:

- Trailing 12-month instrument volatility with a 1% floor.
- A 36-month realized-volatility scaling window.
- A 10% strategy volatility target.
- Three-month signal smoothing.
- A 20% economic-trend allocation in the blended strategy.
- A simple 2 bps turnover and roll-cost model.

### `economic_trend_validation.py`

Implements a 1980–1997 training period and a 1998–2014 validation period for signal form, trade-theme sign, smoothing, class balancing, and blend weights.

The code is committed, but the required `macro_data/` inputs and `outputs/economic_trend_output/` are not included in the repository. Therefore, this README reports the implemented methodology but does not report an economic-trend performance result.

## 7. Post-2014 exposure and rebalancing tests

The latest implementation extends the original universe with uploaded `*_RAD.CSV` continuous-futures closes. The common evaluation period is January 2015–May 2025, with pre-2015 history retained to initialize signals, volatility, and positions. These files are not committed, but the generated reports and output tables are included.

### `net_exposure_out_of_sample.py`

Repeats the gross- and net-exposure experiment on a shared price-trend baseline with a 12-month signal, trailing 12-month instrument volatility with a 1% floor, and a 10% portfolio target based on a 36-month window. It compares the 4x gross cap, ±1x net cap, their combination, and gross-matched controls.

The shared baseline has -0.42% net CAGR and -26.33% maximum drawdown. The gross cap reduces the drawdown to -21.32% with -0.47% net CAGR. The net cap performs worse than its matched-gross control, with -1.31% net CAGR and -30.65% drawdown. Outputs are in `outputs/net_exposure_out_of_sample_aligned/`; the earlier non-aligned run is retained in `outputs/net_exposure_out_of_sample/`.

### `exposure_smoothing_backtest.py`

Applies a trailing three-month average to gross leverage and, in the joint variant, to signed net exposure as a share of gross exposure. Joint smoothing produces 0.04% net CAGR and -24.95% drawdown versus -0.42% and -26.33% for the shared baseline, but raises annual turnover from 14.70x to 17.40x. Results are in `outputs/exposure_smoothing_output/`.

### `short_budget_backtest.py`

Keeps long positions unchanged and halves every short position. A matched control scales both sides proportionally to the same gross exposure. The half-short variant produces 0.88% net CAGR and -16.74% drawdown versus -0.15% and -21.53% for the matched control. Because the rule was selected after examining the 2015–2025 attribution, this is an exploratory result rather than a clean holdout test. Results are in `outputs/short_budget_output/`.

### `rebalance_frequency_out_of_sample.py`

Repeats the monthly, weekly, and daily execution experiment on the later sample and can apply the half-short rule with `--half-short`. Under the original weights, daily leads before costs, weekly leads at 5 and 10 bps, and monthly leads at 25 bps. At 10 bps all schedules have negative CAGR. With half-sized shorts, weekly earns 0.24% net CAGR at 5 bps, while all schedules remain negative at 10 bps. Results are in `outputs/rebalance_frequency_out_of_sample/` and `outputs/rebalance_frequency_half_short/`.

The consolidated methodology and interpretation are in [the post-2014 extension report](outputs/strategy_extensions_out_of_sample_report.md).

## Reproducible run order

### Part 1

```bash
python analysis_eda.py
python strategy_backtest_adj.py
python rolling_backtest.py
python signal_diagnostics.py
python baseline_performance_analysis.py
python baseline_return_attribution.py
python baseline_risk_analysis.py
python validate_diagonal_risk_model.py
python generate_strategy_analysis.py
```

`rolling_backtest.py` can run independently. Run `baseline_performance_analysis.py` before the adjusted-baseline attribution, risk, and benchmark scripts.

### Part 2

```bash
python covariance_risk_validation.py
python portfolio_volatility_targeting.py
python enhanced_strategy_backtest.py
python plot_cost_analysis.py
python rebalance_frequency_backtest.py
python net_exposure_backtest.py
python -m unittest test_portfolio_volatility_targeting.py
python -m unittest test_transaction_cost_model.py
```

The economic-trend scripts are excluded from the reproducible sequence because their macro input files are not committed.

With the uploaded `*_RAD.CSV` files available, reproduce the post-2014 experiments with:

```bash
python net_exposure_out_of_sample.py --data-dir <RAD-data-directory>
python exposure_smoothing_backtest.py --data-dir <RAD-data-directory>
python short_budget_backtest.py --data-dir <RAD-data-directory>
python rebalance_frequency_out_of_sample.py --data-dir <RAD-data-directory>
python rebalance_frequency_out_of_sample.py --half-short --data-dir <RAD-data-directory>
```

## Important assumptions and limitations

- The two baselines rebalance monthly. Weekly and daily rebalancing appear only in the frequency enhancement.
- Sharpe ratios generally assume a zero risk-free rate unless an excess-return regression is explicitly reported.
- The original adjusted baseline assumes zero cross-instrument covariance; covariance-aware construction appears only in Part 2.
- Neither original baseline has a portfolio volatility target, leverage cap, or volatility floor. These controls are Part 2 enhancements.
- Missing held-market returns are generally filled with zero. The daily-frequency experiment instead follows its documented marking and pending-order rules.
- Baseline costs use fixed bps-per-turnover approximations. The detailed Part 2 model adds roll, financing, spread, and market impact but still relies on class-level liquidity assumptions.
- SG Trend uses different instruments, fees, signals, and risk targets and is a comparator rather than a replication target.
- Newer scripts use pandas month-end aliases such as `ME`; use pandas 2.2 or later.
- The post-2014 files are external continuous-futures series. Overlap checks reproduce historical returns closely, but the repository does not independently validate their later contract construction or missing quotes.
- The post-2014 smoothing and half-short rules were developed after inspecting that period and are exploratory rather than untouched out-of-sample tests.

## Dependencies

Use Python with `numpy`, `pandas`, `matplotlib`, `scipy`, `statsmodels`, and `openpyxl`. Run commands from the project root so data and output paths resolve correctly.
