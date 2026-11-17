"""Causal fitting and integration invariants for optional Extra Trees sleeves."""
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from combined_strategy import Pipeline,COMPONENTS,CLEAN_POOL,OPTIONAL_COMPONENTS
from combined_factor_models import extratrees_forecasts
from risk_budgeting import ROOT,read_full_sample_returns


class IntegrationTests(unittest.TestCase):
    def test_optional_models_do_not_change_original_search_pool(self):
        self.assertFalse(set(OPTIONAL_COMPONENTS)&set(COMPONENTS))
        self.assertFalse(set(OPTIONAL_COMPONENTS)&set(CLEAN_POOL))

    def test_alternative_models_cannot_be_stacked(self):
        pipe=object.__new__(Pipeline)
        for config in [set(OPTIONAL_COMPONENTS),{"histgb_overlay","extratrees_overlay"}]:
            with self.assertRaises(ValueError):pipe.targeted(config)

    def test_inactive_model_is_exact_noop(self):
        pipe=object.__new__(Pipeline)
        pipe._cache={}
        core=pd.DataFrame([[.4,-.2],[.3,-.1]],columns=["a","b"])
        pipe.core=lambda *args:core
        pipe.extratrees_sleeve=lambda *args:core*0
        pipe.retarget=lambda w:w*2
        actual=pipe.targeted({"continuous_signal","extratrees_overlay"})
        pd.testing.assert_frame_equal(actual,core)

    def test_future_data_cannot_change_old_forecasts_or_fits(self):
        source=ROOT/"MonthlyReturns_FullSample.xlsx"
        if not source.exists():source=ROOT/"data"/"MonthlyReturns_FullSample.xlsx"
        r=read_full_sample_returns(source)
        full,audit=extratrees_forecasts(r)
        old,old_audit=extratrees_forecasts(r.loc[:"2014-12-31"])
        for name in full:
            # Padding makes even the terminal Dec2014 inference row comparable.
            self.assertTrue(np.allclose(full[name].loc[old[name].index],old[name],equal_nan=True),name)
            self.assertTrue(full[name].loc[:"2004-11-30"].isna().all().all())
            latest=full[name].iloc[-1]
            self.assertGreater(latest.notna().sum(),0)
            values=full[name].stack()
            self.assertTrue(values.between(0,1).all())
        self.assertEqual(len(audit),4)
        self.assertTrue((pd.to_datetime(audit.last_training_label)<pd.to_datetime(audit.first_formation)).all())
        for name in ["Existing66","Extended86"]:
            a=audit.loc[(audit.features==name)&(audit.phase=="fixed_post2014")].iloc[0]
            b=old_audit.loc[(old_audit.features==name)&(old_audit.phase=="fixed_post2014")].iloc[0]
            self.assertEqual(a.training_rows,b.training_rows)
            self.assertEqual(a.feature_count,66 if name=="Existing66" else 86)


if __name__=="__main__":unittest.main()
