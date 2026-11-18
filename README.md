# ORIE 5260: Daily Futures Trend Portfolio

This repository compares a course **daily time-series momentum baseline** with a four-sleeve futures portfolio across 58 markets. The selected portfolio combines price trend (30% signal budget), economic trend (20%), negative skew (20%) and a fixed **42-input Extra Trees** signal (30%). It now targets **11% ex-ante annual volatility**, matching the course baseline, and fully rebalances every 21 business days. It has no gross or net exposure caps and does not use cost-aware execution. The main [academic report](report.md) explains the construction, results and limitations.

On matched 21-day endpoints, selected-portfolio net Sharpe is **1.283** in 1976–2014 and **0.356** in the January 2015–May 2025 out-of-sample period; the course baseline is **1.222** and **0.243**, respectively. The out-of-sample period has been examined during research and is not an untouched holdout.

## Start here

Install [`requirements.txt`](requirements.txt) and run commands from the repository root:

```bash
python run.py --list
python run.py baseline       # Course daily baseline
python run.py selected-42    # Selected portfolio, matched comparison and figures
python -m unittest discover -s tests
```

`selected-42` reads the saved frozen Extra Trees probabilities in `outputs/ic_t_feature_filter/`. To rebuild that research path first:

```bash
python run.py factor-ic
python run.py ic-filter
python run.py ic-filter-oos
python run.py ic-t-filter
python run.py selected-42
```

Use `python run.py <command> --dry-run` to see a command's module and required saved inputs without running it. `python run.py model-evidence` regenerates the factor and model evidence figures. The root scripts `daily_baseline.py`, `run_final_strategy.py` and `compare_baseline.py` remain compatibility entry points; **`run_final_strategy.py` reconstructs the original 66-input portfolio**, not the selected 42-input strategy.

## Repository structure

| Path | Purpose |
|---|---|
| `data/` | Monthly returns, daily futures prices, asset mapping and macroeconomic inputs. |
| `orie5260/common/` | Data loading and the 21-business-day formation calendar. |
| `orie5260/signals/` | Daily price trend, economic themes and within-class negative-skew sleeves. |
| `orie5260/factors/` | Candidate factor features, IC/HAC statistics and input selection. |
| `orie5260/models/` | Extra Trees training and forecast construction. |
| `orie5260/portfolio/` | Covariance estimation, risk scaling, limits and allocation experiments. |
| `orie5260/execution/` | Daily return accounting, transaction costs and experimental cost-aware execution. |
| `orie5260/backtests/` | Course baseline and original 66-input strategy/diagnostics. |
| `orie5260/research/` | Feature-screening and allocation experiments. |
| `orie5260/presentation/prepare_results.py` | **Selected 42-input portfolio** and presentation tables/figures; invoked by `python run.py selected-42`. |
| `run.py`, `orie5260/cli.py` | Command-line entry points for reproducible runs. |
| `outputs/baseline/` | Course baseline returns and robustness variants. |
| `outputs/ic_t_feature_filter/` | Frozen 42-input list, models, probabilities and screening comparisons. |
| `outputs/selected42_target11/` | **Current 11%-target selected-portfolio results**, aligned returns, daily returns and figures. |
| `reports/research/` | Research reports for candidate signals, screens and portfolio alternatives, including rejected variants. |
| `ppt/` | Presentation materials from an earlier reporting pass; use this README, report and selected-result folder for current figures. |
| `tests/` | Timing, accounting, model-selection and module tests. |
| `archive/` | Original flat-layout source and presentation-authoring snapshots. |
| `docs/MODULE_MAP.md` | Mapping from old flat script names to the current modules and commands. |

The current selected strategy uses the **same frozen 42-input list** when Extra Trees is refitted before 2015; before 2005, its unavailable ML budget falls back to price trend. The 42-input screen required training-period absolute mean rank IC ≥ 0.01 and a directionally consistent six-lag HAC |t| ≥ 1.96. The selected portfolio uses 2 basis points per unit traded plus a simple roll allowance. See [report.md](report.md) for methodology and [the research index](reports/research/README.md) for alternative designs.

The selected strategy has no turning-point overlay. Research variants are documented separately in [`reports/research/`](reports/research/).
