"""IC screens may use only labels known before first prediction formation."""
import unittest
import numpy as np
import pandas as pd
from orie5260.models.ic_feature_filter import select_inputs,feature_frames,panel


class ICFeatureFilterTests(unittest.TestCase):
    def inputs(self):
        rng=np.random.default_rng(5260)
        dates=pd.date_range('1975-01-31',periods=108,freq='ME')
        cols=[f'A{i}' for i in range(16)]
        r=pd.DataFrame(rng.normal(.002,.03,(108,16)),index=dates,columns=cols)
        classes=pd.Series(np.repeat(['EQ','FI','FX','CO'],4),index=cols)
        return r,classes

    def test_future_returns_cannot_change_train_screen(self):
        r,classes=self.inputs();boundary=r.index[83]
        selected,table=select_inputs(r,classes,boundary)
        altered=r.copy();altered.loc[altered.index>=boundary]*=-10
        other,other_table=select_inputs(altered,classes,boundary)
        self.assertEqual(selected,other)
        pd.testing.assert_frame_equal(table,other_table)

    def test_class_controls_are_retained_and_feature_count_is_exact(self):
        r,classes=self.inputs()
        frames,_=feature_frames(r,classes)
        self.assertEqual(len(frames),66)
        selected,table=select_inputs(r,classes,r.index[-1],threshold=1.1)
        self.assertEqual(len(selected),4)
        self.assertTrue(all(n.startswith('class_') for n in selected))
        self.assertEqual(int(table.keep.sum()),4)

    def test_hac_screen_is_a_subset_of_ic_only_screen_and_is_causal(self):
        r,classes=self.inputs();boundary=r.index[83]
        ic_only,_=select_inputs(r,classes,boundary)
        selected,table=select_inputs(r,classes,boundary,min_abs_t=1.96)
        self.assertTrue(set(selected).issubset(ic_only))
        numeric=table.loc[table.keep & ~table.feature.str.startswith('class_')]
        self.assertTrue((numeric.mean_train_rank_ic.abs()>=.01).all())
        self.assertTrue((numeric.direction*numeric.hac_t6>=1.96).all())
        altered=r.copy();altered.loc[altered.index>=boundary]*=-10
        other,other_table=select_inputs(altered,classes,boundary,min_abs_t=1.96)
        self.assertEqual(selected,other)
        pd.testing.assert_frame_equal(table,other_table)

    def test_panel_target_is_next_return_and_last_unobserved_label_is_excluded(self):
        r,classes=self.inputs();x,target,return_date=panel(r,classes)
        self.assertLess(x.index.get_level_values('formation_date').max(),r.index[-1])
        formation,instrument=x.index[-1]
        later=r.index[r.index.get_loc(formation)+1]
        self.assertEqual(return_date.iloc[-1],later)
        self.assertAlmostEqual(target.iloc[-1],r.loc[later,instrument])

if __name__=='__main__':unittest.main()
