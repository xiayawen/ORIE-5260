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
- `MonthlyReturns_FullSample.xlsx`: monthly returns for the same 58 markets from February 1969 to May 2025. On 1969–2014 it matches `MonthlyReturns.csv` except six December 2014 cells that are now filled. Used by the Part 2 §8–§12 in-sample / out-of-sample analysis.

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

Uses the diagonal baseline model to calculate variance contributions, risk concentration, and the effective number of risk positions. It does not alter strategy weights. Results are written to `outputs/baseline_risk_analysis_output/`. The covariance-based decomposition added later is described in Part 2, §9.

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

Part 2 begins with the October 27 commit `24949b5`. Each subsection below describes an enhancement that has been implemented in code.

### Data periods used by each enhancement

The table distinguishes **in-sample (IS) design/training**, **validation**, and **out-of-sample (OOS) or later-period evaluation**. “No separate validation” means that the enhancement was examined on the same period used for its design; subperiod tables within that sample are robustness descriptions rather than a held-out validation exercise. Pre-1976 observations are used only to initialize momentum, volatility, and covariance estimates where needed, not to calculate reported strategy performance.

| Part 2 enhancement | IS design or training period | Separate validation period | OOS or later-period evaluation |
| --- | --- | --- | --- |
| §1 Covariance-aware risk forecasting | January 1976–December 2014. Covariances are re-estimated causally using information available at each formation date. | No separate validation. The three- and 12-month subsequent-volatility tests are forecast evaluation inside the same 1976–2014 research sample. | None in `covariance_risk_validation.py`. |
| §2 Portfolio volatility targeting and gross cap | January 1976–December 2014. The 10% target, 4x gross cap, and 2x scaling cap are evaluated on this period. | No separate validation. The 1976–1999 and 2000–2014 results are descriptive stability checks. | January 2015–May 2025 is later evaluated for the EWMA-covariance-target specification through §10. |
| §3 EWMA-enhanced strategy and detailed costs | January 1976–December 2014. The EWMA volatility, covariance targeting, combined strategy, and cost comparisons are developed and compared here. | No separate validation. The 1976–1999 and 2000–2014 splits are descriptive. | January 2015–May 2025 is later evaluated for the combined enhanced strategy through §10. |
| §4 Rebalance frequency | January 1976–December 2014. Monthly, weekly, and daily schedules are compared here. | No separate validation. The 1976–1989, 1990–1999, and 2000–2014 results are descriptive. | January 2015–May 2025 in `rebalance_frequency_out_of_sample.py`. The original frequency comparison is a later-period test; the half-short overlay is exploratory because it was chosen after examining the later data. |
| §5 Fixed net- and gross-exposure controls | January 1976–December 2014. The 4x gross cap and ±1x net cap are first tested here. | No separate validation. | January 2015–May 2025 in `net_exposure_out_of_sample.py`, using the shared later-period price-trend baseline described in §7. |
| §6 Economic-trend strategy | January 1980–December 1997 is used to select signal form, trade-theme sign, smoothing, class balancing, and blend weight. | January 1998–December 2014, with choices locked from the training period. | None completed because the required macro inputs and generated results are not committed. |
| §7 Exposure smoothing | January 2015–May 2025 is used to develop and evaluate the smoothing rules. | None. | No clean OOS period. The reported later-sample result is exploratory because that same period informed the rule. |
| §7 Short-budget rule | January 2015–May 2025 is used to compare short budgets and select the 50% short allocation. | No clean validation. The 1980–1997 and 1998–2014 tables are reverse-time historical robustness checks performed after selecting the rule. | No clean OOS period; January 2015–May 2025 is the selection sample, despite being later than the original baseline cutoff. |
| §8 Monthly full-sample and look-ahead framework | January 1976–December 2014 is the common design/IS period for §8–§11. | The truncation dates June 1990, December 2014, and March 2020 are causal reproducibility tests, not validation samples. | January 2015–May 2025 is the common later evaluation period. |
| §9 Covariance risk decomposition (R1) | January 1976–December 2014 diagnostic analysis. It changes the measurement of risk, not the strategy weights. | No separate validation. | None reported for the decomposition itself. |
| §10 Hierarchical risk budgeting (R2) | January 1976–December 2014. Risk budgets, covariance choice, volatility target, and leverage cap are fixed from this research period. | No separate validation. | January 2015–May 2025, with no re-selection on that period. |
| §11 No-trade band (T1) | January 1976–December 2014. `band_25` is selected using IS turnover and net-Sharpe comparisons only. | No separate validation. | January 2015–May 2025, excluded from rule selection. |
| §12 Execution timing and alpha decay (T3) | January 1976–December 2014 using the original daily files. | No separate validation. | None; the implemented execution-timing study stops in December 2014. |

The January 2015–May 2025 period is strategy-specific OOS for rules fixed before that period was examined. It is not a pristine repository-wide holdout because other project work had already analyzed those dates. Exposure smoothing, the short-budget rule, and the half-short frequency overlay should therefore be treated as exploratory rather than OOS evidence.

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

## 8. Monthly full-sample extension and look-ahead test

`risk_budgeting.read_full_sample_returns()` loads `MonthlyReturns_FullSample.xlsx`. Sections 8–12 use one convention:

