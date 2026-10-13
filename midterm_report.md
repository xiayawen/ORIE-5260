# Midterm Report: Futures Time-Series Momentum

## EDA: what we know about the data

### Summary

The project uses monthly returns for 58 futures markets from January 1969 to December 2014. The universe contains 26 commodity, 14 equity-index, 10 fixed-income, and 8 FX series. `analysis_eda.py` checks coverage, missing values, outliers, cross-market correlations, and agreement between the supplied monthly returns and returns recomputed from daily closing prices.

### Methodology and assumptions

- The supplied matrix contains 552 month-end rows and 20,987 non-missing instrument-month observations.
- Series have different start dates. The longest contains 551 returns, while the shortest contains 75. Missing history is retained rather than backfilled.
- An observation is flagged as an outlier when it falls outside three times the instrument-level interquartile range or has an absolute robust z-score above five. Flagging is diagnostic; observations are not automatically removed.
- Daily files are converted to month-end close-to-close returns and compared with the supplied monthly file where both are available.
- Descriptive Sharpe ratios use a zero risk-free rate.

### Key results

| Data check | Result | Interpretation |
| --- | ---: | --- |
| Instruments | 58 | Broad multi-asset futures universe |
| Monthly rows | 552 | January 1969–December 2014 |
| Non-missing observations | 20,987 | Panel is unbalanced because markets begin at different dates |
| Flagged outliers | 126 | Large commodity moves require care but are economically plausible |
| Daily/monthly overlapping checks | 14,974 | Most reconstructed returns agree closely with the supplied data |
| Median instrument-level maximum recomputation difference | 0.0000% | Strong overall agreement |
| Largest instrument-level maximum difference | 4.70% for RL | This series should be reviewed before final conclusions |

Absolute returns show much stronger persistence than raw returns. Across instruments, mean lag-one autocorrelation is 18.4% for absolute returns but only 6.2% for raw returns. This supports time-varying volatility estimation, while the weaker raw-return autocorrelation suggests that the momentum signal should be assessed directly against future returns.

![Cross-instrument return correlation matrix](outputs/eda_output/correlation_matrix.svg)

The data are suitable for a diversified trend-following study, but the unequal histories, large commodity observations, and remaining reconstruction discrepancies should remain visible in robustness checks.

## Backtest strategy construction

### Summary

The main strategy is the adjusted baseline implemented in `strategy_backtest_adj.py`. It is a monthly time-series momentum strategy with a 12-month signal, expanding-window instrument volatility, inverse-volatility scaling, and equal allocation across eligible instruments. The backtest runs from January 1976 through December 2014.

### Methodology

For instrument (i) at month (t), the signal is

\[
s_{i,t}=\operatorname{sign}\left(\sum_{k=0}^{11} r_{i,t-k}\right).
\]

Annualized volatility is estimated from all available returns through month (t), subject to at least 36 valid monthly observations:

\[
\hat\sigma_{i,t}=\operatorname{Std}(r_{i,1:t})\sqrt{12}.
\]

The preliminary instrument position is

\[
p_{i,t}=s_{i,t}\frac{0.40}{\hat\sigma_{i,t}},
\]

and the portfolio divides these positions equally across the eligible markets. Positions formed using information through month (t) earn returns in month (t+1). The strategy rebalances monthly.

### Main assumptions

- The 40% parameter scales each instrument before diversification. It is not a 40% portfolio volatility target.
- The risk model is diagonal: instrument variances are estimated, while all cross-instrument covariances are assumed to be zero.
- Expanding volatility treats historical realized volatility as a proxy for future volatility.
- Missing realized returns for held positions are filled with zero.
- There are no leverage or position caps, margin constraints, financing costs, contract-specific spreads, or explicit futures roll costs.
- Transaction costs are tested separately at 0, 5, 10, and 25 basis points per one-way change in target weight.
- The static benchmark is always long and uses the same instrument-level volatility scaling and eligibility logic.

This construction avoids the original classroom backtest's full-sample volatility look-ahead. It does not yet use covariance-aware portfolio risk or a portfolio-level volatility target.

## Backtest results and analysis

### Signal diagnostics: items 1–2

`signal_diagnostics.py` measures return, absolute-return, and squared-return autocorrelation at lags 1–12. It also tests whether 1-, 3-, 6-, and 12-month signals predict next-month returns by instrument, asset class, and period. HAC t-statistics are calculated from monthly equal-weighted signed returns to account for dependence across instruments within each month.

