"""Uncapped cost-aware execution keeps timing, daily costs and risk feasibility."""
import unittest
import numpy as np
import pandas as pd
from optimize_ict42_portfolio import replay
from sleeve_allocation import DailyAllocationEngine,FIXED
from data_utils import period_returns
from costs_and_execution import mark_daily


class ICT42ExecutionTests(unittest.TestCase):
    def inputs(self):
        rng=np.random.default_rng(5260)
        daily=pd.DataFrame(rng.normal(.0002,.008,(120,3)),index=pd.bdate_range('2005-01-03',periods=120),columns=list('ABC'))
        dates=daily.index[::21]
        basis=rng.normal(0,.3,(len(dates),4,3))
        cov=np.tile(np.diag([.04,.03,.02])[None],(len(dates),1,1))
        eligible=np.ones((len(dates),3),bool)
        forward=period_returns(daily,dates).fillna(0).to_numpy()
        return daily,dates,basis,cov,eligible,forward

    def test_actual_execution_reconciles_with_daily_marker_and_has_no_gross_cap(self):
        daily,dates,basis,cov,eligible,forward=self.inputs()
        # Very low variance makes a risk-feasible book exceed4x gross.
        cov=cov*.01
        daily=daily*.1
        forward=period_returns(daily,dates).fillna(0).to_numpy()
        engine=DailyAllocationEngine(daily,dates,basis,cov)
        actual,frame,_=replay(engine,FIXED,20.,forward,eligible)
        marked=mark_daily(daily,pd.DataFrame(actual,index=dates,columns=daily.columns))
        np.testing.assert_allclose(frame[marked.columns].to_numpy(),marked.to_numpy(),atol=1e-12)
        self.assertGreater(np.abs(actual).sum(axis=1).max(),4.)
        sigma=np.sqrt(np.einsum('ti,tij,tj->t',actual,cov,actual))
        self.assertLessEqual(sigma.max(),.1+1e-12)

    def test_future_changes_do_not_change_old_decisions_and_exits_are_forced(self):
        daily,dates,basis,cov,eligible,forward=self.inputs()
        eligible[-1,0]=False;basis[-1,:,0]=0
        engine=DailyAllocationEngine(daily,dates,basis,cov)
        actual,_,_=replay(engine,FIXED,5.,forward,eligible)
        self.assertAlmostEqual(actual[-1,0],0.)
        changed=daily.copy();changed.iloc[70:]*=-3
        other_basis=basis.copy();other_basis[4:]*=-1
        changed_engine=DailyAllocationEngine(changed,dates,other_basis,cov)
        other,_,_=replay(changed_engine,FIXED,5.,period_returns(changed,dates).fillna(0).to_numpy(),eligible)
        np.testing.assert_allclose(actual[:4],other[:4],atol=1e-12)

if __name__=='__main__':unittest.main()
