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

The final construction stage was chosen because it had the highest 1976–2014 Sharpe ratio among the stages in the appendix (1.285, against 1.222 for the trend sleeve alone). That choice was made after the 2015–2025 results of every stage had been seen.

## Evaluation and interpretation

The main table compares January 1976–December 2014 with January 2015–May 2025. Within the earlier interval, 2005–2009 was used for development and 2010–2014 for validation. Extra Trees supplies live out-of-training predictions from 2005; its initial pre-2005 years contribute no active ML sleeve and the absent sleeve budget returns to trend. The model is refitted before 2015 using only earlier labels and then frozen.

The later interval is a **chronological evaluation**, but the wider team has inspected it during development. It should not be presented as a pristine, never-seen holdout. Annual returns, volatility, Sharpe and drawdowns in `outputs/comparison/` use identical 21-day period endpoints; the final strategy also reports a separate daily-marked drawdown. The baseline's available drawdown is measured only at 21-day endpoints.

For a quick verification, run `python -m unittest discover -s tests`. The capped γ=5 variant (appendix step 4) was reconciled to the research implementation: all 12,916 common daily net returns matched exactly in the development worktree, and it is reproduced unchanged by `decompose_steps.py` and `exposure_sensitivity.py`. The 58-market baseline statistics also matched the source commit's generated results.
