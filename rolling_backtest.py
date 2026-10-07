"""Matched-universe monthly TSMOM, rolling volatility, cost scenarios and HAC OLS."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/orie5260-matplotlib')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import statsmodels.api as sm
from strategy_backtest import read_returns, momentum_signal, build_strategy_set

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs' / 'rolling'
COST_BPS = (0, 5, 10, 25)
WINDOW = 12


def matched_weights(returns, rolling=True):
    signal = momentum_signal(returns, 12)
    vol = returns.rolling(WINDOW, min_periods=WINDOW).std() * np.sqrt(12) if rolling else pd.DataFrame(
        np.tile((returns.std() * np.sqrt(12)).to_numpy(), (len(returns), 1)), index=returns.index, columns=returns.columns)
    eligible = signal.notna() & vol.notna() & (vol > 0)
    scale = (0.40 / vol).where(eligible).div(eligible.sum(axis=1).replace(0, np.nan), axis=0)
    return (signal * scale).fillna(0), scale.fillna(0), eligible


def simulate(returns, formed_weights, bps):
    executed = formed_weights.shift(1).fillna(0)
    # Fixed target exposure approximation: one-way absolute changes, including initial entry.
    traded = executed.diff().fillna(executed).abs().sum(axis=1)
    missing_held = executed.ne(0) & returns.isna()
    gross = (executed * returns.fillna(0)).sum(axis=1)
    return gross - traded * bps / 10000, traded, executed, missing_held


def metrics(name, r, traded, bps):
    wealth = (1+r).cumprod()
    peak = wealth.cummax().clip(lower=1)
    vol = r.std()*np.sqrt(12)
    return dict(strategy=name, cost_bps=bps, start=str(r.index.min().date()), end=str(r.index.max().date()),
                months=len(r), cagr=(1+r).prod()**(12/len(r))-1, annual_vol=vol,
                sharpe_zero_rf=r.mean()*12/vol, max_drawdown=(wealth/peak-1).min(),
                average_monthly_traded_notional=traded.mean(), annual_cost_drag=traded.mean()*12*bps/10000)


def regression(y, factors, name, specification):
    data = pd.concat([y.rename('y'), factors], axis=1).dropna()
    fit = sm.OLS(data.y, sm.add_constant(data.drop(columns='y'))).fit(cov_type='HAC', cov_kwds={'maxlags':3})
    ci = fit.conf_int().loc['const']*12
    row = dict(strategy=name, specification=specification, months=len(data),
               start=str(data.index.min()), end=str(data.index.max()),
               alpha_annual_arithmetic=fit.params['const']*12, alpha_hac_t=fit.tvalues['const'],
               alpha_pvalue=fit.pvalues['const'], alpha_ci_lower=ci.iloc[0], alpha_ci_upper=ci.iloc[1], r_squared=fit.rsquared)
    for key in factors.columns: row['beta_'+key] = fit.params[key]
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    tw, sw, eligible = matched_weights(r)
    fw, fs, _ = matched_weights(r, rolling=False)
    start_mask = eligible.shift(1, fill_value=False).any(axis=1)
    start = start_mask[start_mask].index[0]
    sample = r.index[r.index >= start]
    table, summaries, diagnostics = {}, [], []
    original = build_strategy_set(r)
    for result in original:
        name = 'original_'+('tsmom' if 'tsmom' in result['name'] else 'static')
        rr = result['returns'].loc[sample]
        summaries.append(metrics(name, rr, result['turnover'].loc[sample], 0))
        table[name] = rr
    for name, weights, costs in [('matched_full_sample_tsmom',fw,(0,)), ('matched_full_sample_static',fs,(0,)),
                                 ('rolling_tsmom',tw,COST_BPS), ('rolling_static',sw,COST_BPS)]:
        for bps in costs:
            net, traded, execution, missing = simulate(r,weights,bps)
            key = f'{name}_{bps}bps'
            table[key] = net.loc[sample]
            summaries.append(metrics(name,net.loc[sample],traded.loc[sample],bps))
            if bps == 0:
                diagnostics.append(dict(strategy=name,missing_held_instrument_months=int(missing.loc[sample].sum().sum()),
                                        max_gross_exposure=execution.loc[sample].abs().sum(axis=1).max()))
    monthly = pd.DataFrame(table)
    summary = pd.DataFrame(summaries)
    corr = []
    for bps in COST_BPS:
        x,y = monthly[f'rolling_tsmom_{bps}bps'], monthly[f'rolling_static_{bps}bps']
        monthly[f'alpha_difference_{bps}bps'] = x-y
        corr.append(dict(cost_bps=bps, correlation=x.corr(y), annual_mean_difference=(x-y).mean()*12))
    monthly.to_csv(OUT/'monthly_returns.csv',index_label='Date')
    summary.to_csv(OUT/'performance_summary.csv',index=False)
    pd.DataFrame(corr).to_csv(OUT/'portfolio_correlations.csv',index=False)
    pd.DataFrame(diagnostics).to_csv(OUT/'diagnostics.csv',index=False)
    eligibility = eligible.shift(1,fill_value=False).loc[sample]
    eligibility.to_csv(OUT/'executed_eligibility.csv',index_label='Date')
    tw.shift(1).loc[sample].to_csv(OUT/'tsmom_executed_weights.csv',index_label='Date')
    sw.shift(1).loc[sample].to_csv(OUT/'static_executed_weights.csv',index_label='Date')
    # Month keys avoid differing calendar vs trading month-end dates.
    lecture = pd.read_excel(ROOT/'Lecture3_livedata.xlsx').set_index('Date')
    lecture.index = pd.to_datetime(lecture.index).to_period('M')
    regressions = []
    for bps in (0,10):
        target = monthly[f'rolling_tsmom_{bps}bps'].copy(); target.index = target.index.to_period('M')
        benchmark = monthly[f'rolling_static_{bps}bps'].copy(); benchmark.index = benchmark.index.to_period('M')
        regressions.append(regression(target,benchmark.rename('static').to_frame(),f'tsmom_{bps}bps','static_raw_returns_HAC3'))
        excess = target - lecture.RF
        regressions.append(regression(excess, lecture[['Mkt-RF','SMB','HML','Mom','RMW','CMA']],
                                      f'tsmom_{bps}bps','six_factors_excess_returns_HAC3'))
    pd.DataFrame(regressions).to_csv(OUT/'regression_alpha.csv',index=False)
    fig, ax = plt.subplots(figsize=(11,6))
    for key in ['original_tsmom','matched_full_sample_tsmom_0bps','rolling_tsmom_0bps','rolling_tsmom_10bps','rolling_static_10bps']:
        ax.plot(monthly.index,(1+monthly[key]).cumprod(),label=key)
    ax.set(yscale='log',title='Common-period cumulative wealth (log scale)',ylabel='Growth of 1'); ax.legend(fontsize=8); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(OUT/'comparison.png',dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9,5))
    for name in ['rolling_tsmom','rolling_static']:
        s=summary[summary.strategy==name]; ax.plot(s.cost_bps,s.cagr*100,marker='o',label=name)
    ax.set(xlabel='One-way cost (basis points of traded notional)',ylabel='CAGR (%)',title='Transaction-cost sensitivity');ax.legend();ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(OUT/'cost_sensitivity.png',dpi=160);plt.close(fig)
    lines = ['# Group update — October 7, 2026','',
             '## Method','12-month momentum and 12-month rolling sample standard deviation, annualized by sqrt(12). Both are known at month t; weights execute at t+1. TSMOM and Static share exactly the same eligibility mask, including the momentum-history requirement. No leverage cap is imposed. The original baseline and matched full-sample controls are retained to separate eligibility and volatility changes.',
             '', 'All headline comparisons use the same period starting '+str(start.date())+'. Original baseline controls still contain full-sample look-ahead bias.',
             '', 'Costs are 0, 5, 10, or 25 bps per one-way absolute target-weight change, including initial entry and exits. This is an illustrative turnover model; it excludes position drift, contract rolls, contract multipliers, actual bid-ask spreads, financing and cash interest.',
             '', '## Results','| Strategy | Cost bps | CAGR | Annual vol | Sharpe (zero RF) | Max drawdown |','|---|---:|---:|---:|---:|---:|']
    for row in summaries:
        lines.append(f"| {row['strategy']} | {row['cost_bps']} | {row['cagr']:.2%} | {row['annual_vol']:.2%} | {row['sharpe_zero_rf']:.3f} | {row['max_drawdown']:.2%} |")
    lines += ['', 'Sharpe uses annualized arithmetic mean / annual volatility, unlike the prior baseline report’s CAGR / volatility.', '',
              '![Comparison](../outputs/rolling/comparison.png)','![Costs](../outputs/rolling/cost_sensitivity.png)', '', '## Regression alpha',
              'Exploratory OLS with Newey–West HAC standard errors (3 monthly lags). Static regression uses raw strategy and static returns; its intercept is not a risk-free-adjusted CAPM alpha. The six-factor regression subtracts the supplied RF from strategy returns and uses Mkt-RF, SMB, HML, Mom, RMW and CMA; its sample is 2000–2014. Equity factors are an exploratory model, not a complete risk model for futures. Annual alpha is 12 times the monthly intercept.',
              '', '| Strategy | Model | Months | Annual alpha | HAC t | p-value |','|---|---|---:|---:|---:|---:|']
    for row in regressions:
        lines.append(f"| {row['strategy']} | {row['specification']} | {row['months']} | {row['alpha_annual_arithmetic']:.2%} | {row['alpha_hac_t']:.2f} | {row['alpha_pvalue']:.3f} |")
    lines += ['', '## Limitations and course requirement',
              f"Rolling portfolios reach maximum gross exposure of {max(d['max_gross_exposure'] for d in diagnostics if d['strategy'].startswith('rolling')):.2f} times capital. Low rolling volatility can create extreme leverage; results require a leverage-cap sensitivity study before practical use.",
              'No course document specifying regression alpha was found in the workspace. The supplied slide asks to illustrate alpha without defining a regression model; confirmation remains pending. Regression results are supplementary, not proof that this requirement was assigned.',
              'Missing realized returns for held instruments are zero-filled and counted in diagnostics.csv. This assumption can bias performance; matching eligibility does not eliminate this data issue. Prices/continuous-contract construction and extreme returns remain unverified. Cost assumptions are sensitivity scenarios, not measured execution costs.',
              '', '## Reproduce','Run `python3 rolling_backtest.py`. Dependencies: numpy, pandas, matplotlib, openpyxl, statsmodels. Outputs: `outputs/rolling/`. The previous dated report is preserved.']
    (ROOT/'reports'/'group_update_2026-10-07.md').write_text('\n'.join(lines)+'\n')
    print(summary.to_string(index=False));print(pd.DataFrame(regressions).to_string(index=False))

if __name__ == '__main__':
    main()