| Lookback | Positive-minus-negative next-month return | Directional hit rate | Annualized signed return | Vol-scaled Sharpe | HAC t-stat, vol-scaled |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 month | 0.58% | 52.8% | 5.16% | 0.57 | 3.61 |
| 3 months | 0.79% | 53.5% | 7.68% | 0.77 | 4.10 |
| 6 months | 0.72% | 54.0% | 7.32% | 0.72 | 3.73 |
| 12 months | 0.79% | 54.4% | 7.43% | 0.86 | 4.51 |

All four horizons have positive return spreads and hit rates above 50%. The 12-month signal has the highest hit rate and vol-scaled Sharpe, supporting its use as the baseline. The 3-month signal is also strong, which supports testing a diversified multi-horizon signal.

![Signal return spread by lookback](outputs/signal_diagnostics_output/signal_return_spread_by_lookback.png)

### Performance: item 3

`baseline_performance_analysis.py` checks signal timing, constructs standardized downstream data, and reports performance, drawdowns, turnover, costs, and exposures.

| Metric | TSMOM baseline | Static benchmark |
| --- | ---: | ---: |
| CAGR | 10.64% | 5.91% |
| Annualized mean return | 10.77% | 6.82% |
| Annualized volatility | 11.15% | 14.52% |
| Sharpe ratio, RF = 0 | 0.97 | 0.47 |
| Maximum drawdown | -26.03% | -67.54% |
| Monthly hit rate | 64.1% | 60.0% |
| Annual turnover | 7.24 | 0.41 |

The baseline materially outperforms the static benchmark, with higher return, lower volatility, and a much smaller maximum drawdown. Its main weakness is turnover. At 10 bps per one-way weight change, CAGR declines to 9.85% and Sharpe to 0.90; at 25 bps, CAGR is 8.68% and Sharpe is 0.81. The cost result remains favorable under the tested assumptions, but it excludes market-specific spreads, roll costs, financing, and liquidity effects.

Average gross exposure is 3.13, with a maximum of 4.60. Average net exposure is +0.84 and ranges from -2.50 to +4.24. The strategy therefore uses substantial implicit leverage and has a long bias on average.

![Baseline cumulative return](outputs/baseline_performance_output/baseline_cumulative_return.png)

![Rolling baseline performance](outputs/baseline_performance_output/baseline_rolling_performance.png)

### Return attribution: item 4

`baseline_return_attribution.py` uses the standardized item 3 instrument returns and weights. It attributes arithmetic return by instrument, asset class, long versus short positions, decade, drawdown event, and an S&P 500 futures proxy bull/bear regime.

| Source | Annualized mean contribution | Share of baseline mean return |
| --- | ---: | ---: |
| Commodities | 5.15% | 47.8% |
| FX | 2.13% | 19.8% |
| Fixed income | 1.83% | 17.0% |
| Equity indices | 1.66% | 15.4% |
| Long positions | 8.74% | 81.2% |
| Short positions | 2.03% | 18.8% |

All four asset classes and both position directions contribute positively, which supports the economic breadth of the strategy. Returns are nevertheless concentrated in commodities and long positions. Lumber and gold are the largest individual contributors, while soybeans and orange juice detract most.

The strategy remains profitable in the S&P 500 futures proxy regimes: annualized mean return is 10.26% in bear regimes and 11.13% in bull regimes. Bear-regime volatility is higher, at 12.60% versus 8.33% in bull regimes. Returns are also positive in every reported decade, although annualized mean return falls to 7.57% in 2010–2014.

![Asset-class and direction return contribution](outputs/baseline_return_attribution_output/asset_class_and_direction_contribution.png)

### Baseline risk and risk-model validation: items 5–6

`baseline_risk_analysis.py` calculates diagonal variance contributions and concentration using item 3 weights and volatility estimates. Under this model, commodities account for 62.7% of average predicted variance, followed by FX at 15.9%, fixed income at 11.0%, and equities at 10.4%. The average effective number of instrument risk positions is 39.6, but the average effective number of asset-class risk positions is only 2.35. Instrument diversification is therefore much stronger than asset-class diversification.

`validate_diagonal_risk_model.py` shifts the item 3 weights and volatility estimates back to their formation dates, then compares predicted volatility with the volatility of fixed-weight returns over the next 12 months. A three-month horizon is included as a robustness check.

| Forecast horizon | Predicted volatility | Realized volatility | Mean error | Predicted-realized correlation | Realized exceeds forecast |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 12 months | 6.82% | 9.78% | +2.96% | 0.13 | 74.8% |
| 3 months | 6.79% | 8.87% | +2.08% | 0.08 | 54.6% |

