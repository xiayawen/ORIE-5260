# Alternative factors and models on original TSMOM

Run `OMP_NUM_THREADS=2 MPLCONFIGDIR=/private/tmp/orie-mpl python3 alternative_factor_models.py`.
The primary baseline, monthly execution, volatility targeting and 2 bps
trading/quarterly roll costs reuse `economic_trend.py` unchanged.

## Six additional signals

Within each asset class, each instrument's peer return is the equal-weight mean
of the other observed instruments, requiring at least three peers. Own returns
are excluded. Beta and correlation use trailing 36 paired months, minimum 24.
Missing own returns invalidate the paired peer observation.

| Signal | Higher score means |
| --- | --- |
| LowPeerBeta_36m | Lower beta to same-class peers |
| LowPeerCorrelation_36m | Lower correlation to peers |
| LowResidualVol_12m | Lower trailing 12-month SD of residual returns |
| ResidualMomentum_12m | Higher trailing residual-return sum / residual SD |
| PeerRelativeReversal_1m | Lower most recent own-minus-peer return |
| PeerRelativeMomentum_12m | Higher own-minus-peer return sum over 11 months ending t-1 / own 12-month SD |

Residual return at each month s is r_s - beta_s * peer_s. Beta_s uses only
information through s; it is not re-estimated on the full sample or retroactively
applied to the entire residual path. No intercept is removed, so this is a
transparent beta-adjusted signal, not a claim to exactly reproduce a published
residual-momentum portfolio. Low-peer-beta is not the published leveraged BAB.

## Models and chronology

31 price signals (25 existing + six new) enter the full models. A new-only
variant uses just the six new signals. Features become current-month,
within-class percentile ranks; asset-class indicators are appended. Labels are
next-month within-class raw-return percentile ranks centered at zero, requiring
four observed returns. Training label dates end November 1994, strictly before
the first forecast formation date in December 1994. Imputation uses training
medians only. No random time split is used.

Models: Ridge(alpha=100), random forest(depth6/leaf30/200 trees), Extra Trees
(depth6/leaf30/200 trees), histogram gradient boosting(depth3/8 leaves/100
iterations/leaf100/L2=10/learning rate .05). Seeds are 5260. Boosting early
stopping is disabled to avoid an implicit random validation split. New-only
Ridge and boosting variants are also included. These fixed configurations are
not an exhaustive algorithm search.

Models fit **once before 1995 and remain frozen**. 1995–1997 forecasts are used
only to warm up sleeve risk history. Each model or direct new signal becomes a
class-centered ranked sleeve with original inverse-volatility construction and
10% target volatility. Sleeve scale requires at least 24 actual live monthly
returns in a 36-month window: pre-launch zeros and in-sample predictions cannot
establish its risk estimate. Blend at 10%, 20% or 30%, then apply native blend
scaling. Validation is **1998–2004**; select by net Sharpe including original
TSMOM, a rescaled-only control and the frozen prior negative-skewness overlay.
There are 36 new overlays plus these three controls. Comparison remains the
previously observed 2005–2014 period, not a new pristine holdout.

## Results

Validation selects **70% TSMOM + 30% direct residual momentum** (Sharpe 1.4791).
Fractions refer to sleeve budgets before final risk scaling. Later-period
results (120 months):

| Strategy | Net annual mean | Net volatility | Net Sharpe | Net max drawdown | Mean gross leverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original TSMOM | 9.12% | 10.23% | 0.891 | -10.73% | 4.18 |
| Rescaled-only TSMOM | 9.68% | 10.85% | 0.892 | -12.65% | 4.54 |
| Previous negative-skew 20% mix | 10.21% | 10.77% | 0.948 | -10.48% | 4.30 |
| Selected residual-momentum 30% mix | **11.74%** | **10.63%** | **1.104** | **-9.35%** | **5.32** |

Compared with original TSMOM, selected annual mean rises 2.62 percentage points
and Sharpe rises about 0.21. Gross leverage rises materially, about 27%, despite
similar realized portfolio volatility. This is not a same-leverage comparison;
historical covariance/risk diversification allows more gross positions. Costs
include native rolls but not full market impact, and leverage constraints could
change the result.

Selected mix Sharpe is 1.29 in 2005–2009 versus baseline 0.91; in 2010–2014
it is 0.89 versus baseline 0.88. Thus most risk-adjusted improvement occurs in
the earlier half; it is not equally strong in both regimes.

For each model, the overlay percentage below was selected using validation,
not the comparison period:

| Model sleeve | Validation-selected share | Later net Sharpe |
| --- | ---: | ---: |
| Rank Ridge, all features | 10% | 0.886 |
| Rank random forest, all | 10% | 0.924 |
| Rank Extra Trees, all | 10% | 0.886 |
| Rank gradient boosting, all | 10% | 0.910 |
| Rank Ridge, new only | 10% | 0.907 |
| Rank gradient boosting, new only | 10% | 0.895 |

Complex models do not beat the direct residual-momentum overlay in this
experiment. Frozen 1994 fits may age, so this does not establish that those
algorithms cannot work with a separately validated retraining procedure.

## Checks and limits

Passed checks: perturbing future returns does not alter any of the six new
historical signals or sleeve risk scaling; sleeve weights remain zero until
24 live returns exist; weights are finite. The strict label-date boundary is
asserted in the runner. No in-sample predictions initialize the model sleeve's
risk estimate. Targets use next-month returns only as labels, never as inputs.

Native accounting treats missing held returns as zero. Excluding the same two
affected later-period months for every reported strategy gives baseline Sharpe
0.858 and selected mix 1.067. The qualitative result survives, but the native
zero treatment and direct-weight turnover retain their previously documented
limitations. All factor/model experiments have used an already examined
historical sample. Multiple comparisons, universe construction, execution
timing, roll/impact assumptions and gross leverage remain material limitations.

Outputs in `outputs/alternative_factor_models/` include exact model config,
validation candidates, per-family comparisons, rank IC, instrument predictions,
weights, portfolio returns, subperiod summaries and a cumulative log-net chart.
Do not select a different configuration by mining `all_net_returns_audit.csv`.
