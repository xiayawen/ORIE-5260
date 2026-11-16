# Combined strategy: in-sample selection, out-of-sample evaluation

**Final combination:** `enhanced + half_short`.

## Protocol

- In-sample (IS) = Jan 1976 - Dec 2014; out-of-sample (OOS) = Jan 2015 - May 2025
  (`MonthlyReturns_FullSample.xlsx`).
- Forward stepwise from `enhanced`: each round adds the candidate with the highest IS net Sharpe if it
  improves the current IS net Sharpe by at least 0.05. Net = Lecture 8 cost model
  (`transaction_cost_model.py`) at $1bn, 5-day impact, drift-adjusted turnover.
- The selection ran on returns truncated at Dec 2014, so no 2015+ value was available to it. The OOS run
  was done once afterwards; the script asserts the IS numbers are identical with and without 2015+ data.
- All component parameters are those fixed in their original scripts on pre-2015 data; nothing was tuned
  here. Each rule is re-implemented on the monthly data and the enhanced construction, not on the
  `economic_trend.py` shared baseline (12-month vol with a 1% floor).
- Pipeline order (fixed in advance): core -> sleeves blended at 20% each and re-targeted to 10% with the
  EWMA covariance (4x gross, 2x scale caps) -> turning point -> half-short -> net cap -> smoothing ->
  4x gross cap -> execution (band_25 or monthly full rebalance).
- Rebalance frequency was not a candidate: weekly/daily trading needs daily closes after 2014, which are
  not available here, so it cannot be tested out of sample.

## Stepwise selection (in-sample only)

| Round | Candidate | IS net Sharpe | Change vs current | Added |
|---:|---|---:|---:|:---:|
| 0 | (start: enhanced) | 1.021 | +0.000 |  |
| 1 | half_short | 1.090 | +0.069 | yes |
| 1 | smooth_leverage | 1.050 | +0.029 |  |
| 1 | smooth_leverage_imbalance | 1.036 | +0.015 |  |
| 1 | band_25 | 1.033 | +0.013 |  |
| 1 | economic_trend | 1.032 | +0.011 |  |
| 1 | turning_point | 1.031 | +0.011 |  |
| 1 | histgb_overlay | 1.021 | +0.000 |  |
| 1 | factor_overlay | 0.950 | -0.071 |  |
| 1 | net_cap | 0.914 | -0.107 |  |
| 1 | risk_budget | 0.771 | -0.250 |  |
| 2 | smooth_leverage | 1.099 | +0.010 |  |
| 2 | turning_point | 1.098 | +0.008 |  |
| 2 | economic_trend | 1.092 | +0.003 |  |
| 2 | smooth_leverage_imbalance | 1.091 | +0.001 |  |
| 2 | histgb_overlay | 1.086 | -0.004 |  |
| 2 | band_25 | 1.072 | -0.018 |  |
| 2 | factor_overlay | 1.038 | -0.052 |  |
| 2 | net_cap | 0.970 | -0.120 |  |
| 2 | risk_budget | 0.833 | -0.257 |  |

Sharpe standard errors are about 0.19 over 39 IS years, so a 0.05 step is not statistically significant
on its own; the threshold only guards against adding near-zero improvements.

## In-sample vs out-of-sample (net of Lecture 8 costs at $1bn unless labelled gross)

Rows other than `baseline`, `enhanced` and `final` are `enhanced` plus that one component.
Turnover is annual drift-adjusted traded notional (x NAV).

