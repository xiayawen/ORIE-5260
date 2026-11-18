"""Pairwise IC, class conditioning and realized-return date alignment."""
import unittest
import numpy as np
import pandas as pd
from orie5260.factors.ic import row_ic,within_class_ic,to_return_date,ic_statistics


class FactorICTests(unittest.TestCase):
    def test_pairwise_missing_values_and_constant_controls(self):
        score=pd.DataFrame([[1.,2.,3.,np.nan],[1.,1.,1.,1.]])
        target=pd.DataFrame([[3.,2.,1.,999.],[1.,2.,3.,4.]])
        p,s,n=row_ic(score,target,minimum=3)
        self.assertAlmostEqual(p.iloc[0],-1.)
        self.assertAlmostEqual(s.iloc[0],-1.)
        self.assertEqual(n.iloc[0],3)
        self.assertTrue(np.isnan(s.iloc[1]))
        self.assertTrue(row_ic(score,target,minimum=4)[1].isna().all())

    def test_class_rank_is_not_a_second_independent_within_class_signal(self):
        cols=list('ABCDEFGH');classes=pd.Series(['X']*4+['Y']*4,index=cols)
        score=pd.DataFrame([[1.,4.,2.,3.,10.,40.,20.,30.]],columns=cols)
        target=pd.DataFrame([[1.,2.,4.,3.,4.,1.,2.,3.]],columns=cols)
        rank=score.copy()
        for _,members in classes.groupby(classes):rank[members.index]=score[members.index].rank(axis=1,pct=True)-.5
        original=within_class_ic(score,target,classes)[1]
        transformed=within_class_ic(rank,target,classes)[1]
        np.testing.assert_allclose(original,transformed)
        flag=pd.DataFrame([[0.]*4+[1.]*4],columns=cols)
        self.assertTrue(within_class_ic(flag,target,classes)[1].isna().all())

    def test_ic_is_attributed_to_next_return_month_not_formation_month(self):
        dates=pd.to_datetime(['2014-11-28','2014-12-31','2015-01-30'])
        scores=pd.Series([.1,.2,.3],index=dates)
        result=to_return_date(scores,dates)
        self.assertEqual(result.index.tolist(),dates[1:].tolist())
        self.assertEqual(result.loc['2015-01-30'],.2)
        self.assertEqual(len(result),2)

    def test_hac_t_matches_bartlett_quadratic_form_and_preserves_direction(self):
        rng=np.random.default_rng(5260)
        values=pd.Series(rng.normal(.04,.1,80))
        centered=values.to_numpy()-values.mean()
        lag=np.abs(np.arange(len(values))[:,None]-np.arange(len(values))[None,:])
        bartlett=np.maximum(1-lag/7,0)
        se=np.sqrt(centered@bartlett@centered/len(values)**2)
        actual=ic_statistics(values)['hac_t6']
        self.assertAlmostEqual(actual,values.mean()/se,places=12)
        self.assertAlmostEqual(ic_statistics(-values)['hac_t6'],-actual,places=12)

    def test_zero_available_months_are_not_reported_as_zero_ic(self):
        result=ic_statistics(pd.Series([np.nan,np.nan]))
        self.assertEqual(result['months'],0)
        self.assertTrue(np.isnan(result['mean_ic']))

if __name__=='__main__':unittest.main()
