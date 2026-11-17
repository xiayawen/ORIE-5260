"""Feasibility, accounting, execution optimality and causality checks."""
import unittest
import numpy as np
from unified_portfolio import Limits,constrain,blended_target,rebalance_metrics,fit_allocation,optimal_trade_fraction,cost_aware_path


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.cov=np.diag([.04,.09,.01,.16])
        self.groups=[np.eye(4,dtype=bool)[j] for j in range(4)]
        self.limits=Limits()

    def check_feasible(self,w):
        self.assertLessEqual(np.abs(w).sum(),4+1e-10)
        self.assertLessEqual(abs(w.sum()),1+1e-10)
        self.assertLessEqual(w@self.cov@w,.01+1e-10)
        for g in self.groups:
            v=w*g;self.assertLessEqual(v@self.cov@v,.0025+1e-10)

    def test_all_limits_simultaneous_and_convex(self):
        a=constrain(np.array([3.,-2.,4.,-5.]),self.cov,self.groups)
        b=constrain(np.array([-1.,2.,-.1,3.]),self.cov,self.groups)
        for u in np.linspace(0,1,21):self.check_feasible(a*u+(1-u)*b)
        np.testing.assert_array_equal(constrain(np.zeros(4),self.cov,self.groups),0)

    def test_execution_lag_and_entry_cost(self):
        formed=np.array([[.2,0],[.1,0],[0,0]])
        r=np.array([[.9,0],[.1,0],[.2,0]])
        b=rebalance_metrics(formed,r)
        np.testing.assert_allclose(b['gross'],[0,.02,.02])
        self.assertAlmostEqual(b['trade_cost'][1],.2*.0002)
        self.assertAlmostEqual(b['roll_cost'][1],.2*.0002*4/12)

    def test_netted_positions_do_not_double_charge_sleeves(self):
        cov=np.repeat(np.eye(2)[None,:,:]*.01,3,axis=0)
        basis=np.zeros((3,4,2));basis[:,0,0]=1;basis[:,1,0]=-1
        target=blended_target(basis,np.array([.5,.5,0,0]),cov,[np.array([True,False]),np.array([False,True])])
        b=rebalance_metrics(target,np.ones((3,2))*.1)
        self.assertTrue((b['trade_cost']==0).all())
        self.assertTrue((b['roll_cost']==0).all())

    def test_fraction_is_at_least_as_good_as_dense_grid(self):
        base=np.array([.10,-.04,.1,-.03]);target=np.array([-.10,.05,.05,.02])
        drift=base*1.1;gamma=5.
        u=optimal_trade_fraction(base,target,drift,self.cov,gamma)
        def objective(z):
            w=base+z*(target-base);d=w-target
            return gamma/24*(d@self.cov@d)+.0002*np.abs(w-drift).sum()+.0002*4/12*np.abs(w).sum()
        self.assertLessEqual(objective(u),min(objective(z) for z in np.linspace(0,1,1001))+1e-12)

    def test_cost_aware_path_causal_and_feasible(self):
        rng=np.random.default_rng(5260);n=12
        cov=np.repeat(self.cov[None,:,:],n,axis=0)
        target=constrain(rng.normal(size=(n,4)),cov,self.groups)
        r=rng.normal(0,.01,size=(n,4));eligible=np.ones_like(r,dtype=bool)
        a,_=cost_aware_path(target,cov,r,self.groups,eligible,5.)
        changed_r=r.copy();changed_r[6:]=.2
        changed_target=target.copy();changed_target[6:]*=-1
        b,_=cost_aware_path(changed_target,cov,changed_r,self.groups,eligible,5.)
        np.testing.assert_allclose(a[:6],b[:6])
        for row in a:self.check_feasible(row)
        stopped=eligible.copy();stopped[5:,1]=False
        t=target.copy();t[5:,1]=0
        actual,_=cost_aware_path(t,cov,r,self.groups,stopped,5.)
        self.assertTrue((actual[5:,1]==0).all())

    def test_allocation_respects_bounds_and_incumbent_utility(self):
        n=30;cov=np.repeat(self.cov[None,:,:],n,axis=0)
        basis=np.tile(np.array([[.2,-.1,.3,-.1],[.1,-.1,.2,-.05],[-.1,.05,.1,.1],[.05,-.02,.2,.02]]),(n,1,1))
        returns=np.tile([.01,-.002,.005,-.003],(n,1))
        mask=np.arange(n)>=2
        a,audit=fit_allocation(basis,cov,returns,self.groups,mask,2,1)
        self.assertAlmostEqual(a.sum(),1,places=7)
        self.assertGreaterEqual(a[0],.3-1e-8)
        self.assertTrue((a[1:]>=-1e-8).all() and (a[1:]<=.3+1e-8).all())
        self.assertGreaterEqual(audit['training_utility'],audit['incumbent_utility']-1e-12)

    def test_allocation_fit_ignores_future_outside_calibration_mask(self):
        rng=np.random.default_rng(123);n=30
        cov=np.repeat(self.cov[None,:,:],n,axis=0)
        basis=rng.normal(0,.1,size=(n,4,4))
        r=rng.normal(0,.01,size=(n,4));mask=(np.arange(n)>=2)&(np.arange(n)<20)
        a,audit=fit_allocation(basis,cov,r,self.groups,mask,2,1)
        changed_r=r.copy();changed_r[20:]=.9
        changed_basis=basis.copy();changed_basis[20:]*=20
        changed_cov=cov.copy();changed_cov[20:]*=3
        b,audit2=fit_allocation(changed_basis,changed_cov,changed_r,self.groups,mask,2,1)
        np.testing.assert_allclose(a,b,atol=1e-8)
        self.assertAlmostEqual(audit['training_utility'],audit2['training_utility'],places=12)


if __name__=='__main__':unittest.main()
