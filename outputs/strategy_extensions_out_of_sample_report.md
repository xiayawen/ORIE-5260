# ORIE 5260 | Rebalance Frequency, Leverage, and Imbalance

**Out-of-sample period** · January 2015 through May 2025, 125 complete months.

Halving short positions improved compound returns in both experiments. Under the team's monthly cost model, net CAGR rose from −0.42% to +0.88% and maximum drawdown fell from 26.33% to 16.74%. In the daily execution model, weekly rebalancing with half-sized shorts raised net CAGR from −1.69% to +0.24% at 5 bps per unit traded. At 10 bps, weekly still led and all three schedules had negative net CAGR.

Both experiments use the uploaded continuous futures data and the original universe of 58 futures tickers. History before 2015 initializes the signals and positions. The data end on June 13, 2025, so the evaluation stops in May. The two experiments use different volatility estimates, execution timing, and cost models. Compare the strategies within each section.

## 1. Rebalance frequency

The monthly, weekly, and daily strategies use the same 12-month momentum rule and expanding instrument volatility. Between month-ends, the signal combines 11 completed monthly returns with the current month-to-date return. Risk estimates update at month-end. Orders are formed on the last weekday of the month, on Fridays, or each weekday, depending on the schedule. Each instrument fills at its next quoted close and positions drift between fills.

| Frequency | Gross CAGR | CAGR at 2 bps | CAGR at 5 bps | CAGR at 10 bps | CAGR at 25 bps | Max daily drawdown at 10 bps | Annual turnover at 10 bps |
|---|---:|---:|---:|---:|---:|---:|---:|
| Monthly | −1.85% | −2.13% | −2.54% | −3.23% | **−5.27%** | 42.52% | 14.13× |
| Weekly | −0.44% | −0.94% | **−1.69%** | **−2.92%** | −6.53% | **40.63%** | 25.18× |
| Daily | **+0.47%** | **−0.51%** | −1.96% | −4.33% | −11.11% | 43.61% | 48.87× |

Daily rebalancing leads before costs and at 2 bps. Weekly leads at 5 and 10 bps, and monthly leads at 25 bps. Weekly also led at 10 bps in the 1976–2014 experiment. At that cost, daily trading turns over almost twice as much notional as weekly trading in the new sample. All three schedules have negative CAGR at each positive cost shown. [Earlier frequency report](rebalance_frequency_output/frequency_report.md)

Costs apply to drift-adjusted traded notional and exclude separate roll, funding, and market impact charges. Instruments without a quote retain the last observed price. Under a sensitivity that approximates an exit at that price after ten weekdays without quotes, the 10 bps ranking stays the same. CAGR is −3.26% monthly, −2.94% weekly, and −4.34% daily. The last observed prices approximate exit values. [Frequency methodology and sensitivity](rebalance_frequency_out_of_sample/frequency_report.md) · [Full results](rebalance_frequency_out_of_sample/performance_summary.csv)

### Rebalance frequency with half-sized shorts

We also reran each schedule after applying the half-short rule to its target weights. All three schedules use the same execution and cost assumptions as the original frequency comparison.

| Frequency | Gross CAGR | CAGR at 2 bps | CAGR at 5 bps | CAGR at 10 bps | CAGR at 25 bps | Annual turnover at 10 bps |
|---|---:|---:|---:|---:|---:|---:|
| Monthly | +0.07% | −0.14% | −0.44% | −0.96% | **−2.48%** | 10.30× |
| Weekly | +1.17% | +0.80% | **+0.24%** | **−0.67%** | −3.38% | 18.40× |
| Daily | **+1.84%** | **+1.12%** | +0.04% | −1.72% | −6.85% | 35.62× |

The half-short rule improves CAGR across all three schedules and five cost assumptions in this sample. Weekly trading earns +0.24% at 5 bps, compared with −1.69% under the original weights. It retains the highest CAGR at 10 bps, where all schedules remain negative. The choice of a smaller short budget used earlier results from the same historical window. [Half-short frequency report](rebalance_frequency_half_short/frequency_report.md) · [Full results](rebalance_frequency_half_short/performance_summary.csv)

## 2. Leverage and long–short imbalance

**Leverage** is gross exposure, the sum of absolute portfolio weights. **Imbalance** is signed net exposure, the sum of portfolio weights. Both are measured relative to equity. For example, long positions of 3× equity and short positions of 1× equity imply gross exposure of 4× and net exposure of +2×.

All variants in this section start from the team's monthly price trend baseline, which uses 12-month momentum, rolling 12-month instrument volatility with a 1% annualized floor, and a 10% portfolio volatility target. We use the team's cost model of 2 bps per unit of target-weight turnover and 2 bps per roll, with four rolls per year prorated by gross exposure. The shared baseline's gross CAGR is +0.23%, and its net compounded return over the full period is −4.34%. Monthly net returns produce a +0.13% annualized arithmetic mean and a −0.42% CAGR.

The first out-of-sample run used the earlier expanding-volatility baseline and a different cost model. It is retained as an archive. [Archived exposure report](net_exposure_out_of_sample/out_of_sample_report.md)

