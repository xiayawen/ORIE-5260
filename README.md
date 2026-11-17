# Daily futures trend portfolio: final submission

This repository contains the course time-series momentum baseline and one selected enhancement: a four-sleeve futures portfolio whose **price-trend signal uses daily data**. The project asks whether adding economic, cross-sectional and machine-learning information, together with a common risk and execution model, improves the baseline's risk-adjusted outcomes. It is the final submission for the enhancement phase of ORIE 5260; the earlier EDA and baseline diagnostics remain in the project's research history.

The main comparison covers **58 futures markets** from January 1976 to May 2025. Positions are reconsidered every **21 business days** and returns are marked daily. The macro, negative-skew and Extra Trees sleeves use information available at the latest month-end; no later month-end value is backfilled into an earlier decision.

## Start here

1. Install the packages in `requirements.txt`.
2. Run `python daily_baseline.py` to rebuild the course baseline.
3. Run `python run_final_strategy.py` to rebuild the selected four-sleeve portfolio.
4. Run `python compare_baseline.py` for the matched 21-day IS/OOS comparison and figure.
5. Read [the final report](report.md) for methods, results and limitations.

All source data needed for these commands are in `data/`. They include the full-sample monthly workbook, the asset map, three FRED series plus the credit-spread series, and the archive of daily back-adjusted futures closes. The baseline also evaluates a 66-market universe as a robustness check; the primary report comparison uses the same 58 markets for both strategies.

## Repository guide

| File or folder | Purpose |
|---|---|
| `daily_baseline.py` | Minxi-Lin's Lecture 11 daily baseline from commit [`5838b70`](https://github.com/xiayawen/ORIE-5260/commit/5838b706cf5b71a1926424fd4751fec679e9af94). Only its input/output paths were adapted to this layout. |
| `price_trend.py` | 252-day compounded-return direction and 252-day instrument volatility for the price-trend sleeve. |
| `macro_trend.py` | Five economic themes mapped to futures positions with dated release assumptions. |
| `negative_skew.py` | Within-asset-class ranking of trailing 12-month negative skewness. |
| `extra_trees.py` | Exact 66-feature Extra Trees classifier, with chronological pre-2005 and pre-2015 fits and a training audit. |
| `risk_model.py` | Six-month EWMA monthly volatility for non-price sleeves, the 252-day sample covariance used in the final portfolio, and shared portfolio limits. |
| `portfolio_engine.py` | Common risk scaling and constrained cost-aware path to target weights. |
| `costs_and_execution.py` | Actual trading and roll cost convention; daily mark-to-market after formation-close trading. |
| `data_utils.py` | Source loading, common instrument list and 21-business-day calendar. |
| `run_final_strategy.py` | Combines the four sleeves at fixed 30%/20%/20%/30% signal budgets and saves weights, returns and daily statistics. |
| `compare_baseline.py` | Aligns both strategies on the same 21-day period endpoints and saves the report comparison. |
| `outputs/baseline/` | Baseline series, summary and anchor-grid sensitivity. |
| `outputs/final_strategy/` | Selected strategy's daily returns, weights, model-fitting audit and statistics. |
| `outputs/comparison/` | Matched-period returns, IS/OOS table and comparison figure. |
| `tests/` | Checks formation timing and portfolio constraints. |

The final portfolio has an annual ex-ante volatility ceiling of 10%, gross exposure at most 4×, absolute net exposure at most 1×, and a 5% standalone volatility ceiling per asset class. It uses a 252-day sample covariance at each formation date. The selected cost convention is **2 basis points per unit traded plus four rolls per year at 2 basis points**; a fixed cost-aware execution parameter γ=5 moderates trading. The baseline uses an 11% ex-ante volatility target and does not impose the portfolio's exposure or asset-class limits. These differences are part of the enhancement and matter when interpreting returns.

## Evaluation and interpretation

The main table compares January 1976–December 2014 with January 2015–May 2025. Within the earlier interval, 2005–2009 was used for development and 2010–2014 for validation. Extra Trees supplies live out-of-training predictions from 2005; its initial pre-2005 years contribute no active ML sleeve and the absent sleeve budget returns to trend. The model is refitted before 2015 using only earlier labels and then frozen.

The later interval is a **chronological evaluation**, but the wider team has inspected it during development. It should not be presented as a pristine, never-seen holdout. Annual returns, volatility, Sharpe and drawdowns in `outputs/comparison/` use identical 21-day period endpoints; the final strategy also reports a separate daily-marked drawdown. The baseline's available drawdown is measured only at 21-day endpoints.

For a quick verification, run `python -m unittest discover -s tests`. The modular final implementation was reconciled to the research implementation: all 12,916 common daily net returns matched exactly in the development worktree. The 58-market baseline statistics also matched the source commit's generated results.
