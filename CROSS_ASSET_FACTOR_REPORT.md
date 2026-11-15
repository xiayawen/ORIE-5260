# Ten cross-asset candidate factors

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 cross_asset_factor_research.py`.
This extends the fixed pre-2015 development / 2015–May2025 comparison design.
There is no rolling classifier refit, new tree hyperparameter search, test
threshold calibration or test-based factor/weight selection.

## Data boundary and research scope

Existing `FuturesUnderlyingData/*.csv` files provide daily OHLC, volume and
open interest through 2014, but the supplied full-sample workbook contains only
monthly returns. Therefore volume/open-interest/liquidity candidates cannot
currently be evaluated consistently after 2014 and are not extrapolated.
Carry and fundamental value would need additional contract-curve/fundamental
data; continuous monthly returns do not identify those quantities.
Research on commodity spot/term premia motivates broadening the data rather
than renaming price signals as carry:
[Szymanowska et al., An Anatomy of Commodity Futures Risk Premia](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.12096).
The ten formulas below are exploratory price-only hypotheses, not reproductions
or empirical validations of that paper.

## Definitions

At each month, form equity, bond, dollar and commodity proxies from eligible
observed instruments in the corresponding mapped asset class, excluding the
target instrument itself. At least three peers must be observed. Dollar is
the negative equal-weight FX futures return. Eurodollar EC is reclassified as
fixed income for these proxies, consistent with the economic-trend script's
static rates-contract correction; original model feature grouping remains
unchanged. These are simple futures proxies, not external market indices.

| Candidate | Higher score / long direction |
| --- | --- |
| LowEquityBeta36 | Negative 36-month beta to equity proxy |
| EquityDownsideHedge60 | Negative beta to equity proxy in negative-equity months |
| LowAbsoluteEquityBeta36 | Negative absolute equity beta |
| LowBondBeta36 | Negative 36-month beta to bond proxy |
| LowDollarBeta36 | Negative 36-month beta to dollar proxy |
| NegativeEquityCoskew60 | Negative standardized third cross-moment with equity |
| EquityLeadResponse60 | Rolling lag-response forecast from equity return |
| BondLeadResponse60 | Rolling lag-response forecast from bond return |
| DollarLeadResponse60 | Rolling lag-response forecast from dollar return |
| CommodityLeadResponse60 | Rolling lag-response forecast from commodity return |

Exposure estimates require 24 paired observations in 36 months. Downside beta
uses 18 negative-equity paired observations in 60 months. Coskewness uses at
least 36 paired observations in 60 months and is
`-[Cov(r,m²)-2*Mean(m)*Cov(r,m)] / [SD(r)*Var(m)]`, using population-moment
conventions. Lag-response coefficients regress r_s on proxy_(s-1) using at
least 36 pairs in 60 months, then multiply by the current proxy minus the
training-window mean lag proxy and divide by own trailing volatility. No
future return fits those coefficients. These rolling feature estimates update
monthly; the final Extra Trees classifier itself remains fixed after 2014.
No factor sign is flipped after seeing a bad result.

## Screening and model comparison

Use the same earliest eligible observations and strict label boundaries as
`fixed_2015_holdout.py`: training labels February1970–November2004, model
validation January2005–November2014, final classifier refit through November2014,
test January2015–May2025. January2008–November2014 selects portfolio configurations
after 2005–2007 live sleeve-risk warmup. December2014 labels never choose or
fit a classifier, though known returns can enter contemporaneous risk estimates.

Training-only class-average Rank IC gate (mean>0, HAC3 t>=1) admits only:

| Signal | Training mean Rank IC | HAC t | Valid months |
| --- | ---: | ---: | ---: |
| NegativeEquityCoskew60 | .0302 | 1.43 | 130 |
| EquityLeadResponse60 | .0243 | 1.12 | 129 |

Each direct candidate is class-ranked and allocated through the native
inverse-volatility/risk-target sleeve construction. Try 10%,20%,30% shares.
Separately compare fixed Extra Trees with the existing 66 features against
86 features (ten new raw scores and ten class-relative ranks added). Both
fit initial training labels, use training-only median imputation, then refit
once on all development labels for later forecasts. The classifier can learn
nonlinear interactions even for features that fail the univariate direct gate;
all ten are included as a predeclared feature-set comparison, not selected on
test IC. Pre-2015 risk history uses the earlier model's out-of-training forecasts.

Select by validation **net portfolio Sharpe**, with no-overlay TSMOM also
available. The winner remains the **existing 66-feature Extra Trees, 30% mix**:
validation Sharpe .9472 versus .9375 for the new 86-feature 30% mix. Extended
features slightly improve validation probability log loss (.68649 vs .68673),
but that is not the declared portfolio selection objective.

## Later-period diagnostic results

| Portfolio | Net annual mean | Net CAGR | Cumulative net return | Net Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original TSMOM | .40% | -.16% | -1.61% | .038 | -24.71% |
| Existing 66-feature 30% classifier mix | .94% | .45% | 4.74% | .094 | -19.43% |
| Extended 86-feature 30% classifier mix | 1.13% | .64% | 6.92% | .114 | -19.04% |
| Best validation direct overlay: coskew10% | .24% | -.30% | -3.07% | .023 | -27.96% |

New features produce only a small descriptive improvement in later trading
results and do not win pre-test portfolio selection. Consequently this study
does not authorize replacing the selected existing-feature strategy. Direct
coskewness fails to improve returns. Extended classifier AUC rises from .5226
to .5264 and accuracy from 52.04% to 52.61%; the probability advantage remains
small (test log loss .69395 vs .69518) and does not establish significant alpha.

## Checks and limitations

Replacing every post-2014 return leaves all ten new pre-2015 signal histories
unchanged. Scores contain no infinities; every proxy explicitly excludes its
target instrument. Strict classifier label boundaries and training-only median
assertions reuse the fixed-holdout helpers. Original 10% target volatility,
2 bps target-weight trading costs, quarterly rolls and missing-held-return zero
treatment remain unchanged; strict common-month sensitivity is exported.

Signals are correlated price-risk proxies, not ten independent risk premia.
Short effective training histories, multiple candidate tests, historic universe,
gross leverage, contract construction and omitted market impact limit inference.
2015–2025 has already been repeatedly inspected. This is a development
comparison on a fixed later interval, not new untouched OOS evidence. Choosing
the extended feature set merely because its later result is better would
violate the declared selection rule.

Outputs under `outputs/cross_asset_factors/`: signal panels, train IC screen,
validation portfolio ranking, feature-set classification metrics, frozen test
probabilities, holdings, net returns, subperiod performance, strict missing-return
sensitivity, config/data audit and P&L chart.