The current risk model materially understates subsequent risk and has little linear forecasting power. At the primary 12-month horizon, realized volatility exceeds the prediction in nearly three quarters of observations and exceeds it by more than 25% in 50.4% of observations. The zero-covariance assumption is a likely source of underestimation because same-direction exposures can be correlated.

![Predicted and realized volatility](outputs/risk_model_validation_output/forecast_scatter.png)

### Benchmark and factor comparison: item 7

`generate_strategy_analysis.py` compares the standardized baseline with the static benchmark and SG Trend. It reports raw and volatility-matched performance, rolling statistics, and HAC regressions. SG Trend is available only from January 2000 through December 2014.

| Metric, 2000–2014 | TSMOM baseline | SG Trend |
| --- | ---: | ---: |
| Annualized mean return | 10.72% | 7.75% |
| CAGR | 10.37% | 6.90% |
| Annualized volatility | 12.83% | 14.60% |
| Sharpe ratio, RF = 0 | 0.84 | 0.53 |
| Maximum drawdown | -26.03% | -17.66% |

The two series have a correlation of 0.62. A raw-return regression estimates a beta of 0.54 and annualized alpha of 6.52% with a HAC t-statistic of 2.48. This indicates meaningful common trend exposure alongside substantial differences in implementation. The comparison is descriptive because SG Trend may use different markets, fees, risk targets, and index rules.

In the joint six-factor regression, annualized baseline alpha is 7.20%, the HAC t-statistic is 2.27, and the model explains 28.0% of variance. Momentum is the clearest exposure, with a beta of 0.29 and HAC t-statistic of 5.17. These equity factors do not fully describe a diversified futures strategy, so residual return should not automatically be interpreted as manager skill.

![Baseline and SG Trend cumulative performance](outputs/strategy_analysis_output/sg_trend_cumulative.png)

## Key findings

1. **The baseline has a credible momentum signal.** All tested lookbacks predict next-month returns, and the 12-month signal has a 54.4% directional hit rate with a statistically strong vol-scaled return.
2. **Historical performance is strong and broad.** The baseline earns a 10.64% CAGR and 0.97 Sharpe ratio from 1976–2014. Every asset class, both long and short positions, and every reported decade contribute positively.
3. **Diversification is uneven.** Commodities generate 47.8% of mean return and 62.7% of diagonal risk. The effective number of asset-class risk positions is only 2.35.
4. **The risk model is the clearest weakness.** Twelve-month realized volatility averages 9.78% against a 6.82% prediction, and forecast-realized correlation is only 0.13.
5. **Turnover matters.** The strategy remains attractive at the tested costs, but the assumptions are generic and omit several implementation costs.
6. **The strategy resembles, but does not replicate, SG Trend.** Their correlation is 0.62, while the baseline has higher return and Sharpe but a deeper maximum drawdown over the overlapping sample.
7. **Recent performance is weaker.** The 2010–2014 annualized mean return of 7.57% is below earlier decades, motivating stability and out-of-sample testing.

## Next steps: enhancing the model

1. **Add covariance-aware portfolio risk.** Estimate expanding, rolling, EWMA, and shrinkage covariance models. Start with shrinkage toward the diagonal because 58 instruments and limited early history can make the sample covariance unstable.
2. **Introduce portfolio-level volatility targeting.** Scale the whole portfolio to a common annual target using ex-ante covariance risk. Apply leverage and scaling caps, and report target breaches.
3. **Separate risk-model and leverage effects.** First compare diagonal and covariance risk estimates at comparable exposure. Then add dynamic portfolio volatility targeting as a separate experiment.
4. **Improve asset-class diversification.** Test equal asset-class risk budgets or limits on class-level risk shares, especially for commodities.
5. **Combine signal horizons.** The 3-, 6-, and 12-month signals are all informative. Use a predetermined multi-horizon average and assess whether it improves stability rather than selecting the best full-sample lookback.
6. **Use faster volatility estimates.** Compare expanding volatility with rolling and EWMA estimates, particularly around volatility regime changes.
7. **Strengthen implementation assumptions.** Add instrument-specific cost estimates, futures roll costs, financing, liquidity constraints, leverage caps, and volatility floors.
8. **Validate enhancements out of sample.** Use walk-forward evaluation with parameters fixed before each test window. Compare predicted and realized risk, turnover, drawdowns, and performance by decade and asset class.
9. **Expand factor analysis.** Add economically relevant futures factors such as equity, duration, USD, commodity, carry, value, and trend factors. The current equity-factor set is incomplete.
10. **Resolve remaining data issues.** Review the RL recomputation difference and test whether flagged outliers materially affect signals, volatility estimates, and results.
