"""Small timing and portfolio-constraint checks for the submitted pipeline."""
import unittest

import numpy as np
import pandas as pd

from costs_and_execution import mark_daily
from daily_baseline import construct_signal
from portfolio_engine import constrain
from risk_model import LIMITS


class FinalStrategyTests(unittest.TestCase):
    def test_baseline_signal_uses_trailing_daily_returns(self):
        dates = pd.bdate_range("2020-01-01", periods=253)
        daily = pd.DataFrame({"A": [.001] * 252 + [-.40]}, index=dates)
        signal, volatility = construct_signal(daily, dates[-2:])
        self.assertEqual(signal.loc[dates[-2], "A"], 1)
        self.assertEqual(signal.loc[dates[-1], "A"], -1)
        self.assertGreater(volatility.loc[dates[-1], "A"], 0)

    def test_close_formation_starts_next_day(self):
        dates = pd.bdate_range("2020-01-01", periods=4)
        daily = pd.DataFrame({"A": [.05, .10, 0, 0]}, index=dates)
        weights = pd.DataFrame({"A": [1, 1]}, index=[dates[0], dates[-1]])
        marked = mark_daily(daily, weights)
        self.assertAlmostEqual(marked.loc[dates[0], "gross_return"], 0)
        self.assertAlmostEqual(marked.loc[dates[1], "gross_return"], .10)

    def test_common_risk_limits(self):
        raw = np.array([[3., 2., -1.]])
        covariance = np.eye(3)[None] * .01
        groups = [np.array([True, True, False]), np.array([False, False, True])]
        weights = constrain(raw, covariance, groups, LIMITS)
        self.assertLessEqual(np.abs(weights).sum(), LIMITS.gross + 1e-10)
        self.assertLessEqual(abs(weights.sum()), LIMITS.net + 1e-10)
        self.assertLessEqual(float(np.sqrt(weights[0] @ covariance[0] @ weights[0])), LIMITS.volatility + 1e-10)


if __name__ == "__main__":
    unittest.main()
