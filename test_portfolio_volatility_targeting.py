"""Synthetic checks for limits, invalid forecasts and execution timing."""
import unittest

import numpy as np
import pandas as pd

from portfolio_volatility_targeting import target_weights, simulate, TARGET, GROSS_CAP, SCALE_CAP


class TargetingTests(unittest.TestCase):
    def test_target_and_limits(self):
        index = pd.date_range("2000-01-31", periods=4, freq="ME")
        weights = pd.DataFrame({"a": [1., 1., 3., 1.], "b": [-1., -1., -3., -1.]}, index=index)
        forecast = pd.Series([.2, .01, .05, np.nan], index=index)
        scaled, details = target_weights(weights, forecast)
        self.assertAlmostEqual(details.applied_scale.iloc[0], TARGET/.2)
        self.assertAlmostEqual(details.applied_scale.iloc[1], SCALE_CAP)
        self.assertAlmostEqual(scaled.abs().sum(axis=1).iloc[2], GROSS_CAP)
        self.assertTrue(details.invalid_forecast.iloc[3])
        self.assertEqual(scaled.iloc[3].abs().sum(), 0)
        self.assertTrue((scaled.abs().sum(axis=1) <= GROSS_CAP + 1e-12).all())
        self.assertTrue((details.predicted_volatility.dropna() <= TARGET + 1e-12).all())

    def test_execution_lag_and_cost_notional(self):
        weights = pd.DataFrame({"a": [1., -1., .5]})
        returns = pd.DataFrame({"a": [.1, .2, .3]})
        gross, traded, executed = simulate(returns, weights)
        np.testing.assert_allclose(gross, [0, .2, -.3])
        np.testing.assert_allclose(traded, [0, 1, 2])
        changed = weights.copy()
        changed.iloc[-1] = 100
        pd.testing.assert_series_equal(simulate(returns, changed)[0], gross)


if __name__ == "__main__":
    unittest.main()
