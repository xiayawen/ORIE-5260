# R2: hierarchical risk budgeting, in-sample vs out-of-sample

**Execution timing convention (main results).** Weights formed from month-t closes earn the whole month-t+1
return, so trades are assumed to fill at the same close used to compute the signal, while the Lecture 8
market-impact cost assumes 5-day execution. `alpha_decay_execution.py` shows that a feasible schedule lowers
in-sample net Sharpe by about 0.07-0.09. Treat reported net Sharpe ratios as upper bounds by roughly this amount.

IS = Jan 1976 - Dec 2014 (all design choices were made here). OOS = Jan 2015 - May 2025 (evaluation only).
Data: `MonthlyReturns_FullSample.xlsx`; on 1969-2014 it matches `MonthlyReturns.csv` except six December 2014
cells that are now filled. AP (Australian equity) has no data from June 2022 to February 2025 and then prints
+23%/+43%/+44% in March-May 2025 (almost certainly a data error); the 12-month signal is undefined after the
gap, so no strategy holds AP then. EC (Eurodollar) is labelled FX in `AssetMapCsv.csv` but is a short-rate future.

## Method

Signed risk budgeting (Spinu 2013): with signs s from the 12-month signal, magnitudes x > 0 minimise
0.5 x'Cx - b'log x with C = diag(s) S diag(s), so every instrument's Euler PCR equals its budget b_i = 1/(K n_c):
each active asset class carries 1/K of ex-ante risk, split equally inside the class. S is the 6-month EWMA
covariance through the formation month. The portfolio is scaled to 10% predicted volatility and gross exposure
above 4x is cut proportionally (risk shares unchanged).

Solver: at most 13 Newton steps, max |PCR - budget| = 9.3e-12.
The 4x cap binds in 75% of months, so average predicted volatility is
5.2% rather than 10%: equal risk for fixed income and FX needs large notional in
low-volatility rate futures.

## Performance net of Lecture 8 costs at $1bn

| Strategy | IS Sharpe | OOS Sharpe | IS vol | OOS vol | IS MaxDD | OOS MaxDD | IS turnover | OOS turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.89 | -0.09 | 11.1% | 11.1% | -26.2% | -33.1% | 8.3 | 13.3 |
| class_count | 0.76 | -0.00 | 16.0% | 12.8% | -29.1% | -28.1% | 10.9 | 17.2 |
| ewma_vol | 1.03 | 0.03 | 12.7% | 12.5% | -19.0% | -28.4% | 14.1 | 28.7 |
| ewma_cov_target | 0.96 | -0.08 | 9.8% | 8.8% | -14.9% | -25.0% | 9.4 | 13.1 |
| enhanced | 1.02 | -0.01 | 9.4% | 7.1% | -14.2% | -15.0% | 9.6 | 12.8 |
| rb_class | 0.77 | -0.10 | 10.5% | 5.3% | -13.1% | -15.5% | 25.6 | 33.9 |
| static_bmk | 0.45 | 0.39 | 14.5% | 14.7% | -67.8% | -28.6% | 1.7 | 2.0 |

## Gross of costs

| Strategy | IS Sharpe | OOS Sharpe | IS vol | OOS vol | IS MaxDD | OOS MaxDD | IS turnover | OOS turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.97 | -0.02 | 11.1% | 11.1% | -26.0% | -30.5% | 8.3 | 13.3 |
| class_count | 0.82 | 0.06 | 16.0% | 12.8% | -28.9% | -25.0% | 10.9 | 17.2 |
| ewma_vol | 1.12 | 0.14 | 12.8% | 12.5% | -18.9% | -22.8% | 14.1 | 28.7 |
| ewma_cov_target | 1.05 | -0.00 | 9.8% | 8.8% | -13.6% | -22.6% | 9.4 | 13.1 |
| enhanced | 1.11 | 0.07 | 9.5% | 7.1% | -13.7% | -13.6% | 9.6 | 12.8 |
| rb_class | 1.00 | 0.19 | 10.6% | 5.4% | -12.0% | -12.6% | 25.6 | 33.9 |
| static_bmk | 0.47 | 0.41 | 14.5% | 14.7% | -67.5% | -28.4% | 1.7 | 2.0 |

