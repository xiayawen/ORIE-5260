"""Rebuild the selected fixed-42-input portfolio at an 11% ex-ante target."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/orie_mpl')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from orie5260.common.data import ROOT
from orie5260.backtests.final_strategy import build_portfolio_inputs, inverse_vol_weight, dated_sleeves, BUDGETS
from orie5260.portfolio.risk_model import monthly_ewma_vol, monthly_covariance_cube, normalize_sleeve
from orie5260.portfolio.engine import risk_normalize
from orie5260.execution.costs_and_execution import mark_daily
from orie5260.backtests.compare_baseline import BASE, measures, drawdown_series

OUT = ROOT / 'outputs' / 'selected42_target11'
TARGET_VOLATILITY = .11
PERIODS = {'IS': ('1976-01-01', '2014-12-31'), 'OOS': ('2015-01-01', '2025-05-31')}
COLORS = ['#8797A6', '#008577']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    x = build_portfolio_inputs()
    r, dates, cov = x['monthly'], x['dates'], x['covariance']
    probability = pd.read_csv(
        ROOT / 'outputs/ic_t_feature_filter/ICT_Fixed42_probabilities.csv',
        index_col=0, parse_dates=True,
    ).reindex(index=r.index, columns=r.columns)
    vol = monthly_ewma_vol(r).where(r.notna().rolling(12, min_periods=12).sum().eq(12))
    mcov = monthly_covariance_cube(r)
    monthly_core = risk_normalize(
        inverse_vol_weight(
            (r.rolling(12, min_periods=12).sum() / monthly_ewma_vol(r)).clip(-1, 1), vol,
        ).to_numpy() * vol.notna().to_numpy(), mcov,
    )
    direction = 2 * probability - 1
    raw = direction.div(vol)
    valid = raw.notna() & direction.ne(0)
    raw = raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0)
    ml = normalize_sleeve(raw, vol.notna().to_numpy(), mcov)
    monthly_basis = np.stack([monthly_core] * 4, axis=1)
    monthly_basis[:, 3] = np.where((np.abs(ml).sum(axis=1) > 0)[:, None], ml, monthly_core)
    x['basis'][:, 3] = dated_sleeves(r, monthly_basis, dates, x['daily_core'], cov, x['eligible'])[:, 3]
    blend = np.einsum('tki,k->ti', x['basis'], BUDGETS)
    selected = risk_normalize(blend, cov, TARGET_VOLATILITY)
    predicted = np.sqrt(np.maximum(np.einsum('ti,tij,tj->t', selected, cov, selected), 0))
    np.testing.assert_allclose(predicted[predicted > 0], TARGET_VOLATILITY, atol=1e-10)
    formed = pd.DataFrame(selected, index=dates, columns=r.columns)
    daily = mark_daily(x['daily'], formed)

    baseline = pd.read_csv(BASE, index_col='Date', parse_dates=True)
    endpoints = baseline.index.intersection(dates)
    wealth = (1 + daily.net_return).cumprod().reindex(endpoints)
    aligned = pd.DataFrame({
        'Baseline': baseline.net.reindex(endpoints),
        'Selected42': wealth / wealth.shift(1) - 1,
    }, index=endpoints).dropna()
    rows = []
    for period, (start, end) in PERIODS.items():
        for name in aligned:
            row = dict(strategy=name, period=period, **measures(aligned[name].loc[start:end]))
            if name == 'Selected42':
                f = daily.loc[start:end]
                years = row['periods'] / 12
                path = (1 + f.net_return).cumprod()
                row.update(
                    annual_turnover=f.turnover.sum() / years,
                    annual_cost=(f.trade_cost + f.roll_cost).sum() / years,
                    average_gross=f.gross_exposure.mean(),
                    average_absolute_net=f.net_exposure.abs().mean(),
                    daily_max_drawdown=(path / path.cummax().clip(lower=1) - 1).min(),
                    daily_sharpe=f.net_return.mean() / f.net_return.std() * np.sqrt(252),
                )
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / 'performance_and_decomposition.csv', index=False)
    aligned.to_csv(OUT / 'aligned_period_returns.csv')
    daily.to_csv(OUT / 'selected42_daily_returns.csv')

    plt.rcParams.update({'font.family': 'Arial', 'font.size': 11})
    pos = np.arange(2)
    width = .32
    fig, ax = plt.subplots(figsize=(6, 3.87))
    for i, name in enumerate(['Baseline', 'Selected42']):
        vals = [float(table.loc[(table.strategy == name) & (table.period == p), 'sharpe_zero_rf'].iloc[0]) for p in PERIODS]
        bars = ax.bar(pos + (i - .5) * width, vals, width, color=COLORS[i], label=['Baseline', 'Four-sleeve (11%)'][i])
        ax.bar_label(bars, labels=[f'{v:.4f}' for v in vals], padding=4)
    ax.set_xticks(pos, ['1976–2014', '2015–May 2025'])
    ax.set_ylim(0, 1.6)
    ax.set_ylabel('Net Sharpe')
    ax.grid(axis='y', alpha=.2)
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.12), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / 'image2.png', dpi=200)
    plt.close(fig)
    for image, period in [('image3', 'IS'), ('image1', 'OOS')]:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        start, end = PERIODS[period]
        for i, name in enumerate(['Baseline', 'Selected42']):
            series = drawdown_series(aligned[name].loc[start:end])
            ax.plot(series.index, series, color=COLORS[i], label=['Baseline', 'Four-sleeve (11%)'][i], lw=1.5)
        ax.set_ylim(-.30, .01)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis='y', alpha=.2)
        ax.legend(loc='upper center', bbox_to_anchor=(.5, -.13), ncol=2, frameon=False)
        fig.tight_layout()
        fig.savefig(OUT / (image + '.png'), dpi=200)
        plt.close(fig)
    print(table.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
