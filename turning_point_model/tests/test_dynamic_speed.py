import unittest

import numpy as np
import pandas as pd

from turning_point_model.dynamic_speed import (
    dynamic_speed_direction,
    fit_frozen_mixing_parameters,
    momentum_states,
)


class DynamicSpeedTests(unittest.TestCase):
    def test_states_and_blend(self):
        dates = pd.date_range("2000-01-31", periods=16, freq=pd.offsets.MonthEnd())
        returns = pd.DataFrame({"A": [0.01] * 12 + [-0.10, -0.10, 0.20, 0.20]}, index=dates)
        state, slow, fast = momentum_states(returns)
        self.assertEqual(state.iloc[12, 0], "Correction")
        params = pd.DataFrame(
            {"correction_fast_weight": [0.75], "rebound_fast_weight": [0.25]}, index=["A"]
        )
        direction = dynamic_speed_direction(returns, params)
        expected = 0.25 * slow.iloc[12, 0] + 0.75 * fast.iloc[12, 0]
        self.assertAlmostEqual(direction.iloc[12, 0], expected)

    def test_training_cutoff_blocks_future_changes(self):
        rng = np.random.default_rng(5260)
        dates = pd.date_range("1980-01-31", periods=360, freq=pd.offsets.MonthEnd())
        returns = pd.DataFrame({"A": rng.normal(0, 0.04, len(dates))}, index=dates)
        first = fit_frozen_mixing_parameters(returns, "2004-12-31", minimum_state_observations=2)
        changed = returns.copy()
        changed.loc["2005-01-01":, "A"] = 10.0
        second = fit_frozen_mixing_parameters(changed, "2004-12-31", minimum_state_observations=2)
        pd.testing.assert_frame_equal(first, second)


if __name__ == "__main__":
    unittest.main()