Sharpe standard errors are about 0.19 IS and 0.31 OOS (Lo 2002, iid).

## Ex-ante vs realized asset-class risk shares

Ex-ante: average EWMA-covariance Euler PCR at formation. Realized: cov(r_class, r_portfolio) / var(r_portfolio)
over the period (sums to one).

| Strategy | Period | Ex-ante COMM/EQ/FI/FX | Realized COMM/EQ/FI/FX | Realized effective classes |
|---|---|---|---|---:|
| baseline | IS | 53% / 16% / 13% / 18% | 52% / 19% / 12% / 17% | 2.86 |
| baseline | OOS | 35% / 26% / 27% / 13% | 31% / 25% / 30% / 14% | 3.71 |
| enhanced | IS | 53% / 17% / 14% / 16% | 64% / 11% / 10% / 15% | 2.19 |
| enhanced | OOS | 33% / 28% / 26% / 14% | 28% / 22% / 33% / 16% | 3.75 |
| rb_class | IS | 32% / 19% / 23% / 26% | 48% / 9% / 16% / 27% | 2.96 |
| rb_class | OOS | 25% / 25% / 25% / 25% | 38% / 18% / 21% / 23% | 3.67 |

## Findings

1. Every TSMOM variant weakens OOS by roughly 0.8-1.1 net Sharpe, including the unmodified baseline, so the drop
   is mainly a regime effect (the 2015-2025 trend-following drought) rather than overfitting of the enhancements.
   The static long benchmark holds up.
2. R2 meets its ex-ante goal (OOS ex-ante shares 25/25/25/25) and has the smallest IS drawdown, but the budget is only
   partly realised (IS commodities ~32% budgeted vs ~48% realised): 6-month EWMA correlations are noisy.
3. R2's gross Sharpe is close to enhanced, but it trades 2-3x as much, because the full-covariance budget is
   re-solved every month (small correlation changes and any sign flip resize every position). Net Sharpe is
   therefore lower. Combine with the T1 no-trade band (`cost_aware_rebalance.py`) for the adopted comparison.

## Look-ahead audit

`python -m unittest test_lookahead.py` reruns every strategy on data truncated at 1990-06, 2014-12 and 2020-03
and checks that all weights, volatility estimates, Lecture 8 costs and T1 holding paths formed up to each cut are
identical to the full-sample run, plus the one-month execution lag. All tests pass.

Remaining sources of bias found by code inspection (none affects the headline strategy weights):

| Where | Issue | Severity |
|---|---|---|
| Research process | All parameters and the enhanced design were chosen after viewing 1976-2014; IS Sharpe is optimistic. Only 2015-2025 is clean OOS. | High (measured above) |
| `strategy_backtest.py` `full_sample_volatility`; `rolling_backtest.py` full-sample controls | Positions sized with full-sample volatility (true look-ahead). Controls only; never quote as tradable. | Medium |
| `strategy_backtest_adj.vol_matched_returns`; `generate_strategy_analysis.py` vol matching | Scales by full-sample realized vol. Sharpe unchanged; matched CAGR, drawdown and wealth plots are ex post. | Low (documented) |
| Return-attribution regimes; diagonal-validation high-vol quintile | Ex-post labels; fine for attribution, not as signals. | Low (documented) |
| `economic_trend.py` | Current-vintage FRED data: macro revisions were not known in real time. | Medium (that module) |
| `transaction_cost_model.py` ADV and spreads | Calibrated to recent liquidity and applied back to 1976; daily volume ends 2014, so OOS ADV uses class constants. | Medium (cost level) |
| Universe | The 58 markets were chosen with hindsight (survivorship / selection). | Medium |
| `tsmom_weights` 1/N divisor | Eligible instruments with no signal (stopped trading / data gap) still count in N, diluting positions (0.2 IS, 1.9 OOS on average). | Low |
| Execution timing | Fill at the signal close with 5-day impact (see top). | ~0.07-0.09 Sharpe |
