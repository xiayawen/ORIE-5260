# ORIE 5260: Final daily futures strategy

This submission compares the course's daily time-series momentum baseline with our **final 42-input, four-sleeve futures strategy** across 58 markets. Both portfolios target **11% annualized ex-ante volatility** and trade on a 21-business-day formation calendar. The four-sleeve strategy assigns signal budgets of 30% to daily price trend, 20% to economic trend, 20% to within-class negative skew, and 30% to a frozen Extra Trees forecast. There are no gross or net exposure caps. The [academic report](report.md) explains the design, evaluation, costs, and limitations.

On matched 21-day endpoints, the final strategy's net Sharpe is **1.283** for 1976–2014 and **0.356** for January 2015–May 2025, compared with **1.222** and **0.243** for the course baseline. The 2015–2025 period was inspected during research and is not a pristine holdout.

## Reproduce the comparison

Install [requirements.txt](requirements.txt), then run from the repository root:

```bash
python run.py baseline
python run.py selected42_target11
```

The baseline command creates the course return series in `outputs/baseline/`. The final-strategy command uses the frozen, chronologically generated 42-input probabilities in `data/frozen_selected42/` and writes its 11%-target tables, daily returns, and figures to [outputs/final_strategy/](outputs/final_strategy/). The saved probabilities define the evaluated strategy; the fixed input list and final fitted model are included for inspection. Refit results may vary slightly with software versions.

## Repository map

| Path | Purpose |
|---|---|
| `data/` | Daily futures prices, monthly returns, asset map, macro series, and frozen 42-input forecast artifacts. |
| `futures_portfolio/backtests/daily_baseline.py` | Course daily 12-month TSMOM baseline with 11% portfolio risk targeting. |
| `futures_portfolio/backtests/selected42_inputs.py` | Four-sleeve input construction and causal signal alignment. |
| `futures_portfolio/backtests/selected42_target11.py` | **Final strategy runner**: combines the fixed 42-input signal, applies 11% portfolio risk targeting, marks daily returns, and compares matched endpoints with the baseline. |
| `futures_portfolio/signals/` | Daily price trend, economic trend, and negative-skew sleeve definitions. |
| `futures_portfolio/factors/`, `futures_portfolio/models/training.py` | Feature definitions, pre-2005 IC/HAC selection logic, and chronological Extra Trees fitting. |
| `futures_portfolio/portfolio/` | Volatility and covariance estimation and risk normalization. |
| `futures_portfolio/execution/` | Daily marking, 2-basis-point trading costs, and modeled roll costs. |
| `outputs/baseline/` | Course baseline series required for the final matched comparison. |
| `outputs/final_strategy/` | Final performance table, aligned and daily returns, Sharpe chart, and in-sample/out-of-sample drawdown charts. |
| `report.md` | Methods, results, interpretation, and limitations. |

The 42-input set was selected using pre-2005 directional IC and HAC evidence, then fixed; the model was refitted using information available before 2015. Before the ML sleeve has an out-of-training forecast, its budget returns to price trend. The saved model and selection metadata are in `data/frozen_selected42/`. The strategy and baseline use the same 11% ex-ante target; realized volatility can differ.

Only the selected strategy and course baseline are part of this submission. Exploratory turning-point, allocation, exposure-limit, and older presentation experiments are excluded.
