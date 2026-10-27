# Portfolio volatility targeting

Fixed parameters: 10% annual portfolio volatility target, 4x gross exposure cap, 2x maximum multiplier on baseline weights. No tuning to performance. All four models scale the same baseline positions; original baseline is also reported. Formation-month forecasts use history through that month; weights execute one month later. Full pre-evaluation history is used for prior weights and initial evaluation turnover.

Covariance estimation follows covariance_risk_validation.py (expanding pairwise covariance, six-month EWMA, fixed 50% shrinkage, 36-month overlap, PSD repair). Invalid forecasts cause zero exposure. Caps can prevent reaching target. Realized risk may exceed target even when forecast risk does not.

Evaluation: January 1976–December 2014, same dates across strategies. Costs: 0/5/10/25 bps per one-way target-weight change. Missing realized returns are zero-filled. No cash yield, financing, margin, position drift, roll costs or market impact. Sharpe assumes zero risk-free rate. Drawdowns include starting wealth of one. Subperiods 1976–1999 and 2000–2014 are descriptive stability checks, not untouched out-of-sample evidence: this full dataset was already examined. No parameter selection or fitted optimization is performed.

Diagonal targeting versus baseline measures scaling and cap effects. Covariance targeting versus diagonal targeting measures model effects under common targeting rules. EWMA also changes marginal variances. No claim of optimal model selection is made.
