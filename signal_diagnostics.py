# Signal diagnostics
#
# Purpose
# -------
# This script will evaluate whether past futures returns contain useful information
# about subsequent monthly returns before the project changes the baseline portfolio
# construction. It will cover both return autocorrelation and direct tests of the
# time-series momentum signals used by the strategy.
#
# Planned analysis
# ----------------
# 1. Calculate monthly return autocorrelation at lags 1 through 12.
# 2. Calculate autocorrelation of absolute and squared monthly returns to examine
#    volatility persistence.
# 3. Report autocorrelation results by instrument, asset class, and time period.
# 4. Construct 1-, 3-, 6-, and 12-month momentum signals using the same timing and
#    signal definitions as the baseline strategy.
# 5. Measure the next-month return following positive and negative signals.
# 6. Calculate the positive-signal minus negative-signal return spread.
# 7. Calculate directional hit rates at the instrument-month level.
# 8. Report signal results by lookback, instrument, asset class, and time period.
#
# Expected inputs
# ---------------
# - MonthlyReturns.csv
#     Monthly returns for the futures universe.
# - AssetMapCsv.csv
#     Instrument names and asset-class classifications.
# - strategy_backtest_adj.py
#     Shared data-loading and momentum-signal definitions, so diagnostics use the
#     same lookback construction and timing as the adjusted baseline.
#
# Expected outputs
# ----------------
# All outputs will be written to outputs/signal_diagnostics_output/.
#
# Planned tables:
# - return_autocorrelation_by_instrument.csv
# - return_autocorrelation_by_asset_class.csv
# - volatility_autocorrelation.csv
# - autocorrelation_by_period.csv
# - signal_predictiveness_by_instrument.csv
# - signal_predictiveness_by_asset_class.csv
# - signal_predictiveness_by_lookback.csv
# - signal_predictiveness_by_period.csv
# - directional_hit_rates.csv
#
# Planned figures:
# - return_autocorrelation_lags.png
# - volatility_autocorrelation_lags.png
# - signal_return_spread_by_lookback.png
# - signal_hit_rate_by_asset_class.png
# - signal_predictiveness_by_period.png
#
# Implementation status
# ---------------------
# Documentation stub only. No analysis code has been implemented yet.
