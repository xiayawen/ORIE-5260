# Daily futures trend portfolio: final submission

This repository contains the course time-series momentum baseline and one selected enhancement: a four-sleeve futures portfolio whose **price-trend signal uses daily data**. The project asks whether adding economic, cross-sectional and machine-learning information, combined under a common covariance risk model, improves the baseline's risk-adjusted outcomes. It is the final submission for the enhancement phase of ORIE 5260; the earlier EDA and baseline diagnostics remain in the project's research history.

The main comparison covers **58 futures markets** from January 1976 to May 2025. Positions are reconsidered every **21 business days** and returns are marked daily. The macro, negative-skew and Extra Trees sleeves use information available at the latest month-end; no later month-end value is backfilled into an earlier decision.

## Start here

1. Install the packages in `requirements.txt`.
2. Run `python daily_baseline.py` to rebuild the course baseline.
3. Run `python run_final_strategy.py` to rebuild the selected four-sleeve portfolio.
4. Run `python compare_baseline.py` for the matched 21-day IS/OOS comparison and figure.
5. Run `python decompose_steps.py` for the construction stages in the report appendix (exposure limits and cost-aware execution).
6. Run `python exposure_sensitivity.py` for the appendix gross and net exposure-limit check of the capped variant.
7. Read [the final report](report.md) for methods, results and limitations.

All source data needed for these commands are in `data/`. They include the full-sample monthly workbook, the asset map, three FRED series plus the credit-spread series, and the archive of daily back-adjusted futures closes. The baseline also evaluates a 66-market universe as a robustness check; the primary report comparison uses the same 58 markets for both strategies.

## Repository guide

| File or folder | Purpose |
|---|---|
| `daily_baseline.py` | Minxi-Lin's Lecture 11 daily baseline from commit [`5838b70`](https://github.com/xiayawen/ORIE-5260/commit/5838b706cf5b71a1926424fd4751fec679e9af94), with local data paths and inspectable signal outputs. It constructs the 252-day direction, instrument volatility and portfolio weights directly from daily returns. |
| `price_trend.py` | 252-day compounded-return direction and 252-day instrument volatility for the price-trend sleeve. |
| `macro_trend.py` | Five economic themes mapped to futures positions with dated release assumptions. |
| `negative_skew.py` | Within-asset-class ranking of trailing 12-month negative skewness. |
| `extra_trees.py` | Exact 66-feature Extra Trees classifier, with chronological pre-2005 and pre-2015 fits and a training audit. |
| `risk_model.py` | Six-month EWMA monthly volatility for non-price sleeves, the 252-day sample covariance used in the final portfolio, and shared portfolio limits. |
| `portfolio_engine.py` | Risk scaling to the 10% ex-ante target; the exposure limits and cost-aware path used by the appendix variants. |
| `costs_and_execution.py` | Actual trading and roll cost convention; daily mark-to-market after formation-close trading; γ=5 execution for the appendix variant. |
| `data_utils.py` | Source loading, common instrument list and 21-business-day calendar. |
| `run_final_strategy.py` | Combines the four sleeves at fixed 30%/20%/20%/30% signal budgets, scales the book to 10% ex-ante volatility, fully rebalances, and saves weights, returns and daily statistics. `build_portfolio_inputs()` is shared with the appendix scripts. |
| `compare_baseline.py` | Aligns both strategies on the same 21-day period endpoints and saves performance, wealth and drawdown comparisons. |
| `decompose_steps.py` | Appendix A: trend sleeve alone, the selected blend, the blend with the four exposure limits, and with γ=5 cost-aware execution, on the same 21-day endpoints. |
| `exposure_sensitivity.py` | Appendix B: replays the capped γ=5 variant with gross and net limits removed separately and together, plus a gross-matched control. |
| `outputs/baseline/` | Baseline signals, volatility estimates, raw and final formation weights, return series, summary and anchor-grid sensitivity. |
| `outputs/final_strategy/` | Selected strategy's daily returns, weights, model-fitting audit and statistics. |
| `outputs/comparison/` | Matched-period returns, IS/OOS table, wealth figure and drawdown figure. |
| `outputs/decomposition/` | Construction-stage table (CSV and Markdown) for Appendix A. |
| `outputs/exposure_sensitivity/` | Appendix B: exposure-limit performance of the capped variant, target-change frequencies, formation exposures, daily returns and later-period drawdown figure. |
| `tests/` | Checks formation timing, the 10% ex-ante scaling and the appendix portfolio constraints. |