| Strategy | Net CAGR | Annualized mean net return | Max monthly drawdown | Avg. gross exposure | Avg. signed net exposure |
|---|---:|---:|---:|---:|---:|
| Shared price trend baseline | −0.42% | +0.13% | 26.33% | 4.57× | +0.82× |
| 4× gross cap only | −0.47% | −0.11% | 21.32% | 3.59× | +0.56× |
| ±1× net cap only | −1.31% | −0.90% | 30.65% | 3.65× | +0.22× |
| Gross and net caps | −0.82% | −0.56% | 23.33% | 3.02× | +0.21× |
| Smooth leverage only | −0.39% | +0.17% | 27.71% | 4.60× | +0.81× |
| Smooth leverage and imbalance | +0.04% | +0.63% | 24.95% | 4.60× | +0.85× |
| Half-sized short positions | **+0.88%** | **+1.20%** | **16.74%** | 3.63× | +1.76× |
| Same gross as half-short, original long–short proportions | −0.15% | +0.19% | 21.53% | 3.63× | +0.84× |

**Fixed limits.** The 4× gross cap scales both sides down proportionally when their combined notional exceeds the limit. The ±1× net cap trims the larger side when the net position moves outside the band. The gross cap lowered maximum drawdown by 5.01 percentage points while giving up about 0.04 points of net CAGR, based on unrounded results. The net cap alone lowered net CAGR by 0.68 points and deepened maximum drawdown by 7.25 points versus the control that matched gross exposure each month and preserved the original long–short proportions. [Fixed-limit report and matched controls](net_exposure_out_of_sample_aligned/out_of_sample_report.md)

**Three-month smoothing.** We smooth gross exposure and, in the second variant, the signed net share of gross exposure using averages of current and past target weights. The two smoothing variants have the same gross exposure each month. Each side may reach up to 1.25 times its baseline notional. Adding imbalance smoothing improved net CAGR by 0.43 points and reduced maximum drawdown by 2.76 points compared with smoothing gross exposure alone. Joint smoothing increased annual turnover from 14.70× to 17.40× versus the shared baseline, and its net CAGR remained close to zero. Its average signed net exposure was slightly higher, consistent with smoothing the path of exposure over time. [Smoothing methods and results](exposure_smoothing_output/exposure_smoothing_report.md) · [Full results](exposure_smoothing_output/performance_summary.csv)

**Smaller short budget.** This variant keeps the baseline long weights and halves every short weight at formation. It gains 1.03 percentage points of net CAGR versus proportionally reducing both sides to the same gross exposure in every month. Annual turnover falls from 14.70× to 11.14× compared with the shared baseline. Net CAGR is +0.11% if both cost rates rise to 5 bps and −1.17% at 10 bps. The strategy also gives up return versus the original baseline in both pre-2015 comparison periods. The short budget was developed after inspecting the 2015–2025 attribution, so these later returns are exploratory. [Short-budget report](short_budget_output/short_budget_report.md)

## Interpretation

The 4× gross cap had the shallowest drawdown among the fixed limits. The smaller short budget leads the exposure table on both net CAGR and maximum drawdown while taking a higher net long position. Imposing a strict net band hurt performance relative to scaling the whole portfolio to the same gross exposure. For rebalance frequency, the choice depends on execution costs, with weekly rebalancing leading under the two intermediate cost assumptions.

The sample falls after the original 2014 cutoff, but it had already been examined for other specifications before the smoothing rules were tested. Treat the smoothing results as exploratory. Some contracts have missing or discontinued quotes. The monthly exposure experiment assigns zero realized P&L to a held instrument-month with a missing return. The frequency experiment marks positions daily, while the exposure experiment marks them monthly. Drawdowns should be compared within each experiment.

## Why several out-of-sample returns are negative

The frequency backtest on the new upload reproduces the old 1976–2014 CAGRs to numerical precision at 10 bps. Those CAGRs are 8.95% monthly, 9.46% weekly, and 8.07% daily. Separately, returns reconstructed from the new closes match 20,915 historical instrument-month observations with a pooled mean absolute difference of about 0.00022 percentage points. These checks cover the overlapping data and the earlier frequency results.

The 12-month momentum signal was weaker after 2014. Across nonzero, observed instrument-months with a valid signal, its next-month directional hit rate fell from 54.4% in 1980–2014 to 50.4% in the later sample. The unweighted signed return averaged +4.47% per year on an arithmetic basis in the earlier period and −1.07% in the later period. These signal diagnostics weight instrument-months equally. In the actual shared monthly portfolio, the annualized arithmetic gross contributions were +1.55 percentage points from fixed income, +0.31 from FX, −0.94 from equity indices, and −0.13 from commodities, using the original asset classifications.

The shared monthly baseline earned +0.23% gross CAGR and −0.42% net CAGR. Its modeled trading and roll costs averaged about 0.66% of equity annually. In the separate frequency experiment, daily trading earned +0.47% gross CAGR, but its roughly 49× annual turnover made its net result particularly sensitive to costs.

Some new monthly closes imply very large moves. As a diagnostic, we reran the shared monthly baseline after capping absolute out-of-sample instrument returns at 20% and 30%, applying the same returns to signal formation and realized P&L. Net CAGR was −0.13% and −0.41%, respectively, compared with −0.42% on the original data. The report uses the original data. The overlap check does not independently validate post-2014 contract construction or missing quotes.

## Reproduce

From the repository root, run the following commands with the uploaded `*_RAD.CSV` files available locally. Use `--data-dir` to point each command at the folder containing those files.

```bash
python rebalance_frequency_out_of_sample.py
python rebalance_frequency_out_of_sample.py --half-short
python net_exposure_out_of_sample.py
python exposure_smoothing_backtest.py
python short_budget_backtest.py
```
