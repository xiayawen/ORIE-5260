"""Daily accounting equivalence, training truncation and feasible budget fits."""
import unittest
import numpy as np
import pandas as pd
from orie5260.portfolio.allocation import DailyAllocationEngine, FIXED, fit_budgets, allocation_utility
from orie5260.execution.costs_and_execution import mark_daily


class SleeveAllocationTests(unittest.TestCase):
    def inputs(self):
        rng=np.random.default_rng(5260)
        dates=pd.bdate_range('2005-01-03',periods=160)
        daily=pd.DataFrame(rng.normal(.0002,.012,(160,3)),index=dates,columns=list('ABC'))
        daily.iloc[18:21,1]=np.nan
        formation=dates[::21]
        basis=rng.normal(0,.3,(len(formation),4,3))
        cov=np.tile(np.diag([.03,.04,.02])[None],(len(formation),1,1))
        return daily,formation,basis,cov

    def test_vectorized_replay_matches_original_marker_including_costs(self):
        daily,dates,basis,cov=self.inputs()
        engine=DailyAllocationEngine(daily,dates,basis,cov)
        schedule=np.tile(FIXED,(len(dates),1));schedule[3:]=[.7,.1,.1,.1]
        for allocation in [FIXED,np.array([.7,.1,.1,.1]),np.array([1.,0.,0.,0.]),schedule]:
            target=engine.targets(allocation)
            original=mark_daily(daily,pd.DataFrame(target,index=dates,columns=daily.columns))
            actual=engine.frame(allocation)
            np.testing.assert_allclose(actual[original.columns].to_numpy(),original.to_numpy(),atol=1e-12)
            self.assertAlmostEqual(actual.gross_return.iloc[0],0.)
            self.assertAlmostEqual(actual.trade_cost.iloc[1],abs(target[0]).sum()*.0002)

    def test_training_fit_is_invariant_to_appended_future_data(self):
        daily,dates,basis,cov=self.inputs();end=daily.index[90]
        first=DailyAllocationEngine(daily,dates,basis,cov,end=end)
        changed=daily.copy();changed.loc[changed.index>end]=.9
        changed_basis=basis.copy();changed_basis[dates>end]*=1000
        other=DailyAllocationEngine(changed,dates,changed_basis,cov,end=end)
        a,fit=fit_budgets(first,'2005-01-03',2.,1.)
        b,_=fit_budgets(other,'2005-01-03',2.,1.)
        np.testing.assert_allclose(a,b,atol=1e-12)
        self.assertLessEqual(first.index.max(),end)
        self.assertAlmostEqual(a.sum(),1.)
        self.assertGreaterEqual(a[0],.3-1e-8)
        self.assertTrue(np.all(a[1:]>=-1e-8))
        self.assertTrue(np.all(a[1:]<=.3+1e-8))
        self.assertGreaterEqual(fit['training_utility'],fit['fixed_utility']-1e-12)

    def test_validation_excludes_a_period_formed_before_fit_was_known(self):
        from orie5260.research.allocation.optimize_daily_budgets import validation_metrics
        daily_dates=pd.bdate_range('2009-12-21','2010-05-20')
        endpoints=pd.to_datetime(['2009-12-21','2010-01-20','2010-02-18','2010-03-19','2010-04-19','2010-05-20'])
        frame=pd.DataFrame({'net_return':np.sin(np.arange(len(daily_dates)))*.001+.0002},index=daily_dates)
        before=validation_metrics(frame,endpoints)
        changed=frame.copy()
        changed.loc[:'2010-01-20','net_return']=.01
        after=validation_metrics(changed,endpoints)
        self.assertEqual(before['periods'],4)
        self.assertAlmostEqual(before['sharpe_zero_rf'],after['sharpe_zero_rf'],places=10)

    def test_cost_and_risk_enter_utility(self):
        daily,dates,basis,cov=self.inputs()
        engine=DailyAllocationEngine(daily,dates,basis,cov)
        start='2005-01-03';b=engine.evaluate(FIXED)
        u=allocation_utility(engine,FIXED,start,2.,1.)
        costly=allocation_utility(engine,FIXED,start,2.,3.)
        risky=allocation_utility(engine,FIXED,start,8.,1.)
        self.assertAlmostEqual(u-costly,2*(b['gross_return']-b['net_return']).mean()*252)
        self.assertAlmostEqual(u-risky,3*b['gross_return'].var(ddof=1)*252)


if __name__=='__main__':unittest.main()