- **In-sample (IS):** January 1976–December 2014. All design and parameter choices were made on this period.
- **Out-of-sample (OOS):** January 2015–May 2025 (125 months), evaluation only. Nothing is re-estimated or re-selected; expanding estimates continue month by month.
- **Costs:** Lecture 8 model (`transaction_cost_model.py`) at $1 billion AUM.

This monthly extension differs from §7, which uses the daily `*_RAD.CSV` closes and a different shared baseline (trailing 12-month volatility with a 1% floor), so results are not directly comparable across the two sections.

### `test_lookahead.py`

Reruns the strategies on data truncated at June 1990, December 2014, and March 2020 and checks that every weight, volatility estimate, Lecture 8 cost, and no-trade-band holding path formed before each cut is identical to the full-sample run. It also checks the one-month execution lag. Run with `python -m unittest test_lookahead.py`.

## 9. Covariance risk decomposition (R1)

`baseline_risk_analysis.py` now also decomposes the adjusted baseline with EWMA (six-month half-life) and expanding covariance forecasts using the Euler decomposition (MCR = Σw/σ, CR = w × MCR, PCR = CR/σ; `risk_budgeting.euler_decomposition`). The diagonal outputs are unchanged.

Over 1976–2014, the diagonal model predicts 6.8% portfolio volatility against 10.6% with EWMA covariance and 11.1% realized. With correlations included, commodities carry 53% of risk instead of 63%, equities 16% instead of 10%, and the effective number of independent instrument bets falls from about 40 to 17. Outputs: `diagonal_vs_covariance_class_risk.csv/.png` and `covariance_*` files in `outputs/baseline_risk_analysis_output/`.

## 10. Hierarchical risk budgeting (R2)

### `risk_budgeting.py` and `risk_budget_backtest.py`

Each month, signs come from the 12-month signal and position sizes solve the Spinu convex risk-budgeting problem, so that every active asset class carries 1/K of ex-ante risk (25% when all four trade), split equally inside the class. The covariance is six-month EWMA. The portfolio is scaled to 10% predicted volatility, and gross exposure above 4x is cut proportionally. The script compares R2 with the baseline, E1, E3, covariance targeting, enhanced, and static strategies in-sample and out-of-sample.

R2 equalizes ex-ante risk (OOS shares 25/25/25/25) and has the smallest in-sample drawdown, but the 4x cap binds in 75% of months and turnover is 26–34x a year. Net Sharpe at $1 billion is 0.77 IS and -0.10 OOS, versus 1.02 and -0.01 for enhanced. Results and the repository-wide look-ahead audit are in `outputs/risk_budget_output/risk_budget_report.md`.

## 11. No-trade band (T1)

### `cost_aware_rebalance.py`

Simulates path-dependent holdings: each month, a drifted weight is traded only if it lies outside ±25% of the absolute target weight (`band_25`), and then only to the band edge. Sign flips, entries, and exits are always executed. The script also reports band_10 and partial-rebalancing variants and full metrics for every strategy in-sample, out-of-sample, and over the full sample.

band_25 cuts in-sample turnover by 30–40% (enhanced 9.6x to 6.1x). In-sample net Sharpe is roughly unchanged for the 1/N and enhanced variants and rises for R2 (0.77 to 0.91). Enhanced + band_25 is the final configuration: net Sharpe 1.03 IS and 0.11 OOS, maximum drawdown -12.9% IS and -10.8% OOS. Results are in `outputs/cost_aware_rebalance_output/`.

## 12. Execution timing on daily data (T3)

### `alpha_decay_execution.py`

Rebuilds the band_25 baseline, enhanced, and R2 portfolios on daily closes (1976–2014) and measures gross Sharpe by execution delay and net Sharpe by execution horizon at $100 million, $1 billion, and $10 billion. Alpha decays by about 0.05–0.06 Sharpe on the first day and about 0.01 per day afterwards. Starting the day after formation with the best horizon at $1 billion lowers in-sample net Sharpe from 0.85 to 0.76 (baseline), 1.03 to 0.95 (enhanced), and 0.91 to 0.84 (R2). Results are in `outputs/alpha_decay_output/`.

### `risk_tcost_summary.py`

Summarizes the risk-decomposition, risk-budgeting and transaction-cost work (§9–§12): an IS/OOS metric table for Baseline, Enhanced and R2 with and without the band_25 no-trade band (`summary_metrics.md/.csv`) and a six-panel figure (`risk_tcost_summary.png`) in `outputs/risk_tcost_summary_output/`.

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

With `MonthlyReturns_FullSample.xlsx` in the project root, reproduce §8–§12 with:

```bash
python baseline_risk_analysis.py   # requires baseline_performance_analysis.py outputs
python risk_budget_backtest.py
python cost_aware_rebalance.py
python alpha_decay_execution.py
python risk_tcost_summary.py
python -m unittest test_lookahead.py
```

## Important assumptions and limitations

- Execution timing (§8–§12): weights formed from month-t closes earn the whole month-t+1 return, so trades are assumed to fill at the same close used to compute the signal, while the Lecture 8 impact cost assumes 5-day execution. §12 shows a feasible schedule lowers in-sample net Sharpe by about 0.07–0.09; daily data end in 2014, so OOS figures cannot be adjusted directly. Treat these net Sharpe ratios as upper bounds by roughly this amount.
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
