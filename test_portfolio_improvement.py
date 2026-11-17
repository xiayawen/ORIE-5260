"""Regression checks for reversal execution and pre-2015 selection scoring."""
import unittest
import numpy as np
import pandas as pd
from improve_combined_portfolio import adaptive_execution, fold_score
from unified_portfolio import Limits, constrain

class ImprovementTests(unittest.TestCase):
    def inputs(self):
        return dict(r=pd.DataFrame(np.zeros((8,2))),cov=np.tile(np.eye(2)[None,:,:]*.04,(8,1,1)),
            groups=[np.array([True,False]),np.array([False,True])],eligible=np.ones((8,2),bool),limits=Limits())

    def test_future_returns_and_targets_cannot_change_past_holdings(self):
        inp=self.inputs();target=np.tile([.2,-.2],(8,1));target[4:]*=-1
        actual,b=adaptive_execution(target,inp)
        changed=self.inputs();changed['r'].iloc[6:]=.1
        changed_target=target.copy();changed_target[6:]=0
        other,_=adaptive_execution(changed_target,changed)
        np.testing.assert_allclose(actual[:6],other[:6])
        np.testing.assert_array_equal(b['executed'][1:],actual[:-1])
        self.assertEqual(b['rapid'][4],1)
        np.testing.assert_allclose(actual[4],target[4])

    def test_eligibility_exits_are_forced_and_limits_hold(self):
        inp=self.inputs();inp['eligible'][5:,0]=False
        target=np.tile([.2,-.2],(8,1));target[5:,0]=0
        actual,_=adaptive_execution(target,inp)
        np.testing.assert_array_equal(actual[5:,0],0)
        for t,w in enumerate(actual):
            repaired=constrain(w,inp['cov'][t],inp['groups'],inp['limits'])
            # constrain may increase a small feasible portfolio: directly test bounds.
            self.assertLessEqual(np.abs(w).sum(),4+1e-12)
            self.assertLessEqual(abs(w.sum()),1+1e-12)
            self.assertLessEqual(w@inp['cov'][t]@w,.01+1e-12)

    def test_selection_score_ignores_post2014(self):
        dates=pd.date_range('2004-12-31','2016-12-31',freq='ME');n=len(dates)
        net=.002+.01*np.sin(np.arange(n));b=dict(net=net,roll_cost=np.ones(n)*.0001,
            trade_cost=np.ones(n)*.0001,turnover=np.ones(n),gross_exposure=np.ones(n),net_exposure=np.zeros(n))
        before=fold_score(b,dates)
        for key in b:b[key]=b[key].copy();b[key][dates>='2014-12-01']=.9
        self.assertEqual(before,fold_score(b,dates))

if __name__=='__main__':unittest.main()
