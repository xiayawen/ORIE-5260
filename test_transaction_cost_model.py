"""Synthetic checks for the Lecture 8 cost model: units, timing and scaling."""
import unittest

import numpy as np
import pandas as pd

from transaction_cost_model import (
    CostParameters, cost_breakdown, instrument_adv_usd, rolls_per_year, trade_weights, TRADING_DAYS,
)


def frames(executed, vol=0.16, adv=1e9):
    idx, cols = executed.index, executed.columns
    return (pd.DataFrame(vol, index=idx, columns=cols), pd.DataFrame(adv, index=idx, columns=cols),
            pd.Series("EQ", index=cols))


class CostModelTests(unittest.TestCase):
    def setUp(self):
        idx = pd.date_range("2000-01-31", periods=4, freq="ME")
        self.executed = pd.DataFrame({"a": [0., 1., 1., -1.]}, index=idx)
        self.params = CostParameters(commission_bps=1, roll_bps=1, rolls_per_year={"EQ": 12},
                                     half_spread_bps={"EQ": 1}, impact_coefficient=0.5,
                                     margin_rate={"EQ": 0.05}, aum_usd=1e8,
                                     execution_days=1, turnover="target")

    def test_components_in_return_units(self):
        vol, adv, cls = frames(self.executed)
        monthly, _ = cost_breakdown(self.executed, vol, adv, cls, self.params)
        np.testing.assert_allclose(monthly.turnover, [0, 1, 0, 2])
        np.testing.assert_allclose(monthly.commission, [0, 1e-4, 0, 2e-4])
        np.testing.assert_allclose(monthly.half_spread, monthly.commission)
        np.testing.assert_allclose(monthly.roll, [0, 1e-4, 1e-4, 1e-4])  # held positions roll even with no trade
        expected = 0.5 * 0.16 / np.sqrt(TRADING_DAYS) * np.sqrt(2 * 1e8 / 1e9) * 2
        self.assertAlmostEqual(monthly.market_impact.iloc[3], expected)
        self.assertEqual(monthly.financing.sum(), 0)

    def test_impact_scales_with_square_root_of_aum(self):
        vol, adv, cls = frames(self.executed)
        small, _ = cost_breakdown(self.executed, vol, adv, cls, self.params)
        large, _ = cost_breakdown(self.executed, vol, adv, cls, self.params.with_aum(4e8))
        np.testing.assert_allclose(large.market_impact, 2 * small.market_impact)
        np.testing.assert_allclose(large.commission, small.commission)

    def test_uses_formation_date_information_only(self):
        vol, adv, cls = frames(self.executed)
        base, _ = cost_breakdown(self.executed, vol, adv, cls, self.params)
        vol_changed = vol.copy()
        vol_changed.iloc[-1] = 10.0  # last formation date: affects no trade inside the sample
        later, _ = cost_breakdown(self.executed, vol_changed, adv, cls, self.params)
        pd.testing.assert_frame_equal(base, later)
        vol_changed.iloc[2] = 0.32  # formation for month 4's trade
        doubled, _ = cost_breakdown(self.executed, vol_changed, adv, cls, self.params)
        self.assertAlmostEqual(doubled.market_impact.iloc[3], 2 * base.market_impact.iloc[3])

    def test_financing_only_on_margin_shortfall(self):
        levered = self.executed * 30  # 30x gross at 5% margin = 150% of equity
        vol, adv, cls = frames(levered)
        monthly, _ = cost_breakdown(levered, vol, adv, cls, self.params)
        np.testing.assert_allclose(monthly.margin_to_equity, [0, 1.5, 1.5, 1.5])
        np.testing.assert_allclose(monthly.financing.iloc[1:], 0.5 * 50e-4 / 12)

    def test_drift_turnover_by_hand(self):
        idx = self.executed.index
        returns = pd.DataFrame({"a": [0.0, 0.10, 0.0, 0.0], "b": [0.0, 0.0, 0.0, 0.0]}, index=idx)
        w = pd.DataFrame({"a": [0., 0.5, 0.5, 0.5], "b": [0., 0.5, 0.5, 0.5]}, index=idx)
        trade = trade_weights(w, returns, "drift")
        # month 2: a +10%, portfolio +5% -> a drifted to 0.55/1.05, rebalance back to 0.5
        self.assertAlmostEqual(trade.loc[idx[2], "a"], abs(0.5 - 0.55 / 1.05))
        self.assertAlmostEqual(trade.loc[idx[2], "b"], abs(0.5 - 0.50 / 1.05))
        self.assertEqual(trade.loc[idx[3]].sum(), 0.0)
        pd.testing.assert_frame_equal(trade_weights(w, None, "drift"), trade_weights(w, returns, "target"))

    def test_drift_uses_only_past_returns(self):
        rng = np.random.default_rng(0)
        idx = pd.date_range("1990-01-31", periods=40, freq="ME")
        w = pd.DataFrame(rng.normal(0, .5, (40, 3)), index=idx)
        r = pd.DataFrame(rng.normal(0, .05, (40, 3)), index=idx)
        r2 = r.copy(); r2.iloc[30:] = 0.9
        pd.testing.assert_frame_equal(trade_weights(w, r).iloc[:31], trade_weights(w, r2).iloc[:31])

    def test_instrument_roll_cycle_overrides_class(self):
        params = CostParameters(roll_bps=1)
        cls = pd.Series({"ZU": "COMM", "ZC": "COMM", "XYZ": "COMM"})
        self.assertEqual(rolls_per_year(cls.index, cls, params).tolist(), [12, 5, 6])

    def test_execution_days_lower_impact(self):
        vol, adv, cls = frames(self.executed)
        one, _ = cost_breakdown(self.executed, vol, adv, cls, self.params)
        five, _ = cost_breakdown(self.executed, vol, adv, cls, self.params.replace(execution_days=5))
        np.testing.assert_allclose(five.market_impact, one.market_impact / np.sqrt(5))

    def test_illiquid_flag_cuts_adv(self):
        volume = pd.DataFrame({"a": [500., 5000., np.nan]})
        adv, flag = instrument_adv_usd(volume, pd.Series({"a": "COMM"}), CostParameters())
        np.testing.assert_allclose(adv.a, [1e8, 1e9, 1e9])
        self.assertEqual(flag.a.tolist(), [True, False, False])


if __name__ == "__main__":
    unittest.main()