The final portfolio is scaled at every formation to **10% ex-ante annual volatility** using a 252-day sample covariance, with **no gross, net or asset-class exposure caps**, and trades fully to its target every 21 business days. The cost convention is **2 basis points per unit traded plus four rolls per year at 2 basis points**. The baseline is built the same way from the price-trend sleeve alone, with an 11% ex-ante target. Without caps, both strategies run high leverage in low-volatility rate futures after 2015 (about 11× gross); the final portfolio's average net long is about 6.7× NAV. The report appendix shows the variant with a 10% volatility ceiling, 4× gross, 1× net and 5% per-class limits, with and without γ=5 cost-aware execution.

## Evaluation and interpretation

The main table compares January 1976–December 2014 with January 2015–May 2025. Within the earlier interval, 2005–2009 was used for development and 2010–2014 for validation. Extra Trees supplies live out-of-training predictions from 2005; its initial pre-2005 years contribute no active ML sleeve and the absent sleeve budget returns to trend. The model is refitted before 2015 using only earlier labels and then frozen.

For a quick verification, run `python -m unittest discover -s tests`. The capped γ=5 variant (appendix step 4) was reconciled to the research implementation: all 12,916 common daily net returns matched exactly in the development worktree, and it is reproduced unchanged by `decompose_steps.py` and `exposure_sensitivity.py`. The 58-market baseline statistics also matched the source commit's generated results.

## Research extension: train four-sleeve budgets

`python optimize_daily_budgets.py` fits nonnegative bounded sleeve budgets with a return/risk/cost objective, validates six settings before 2015 and evaluates frozen weights with the same daily full-rebalance engine. This is a separate research experiment; it does not change the selected submission. Fixed budgets won the validation comparison. See [DAILY_BUDGET_OPTIMIZATION_REPORT.md](DAILY_BUDGET_OPTIMIZATION_REPORT.md) and `outputs/daily_budget_optimization/`.

## Research diagnostic: final ET66 feature IC

`python factor_ic_analysis.py` reports monthly next-return Rank/Pearson IC for all 66 model inputs and the frozen model probabilities. It separates raw factors, within-class rank transforms and class controls; no factor is selected or sign-flipped using later IC. See [FACTOR_IC_REPORT.md](FACTOR_IC_REPORT.md) and `outputs/factor_ic/`.

## Pre-2015-only IC feature screening

`python backtest_ic_filter.py` screens numeric ET66 inputs using absolute mean training Rank IC >=0.01. It screens before2005, validates frozen predictions in2005–2014, then re-screens/refits before2015 and saves a frozen model. It does not calculate post2014 performance and does not change the submitted strategy. See [IC_FEATURE_FILTER_REPORT.md](IC_FEATURE_FILTER_REPORT.md).

`python evaluate_ic_filter_oos.py` is the separately authorized later evaluation of the already frozen IC rules: it distinguishes a fixed56-input list from the pre2015 re-screened55-input list. See [IC_FILTER_OOS_REPORT.md](IC_FILTER_OOS_REPORT.md). No later IC is used for screening.

## Research diagnostic: IC plus HAC t-stat screening

`python backtest_ic_t_filter.py` adds a pre-announced direction-consistent |HAC t-stat|>=1.96 requirement to |mean monthly Rank IC|>=0.01, with six Newey–West lags. Features are screened before2005, validated2005–2014, and models refitted/frozen before2015. See [IC_T_FILTER_REPORT.md](IC_T_FILTER_REPORT.md). It compares fixed42 and pre2015 re-screened38 input policies without changing the submitted strategy.

## Fixed42 portfolio budgets and execution

`python optimize_ict42_portfolio.py` compares fixed vs learned signal budgets and full vs cost-aware execution with the already frozen42-input ET model. It selects utility/execution settings before2015, retains the original as an incumbent and does not add gross/net/class caps. See [ICT42_PORTFOLIO_OPTIMIZATION_REPORT.md](ICT42_PORTFOLIO_OPTIMIZATION_REPORT.md) for the staged method and results.