| Strategy | IS Net CAGR | OOS Net CAGR | IS Gross ret | OOS Gross ret | IS Net ret | OOS Net ret | IS Vol | OOS Vol | IS Sharpe | OOS Sharpe | IS Max DD | OOS Max DD | IS Turnover | OOS Turnover | IS Cost drag | OOS Cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 9.68% | -1.64% | 10.77% | -0.26% | 9.89% | -1.04% | 11.13% | 11.07% | 0.89 | -0.09 | -26.2% | -33.1% | 8.3 | 13.3 | 0.88% | 0.78% |
| enhanced | 9.59% | -0.33% | 10.53% | 0.52% | 9.63% | -0.09% | 9.44% | 7.06% | 1.02 | -0.01 | -14.2% | -15.0% | 9.6 | 12.8 | 0.90% | 0.60% |
| risk_budget | 7.82% | -0.65% | 10.54% | 1.04% | 8.10% | -0.51% | 10.51% | 5.34% | 0.77 | -0.10 | -13.1% | -15.5% | 25.6 | 33.9 | 2.44% | 1.55% |
| economic_trend | 10.05% | -0.20% | 11.03% | 0.71% | 10.09% | 0.07% | 9.78% | 7.31% | 1.03 | 0.01 | -13.8% | -17.3% | 11.3 | 14.5 | 0.94% | 0.64% |
| factor_overlay | 8.79% | -1.11% | 10.06% | -0.03% | 8.89% | -0.90% | 9.36% | 6.57% | 0.95 | -0.14 | -15.6% | -17.3% | 16.6 | 23.8 | 1.17% | 0.86% |
| turning_point | 9.64% | -0.20% | 10.58% | 0.65% | 9.67% | 0.05% | 9.38% | 7.04% | 1.03 | 0.01 | -14.2% | -14.6% | 9.9 | 13.1 | 0.91% | 0.61% |
| half_short † | 8.76% | 0.55% | 9.37% | 1.12% | 8.74% | 0.68% | 8.02% | 5.16% | 1.09 | 0.13 | -11.5% | -9.5% | 7.3 | 9.6 | 0.63% | 0.44% |
| net_cap | 7.75% | -0.87% | 8.68% | -0.19% | 7.86% | -0.72% | 8.60% | 5.57% | 0.91 | -0.13 | -14.2% | -13.9% | 9.4 | 12.6 | 0.83% | 0.53% |
| smooth_leverage † | 9.82% | -0.37% | 10.69% | 0.47% | 9.84% | -0.12% | 9.37% | 7.07% | 1.05 | -0.02 | -13.8% | -15.7% | 9.0 | 12.3 | 0.85% | 0.59% |
| smooth_leverage_imbalance † | 9.80% | -0.04% | 10.73% | 0.85% | 9.83% | 0.22% | 9.49% | 7.26% | 1.04 | 0.03 | -14.7% | -16.1% | 10.0 | 13.9 | 0.90% | 0.63% |
| band_25 | 8.58% | 0.47% | 9.20% | 1.07% | 8.60% | 0.65% | 8.32% | 6.10% | 1.03 | 0.11 | -12.8% | -10.8% | 6.1 | 8.4 | 0.60% | 0.42% |
| histgb_overlay | 9.58% | 1.02% | 10.58% | 1.92% | 9.62% | 1.22% | 9.43% | 6.52% | 1.02 | 0.19 | -14.2% | -10.9% | 12.2 | 17.5 | 0.96% | 0.69% |
| final † | 8.76% | 0.55% | 9.37% | 1.12% | 8.74% | 0.68% | 8.02% | 5.16% | 1.09 | 0.13 | -11.5% | -9.5% | 7.3 | 9.6 | 0.63% | 0.44% |

† Designed after the 2015-2025 data had been examined (half-short rule, exposure smoothing): their OOS
columns are **not a clean out-of-sample test**. The final combination contains half_short, so its OOS result is not clean either.

## Walk-forward selection

The one-shot selection above fixes the combination once, using all of 1976-2014. As a test of the
selection *procedure*, the same stepwise rule (+0.05 net Sharpe threshold) is rerun at every Dec-31
close on an expanding window from Jan 1976 to that date, and the chosen combination is traded for the next
12 formation months. Switching combinations is traded and charged through the cost model; the no-trade
band applies only in months whose combination includes `band_25`. The window type (expanding), first
traded year (1990) and candidate pools were fixed before any walk-forward result was computed.

- **Clean pool:** risk_budget, economic_trend, factor_overlay, turning_point, net_cap, band_25, histgb_overlay (excludes the rules designed after viewing 2015+ data).
- **All-candidates pool †:** also half_short and the smoothing rules; its 2015+ results are not clean.
- 1990-2014 decisions are causal, but the component designs themselves were developed on data covering
  that period, so it is a pseudo-out-of-sample check; 2015-2025 is the out-of-sample period.
- Blending rule: a sleeve with no positions at a date returns its share to the core, and dates with no
  active sleeve keep the core unchanged. This was corrected after a first walk-forward run showed the
  inactive (pre-1997) HistGB sleeve being "selected" only because its unused 30% share rescaled the
  portfolio. It is a correctness fix (an inactive component must be a no-op), not a tuned parameter, but
  it was made after seeing that run.
- Scores at each decision date use only months up to that date; this relies on truncation invariance,
  verified by `test_lookahead.py`, and the 2015 decision is asserted equal to a selection run on data
  truncated at Dec 2014.

