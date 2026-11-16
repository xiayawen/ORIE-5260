"""Tests for the final five-strategy turning-point comparison."""

from __future__ import annotations

import unittest

import pandas as pd

from turning_point_model.final_model import build_final_weights


class FinalModelTests(unittest.TestCase):
    def test_five_strategies_apply_expected_reductions(self):
        dates = pd.date_range("2000-01-31", periods=4, freq="M")
        adjusted = pd.DataFrame({"A": [0.1] * 4}, index=dates)
        targeted = pd.DataFrame({"A": [0.4] * 4}, index=dates)
        disagreement = pd.DataFrame({"A": [False, True, True, True]}, index=dates)
        majority = pd.DataFrame({"A": [False, False, True, True]}, index=dates)
        strict = pd.DataFrame({"A": [False, False, False, True]}, index=dates)
        result = build_final_weights(adjusted, targeted, disagreement, majority, strict)

        self.assertEqual(list(result), [
            "adjusted_baseline",
            "vol_targeted_baseline",
            "unfiltered_method1",
            "majority_vote_method1",
            "four_of_five_method1",
        ])
        self.assertEqual(result["unfiltered_method1"]["A"].tolist(), [0.4, 0.2, 0.2, 0.2])
        self.assertEqual(result["majority_vote_method1"]["A"].tolist(), [0.4, 0.4, 0.2, 0.2])
        self.assertEqual(result["four_of_five_method1"]["A"].tolist(), [0.4, 0.4, 0.4, 0.2])


if __name__ == "__main__":
    unittest.main()
