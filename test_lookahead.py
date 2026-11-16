"""Empirical look-ahead test: truncation invariance.

If a strategy uses only information available at each formation date, the
weights formed on or before date T must be identical whether the backtest is run
on data ending at T or on the full 1969-2025 sample. Any difference means some
input at T depends on data after T. Covers signals, expanding/EWMA volatility,
covariance forecasts, volatility targeting, risk budgeting and the Lecture 8 cost
model (including its trailing-volume liquidity input).

    python -m unittest test_lookahead.py
"""

import unittest

import numpy as np

from risk_budget_backtest import build_all
from risk_budgeting import read_full_sample_returns
from strategy_backtest_adj import read_asset_map
from transaction_cost_model import (
    DEFAULT_PARAMETERS, trailing_contract_volume, instrument_adv_usd, cost_breakdown,
)
from portfolio_volatility_targeting import simulate, GROSS_CAP
from cost_aware_rebalance import rebalance_path, RULES

CUTS = ("1990-06-29", "2014-12-31", "2020-03-31")


class TruncationInvariance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.returns, cls.asset_map = read_full_sample_returns(), read_asset_map()
        cls.full = build_all(cls.returns, cls.asset_map)

    def test_weights_and_costs_do_not_use_future_data(self):
        full_strategies, _, full_vol, asset_class = self.full
        for cut in CUTS:
            short = self.returns.loc[:cut]
            strategies, _, vol, _ = build_all(short, self.asset_map)
            self.assertTrue(np.allclose(vol.to_numpy(), full_vol.loc[short.index].to_numpy(), equal_nan=True))
            for name, weights in strategies.items():
                with self.subTest(cut=cut, strategy=name):
                    np.testing.assert_allclose(weights.to_numpy(), full_strategies[name].loc[short.index].to_numpy(),
                                               atol=1e-10, err_msg=f"{name} changes when data after {cut} is added")
            for label, data, w, sigma in (("short", short, strategies["rb_class"], vol),
                                          ("full", self.returns, full_strategies["rb_class"], full_vol)):
                volume = trailing_contract_volume(data.index, data.columns)
                adv, _ = instrument_adv_usd(volume, asset_class, DEFAULT_PARAMETERS)
                _, _, executed = simulate(data, w)
                cost, _ = cost_breakdown(executed, sigma, adv, asset_class, DEFAULT_PARAMETERS, data)
                if label == "short":
                    short_cost = cost.total
                else:
                    np.testing.assert_allclose(short_cost.to_numpy(), cost.total.loc[short.index].to_numpy(), atol=1e-12)

    def test_rebalancing_rules_do_not_use_future_data(self):
        full_strategies = self.full[0]
        cut = "2014-12-31"
        short = self.returns.loc[:cut]
        for name in ("baseline", "enhanced", "rb_class"):
            for rule_name, rule in RULES.items():
                with self.subTest(strategy=name, rule=rule_name):
                    formed = full_strategies[name]
                    full_path = rebalance_path(formed, self.returns, rule, GROSS_CAP)
                    short_path = rebalance_path(formed.loc[short.index], short, rule, GROSS_CAP)
                    np.testing.assert_allclose(short_path.to_numpy(), full_path.loc[short.index].to_numpy(), atol=1e-12)

    def test_execution_lag(self):
        strategies = self.full[0]
        for name, formed in strategies.items():
            _, _, executed = simulate(self.returns, formed)
            np.testing.assert_allclose(executed.iloc[1:].to_numpy(), formed.iloc[:-1].fillna(0).to_numpy())


class CombinedStrategyTruncation(unittest.TestCase):
    """combined_strategy.py: returns AND macro files cut at each date must not change any earlier
    formation weight, executed weight or Lecture 8 cost. Covers every candidate component (the
    all-components configuration) and the selected final combination."""

    @classmethod
    def setUpClass(cls):
        import json
        from combined_strategy import Pipeline, ALL_COMPONENTS, OUT
        cls.Pipeline = Pipeline
        cls.returns, cls.asset_map = read_full_sample_returns(), read_asset_map()
        selected = json.loads((OUT / "selected_components.json").read_text())["selected"]
        cls.configs = {"final": frozenset(selected), "all_components": ALL_COMPONENTS}
        cls.full = Pipeline(cls.returns, cls.asset_map)

    def test_combined_pipeline_is_truncation_invariant(self):
        import tempfile
        from pathlib import Path
        import pandas as pd
        from combined_strategy import MACRO_DIR
        for cut in CUTS:
            with tempfile.TemporaryDirectory() as tmp:
                for path in MACRO_DIR.glob("*.csv"):  # macro data as it existed up to the cut
                    frame = pd.read_csv(path)
                    frame[pd.to_datetime(frame.iloc[:, 0]) <= pd.Timestamp(cut)].to_csv(Path(tmp) / path.name, index=False)
                short = self.Pipeline(self.returns.loc[:cut], self.asset_map, Path(tmp))
                for name, config in self.configs.items():
                    with self.subTest(cut=cut, config=name):
                        idx = short.r.index
                        np.testing.assert_allclose(short.formed(config).to_numpy(),
                                                   self.full.formed(config).loc[idx].to_numpy(), atol=1e-10)
                        np.testing.assert_allclose(short.executed(config).to_numpy(),
                                                   self.full.executed(config).loc[idx].to_numpy(), atol=1e-10)
                        np.testing.assert_allclose(short.run(config).to_numpy(),
                                                   self.full.run(config).loc[idx].to_numpy(), atol=1e-10)


if __name__ == "__main__":
    unittest.main()
