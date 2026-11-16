"""Unit tests for the macro-confirmation exposure gate."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from turning_point_model.macro_features import (
    equal_weight_opposition_vote,
    four_of_five_opposition,
    macro_confirmed_binary_weights,
)


class MacroConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2000-01-31", periods=4, freq="M")
        self.baseline = pd.DataFrame({"A": [1.0] * 4}, index=self.dates)
        self.opposition = pd.DataFrame({"A": [False, True, False, True]}, index=self.dates)

    def test_binary_rule_reduces_only_macro_confirmed_turning_points(self):
        turning = pd.DataFrame({"A": [False, True, True, False]}, index=self.dates)
        result = macro_confirmed_binary_weights(
            self.baseline, turning, self.opposition, alpha=0.5
        )
        np.testing.assert_allclose(result["A"], [1.0, 0.5, 1.0, 1.0])

    def test_zero_alpha_reconciles_to_baseline(self):
        turning = pd.DataFrame(True, index=self.dates, columns=["A"])
        result = macro_confirmed_binary_weights(
            self.baseline, turning, self.opposition, alpha=0.0
        )
        pd.testing.assert_frame_equal(result, self.baseline)

    def test_equal_weight_vote_requires_strict_majority(self):
        baseline = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=self.dates[:3])
        directions = {
            "theme_1": pd.DataFrame({"A": [-1.0, -1.0, -1.0]}, index=self.dates[:3]),
            "theme_2": pd.DataFrame({"A": [-1.0, -1.0, 1.0]}, index=self.dates[:3]),
            "theme_3": pd.DataFrame({"A": [-1.0, 1.0, np.nan]}, index=self.dates[:3]),
            "theme_4": pd.DataFrame({"A": [1.0, 1.0, np.nan]}, index=self.dates[:3]),
            "theme_5": pd.DataFrame({"A": [1.0, np.nan, np.nan]}, index=self.dates[:3]),
        }
        result = equal_weight_opposition_vote(directions, baseline)
        np.testing.assert_allclose(result["opposition_vote_share"]["A"], [0.6, 0.5, 0.5])
        self.assertEqual(
            result["macro_vote_opposes_baseline"]["A"].tolist(),
            [True, False, False],
        )

    def test_equal_weight_vote_excludes_ineligible_instruments(self):
        directions = {
            "theme": pd.DataFrame(
                {"A": [-1.0] * 4, "B": [-1.0] * 4}, index=self.dates
            )
        }
        baseline = pd.DataFrame(
            {"A": [1.0] * 4, "B": [1.0] * 4}, index=self.dates
        )
        result = equal_weight_opposition_vote(directions, baseline, ["A"])
        self.assertTrue(result["macro_vote_opposes_baseline"]["A"].all())
        self.assertFalse(result["macro_vote_opposes_baseline"]["B"].any())
        self.assertTrue(result["opposition_vote_share"]["B"].isna().all())

    def test_four_of_five_requires_four_opposing_available_themes(self):
        features = {
            "opposition_vote_count": pd.DataFrame({"A": [3, 4, 4, 5]}, index=self.dates),
            "available_theme_count": pd.DataFrame({"A": [5, 5, 3, 5]}, index=self.dates),
            "macro_vote_eligible": pd.DataFrame({"A": [True, True, True, False]}, index=self.dates),
        }
        result = four_of_five_opposition(features)
        self.assertEqual(result["A"].tolist(), [False, True, False, False])


if __name__ == "__main__":
    unittest.main()
