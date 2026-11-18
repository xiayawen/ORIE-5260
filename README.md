# ORIE 5260: Final daily futures strategy

This submission compares the course's daily time-series momentum (TSMOM) baseline with a **four-sleeve, 42-input futures portfolio** across 58 markets. Both target **11% annualized ex-ante volatility** and form positions every 21 business days. The final portfolio combines daily price trend (30% signal budget), economic trend (20%), within-class negative skew (20%), and a frozen Extra Trees forecast (30%). It has no gross or net exposure caps. See the [main report](report.md) for the method, results, and limitations.

On matched 21-day endpoints, the final portfolio's net Sharpe is **1.283** in 1976–2014 and **0.356** in January 2015–May 2025; the baseline's is **1.222** and **0.243**, respectively. The out-of-sample period was examined during research and is not an untouched holdout.

## Run the submitted backtests

Install [requirements.txt](requirements.txt), then run from the repository root:

```bash
python run.py baseline
python run.py selected42_target11
```

The baseline command generates the comparison series in `outputs/baseline/`. The second command reads the saved, chronological 42-input probabilities in `data/frozen_selected42/` and regenerates the tables, daily returns, and figures in [outputs/final_strategy/](outputs/final_strategy/). These saved probabilities define the evaluated strategy. The frozen input list and final fitted model are included for inspection; a fresh model refit can differ slightly across software versions.

## Repository structure

| Path | Purpose |
|---|---|
| [run.py](run.py), `futures_portfolio/cli.py` | Entry point and the two submitted commands. |
| [data/](data/) | Daily futures prices, monthly returns, market-to-asset-class map, macro series, and `frozen_selected42/` forecast artifacts. |
| `futures_portfolio/common/` | Data loaders and the 21-business-day formation calendar. |
| `futures_portfolio/signals/` | Price-trend, economic-trend, and negative-skew signals. |
| `futures_portfolio/factors/`, `futures_portfolio/models/training.py` | Candidate features, pre-2005 IC/HAC selection rules, and chronological model-fitting code. |
| `futures_portfolio/portfolio/` | Volatility and covariance estimates and portfolio risk scaling. |
| `futures_portfolio/execution/` | Daily NAV marking, 2-basis-point trade costs, and modeled roll costs. |
| `futures_portfolio/backtests/daily_baseline.py` | Course 12-month TSMOM baseline at an 11% ex-ante portfolio target. The root [daily_baseline.py](daily_baseline.py) is a compatibility entry point. |
| `futures_portfolio/backtests/selected42_inputs.py` | Builds and dates the four sleeve inputs. |
| `futures_portfolio/backtests/selected42_target11.py`, `selected42_metrics.py` | **Final strategy runner** and matched-period performance measures. |
| `outputs/baseline/` | The retained course baseline series used in the comparison. |
| [outputs/final_strategy/](outputs/final_strategy/) | Final performance CSV, aligned and daily returns, Sharpe chart, and in-sample/out-of-sample drawdown charts. Filenames retain `selected42_target11` to identify the specification. |
| [report.md](report.md), [docs/report_equations/](docs/report_equations/) | Main academic report and its GitHub-compatible equation images and source definitions. |
| [report (1).md](<report (1).md>) | Separate collaborator-submitted report copy, retained unchanged. |

The 42-input set was selected using pre-2005 directional IC and HAC evidence and held fixed for the pre-2015 model refit. Before an out-of-training ML forecast is available, its budget returns to price trend. Historical screening used an earlier 10% research convention; all **submitted portfolio results** use the 11% target.

Older experiments, the PPT, and the previous `orie5260/` package are excluded by [.gitignore](.gitignore). They may still appear in an existing local checkout, but are not part of this branch's tracked submission.