| Strategy | 1990-2014 Net CAGR | OOS Net CAGR | 1990-2014 Gross ret | OOS Gross ret | 1990-2014 Net ret | OOS Net ret | 1990-2014 Vol | OOS Vol | 1990-2014 Sharpe | OOS Sharpe | 1990-2014 Max DD | OOS Max DD | 1990-2014 Turnover | OOS Turnover | 1990-2014 Cost drag | OOS Cost drag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 9.26% | -1.64% | 10.25% | -0.26% | 9.48% | -1.04% | 10.97% | 11.07% | 0.86 | -0.09 | -26.2% | -33.1% | 9.7 | 13.3 | 0.77% | 0.78% |
| enhanced | 8.86% | -0.33% | 9.56% | 0.52% | 8.85% | -0.09% | 8.16% | 7.06% | 1.08 | -0.01 | -9.4% | -15.0% | 10.3 | 12.8 | 0.71% | 0.60% |
| final † | 8.24% | 0.55% | 8.69% | 1.12% | 8.17% | 0.68% | 6.87% | 5.16% | 1.19 | 0.13 | -7.7% | -9.5% | 7.9 | 9.6 | 0.51% | 0.44% |
| walk_forward_clean | 8.35% | -0.33% | 9.12% | 0.52% | 8.38% | -0.09% | 8.21% | 7.06% | 1.02 | -0.01 | -9.4% | -15.0% | 11.3 | 12.8 | 0.74% | 0.60% |
| walk_forward_all † | 8.24% | 0.55% | 8.93% | 1.12% | 8.25% | 0.68% | 7.93% | 5.16% | 1.04 | 0.13 | -9.4% | -9.5% | 10.2 | 9.6 | 0.68% | 0.44% |

| Return year | Clean pool selects | All-candidates pool selects † |
|---:|---|---|
| 1990 | economic_trend | economic_trend + smooth_leverage |
| 1991 | economic_trend | economic_trend + smooth_leverage |
| 1992 | economic_trend | economic_trend + smooth_leverage |
| 1993 | economic_trend | economic_trend + smooth_leverage |
| 1994 | economic_trend | economic_trend + smooth_leverage |
| 1995 | economic_trend | economic_trend + smooth_leverage |
| 1996 | (enhanced only) | half_short |
| 1997 | (enhanced only) | half_short |
| 1998 | (enhanced only) | (enhanced only) |
| 1999 | (enhanced only) | (enhanced only) |
| 2000 | (enhanced only) | (enhanced only) |
| 2001 | (enhanced only) | (enhanced only) |
| 2002 | (enhanced only) | (enhanced only) |
| 2003 | (enhanced only) | (enhanced only) |
| 2004 | economic_trend | economic_trend |
| 2005 | (enhanced only) | half_short |
| 2006 | economic_trend | economic_trend + half_short |
| 2007 | (enhanced only) | half_short |
| 2008 | (enhanced only) | half_short |
| 2009 | (enhanced only) | (enhanced only) |
| 2010 | (enhanced only) | half_short |
| 2011 | (enhanced only) | half_short |
| 2012 | (enhanced only) | half_short |
| 2013 | (enhanced only) | half_short |
| 2014 | (enhanced only) | half_short |
| 2015 | (enhanced only) | half_short |
| 2016 | (enhanced only) | half_short |
| 2017 | (enhanced only) | half_short |
| 2018 | (enhanced only) | half_short |
| 2019 | (enhanced only) | half_short |
| 2020 | (enhanced only) | half_short |
| 2021 | (enhanced only) | half_short |
| 2022 | (enhanced only) | half_short |
| 2023 | (enhanced only) | half_short |
| 2024 | (enhanced only) | half_short |
| 2025 | (enhanced only) | half_short |

![Wealth, IS vs OOS](combined_wealth_is_vs_oos.png)

## Caveats

- **Execution timing.** Main results fill at the signal close while impact costs assume 5-day execution;
  `alpha_decay_execution.py` shows this overstates IS net Sharpe by about 0.07-0.09.
- **Research look-ahead.** The repository had already analysed 2015-2025 for other strategies, so the OOS
  period is strategy-specific OOS, not a pristine holdout. The 58-market universe was chosen with hindsight.
- **Macro data.** FRED current vintages (INDPRO, CPIAUCSL, GS2, BAA10Y) include later revisions that were
  not known in real time. Publication lags: INDPRO and CPI usable one month after the reference month;
  GS2 and BAA10Y monthly averages of daily data, known at month-end.
- **Turning point.** Flags use only trailing 2- and 12-month return sums and the macro vote; no
  smoothing, filtering or ex-post peak/trough dating.
- **HistGB sleeve.** `rolling_sign_prediction.py` model and schedule unchanged (15-year rolling window,
  refit before each return year, labels strictly before the first formation date, forecasts from 1997;
  window and 30% weight chosen on 2000-2004 validation). It is inactive before 1997, so it cannot add
  in-sample Sharpe in 1976-1996. Feature eligibility uses `economic_trend.instrument_vol` as in the
  original; sizing uses EWMA vol like the other sleeves. The most recent formation month is kept for
  forecasting (the original `prepare` drops it because it has no label yet).
- **Costs after 2014.** Daily volume ends Dec 2014, so OOS liquidity uses the asset-class ADV constants.
- **Look-ahead test.** `python -m unittest test_lookahead.py` truncates returns and macro files at 1990-06,
  2014-12 and 2020-03 and checks that the final and all-components pipelines give identical weights and
  costs up to each cut.
