"""R2: hierarchical risk-budget TSMOM, in-sample (1976-2014) vs out-of-sample (2015-2025).

Data: MonthlyReturns_FullSample.xlsx (Feb 1969 - May 2025). Every parameter below
was fixed before the 2015-2025 data were examined, and nothing is re-estimated or
re-selected on the out-of-sample period: estimates simply keep expanding month by
month, exactly as a live strategy would.

Strategies (same 12-month sign signal throughout):
- baseline         course baseline: 40%/expanding vol, 1/N over eligible instruments
- class_count      E3: equal *count* budget per asset class (no correlation)
- ewma_vol         E1: EWMA (6m half-life) instrument vol sizing
- ewma_cov_target  baseline scaled to 10% predicted vol with EWMA covariance (4x/2x caps)
- enhanced         EWMA vol sizing + EWMA covariance targeting
- rb_class         R2: 25% of ex-ante risk per asset class, equal inside each class,
                   EWMA covariance, 10% predicted vol, 4x gross cap
- static_bmk       always-long course benchmark (reference)

Timing: weights formed with returns through month t earn month t+1 returns.
Run from the project root:  python risk_budget_backtest.py
"""

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from enhanced_strategy_backtest import build_strategies
from portfolio_volatility_targeting import simulate, GROSS_CAP
from risk_budgeting import (
    ROOT, IS_START, IS_END, OOS_START, read_full_sample_returns, risk_budget_weights,
    class_risk_shares, realized_class_risk_shares, effective_number,
)
from strategy_backtest_adj import (
    read_asset_map, momentum_signal, expanding_volatility, tsmom_weights, BASELINE_LOOKBACK,
)
from transaction_cost_model import (
    DEFAULT_PARAMETERS, trailing_contract_volume, instrument_adv_usd, cost_breakdown, trade_weights,
)

OUT = ROOT / "outputs" / "risk_budget_output"
TARGET = 0.10
FLAT_BPS = 10
PERIODS = {"in_sample_1976_2014": (IS_START, IS_END),
           "out_of_sample_2015_2025": (OOS_START, None),
           "full_1976_2025": (IS_START, None)}
MAIN = ("baseline", "class_count", "ewma_vol", "ewma_cov_target", "enhanced", "rb_class", "static_bmk")
CAPPED = {"ewma_cov_target", "enhanced", "rb_class"}
CLASSES = ["COMM", "EQ", "FI", "FX"]


def build_all(returns, asset_map):
    asset_class = asset_map.set_index("ID")["AssetClass"].reindex(returns.columns)
    signal = momentum_signal(returns, BASELINE_LOOKBACK)
    exp_vol = expanding_volatility(returns)
    strategies, _, ewma_vol, _ = build_strategies(returns, asset_map)
    strategies["class_count"] = tsmom_weights(signal, exp_vol, asset_map, "asset_class").fillna(0)
    strategies["rb_class"], diagnostics = risk_budget_weights(
        returns, signal, exp_vol.notna(), asset_class, "ewma", TARGET, GROSS_CAP)
    return {k: strategies[k] for k in MAIN}, diagnostics, ewma_vol, asset_class


def statistics(r, traded):
    r = r.dropna()
    wealth = (1 + r).cumprod()
    years = len(r) / 12
    vol = r.std() * np.sqrt(12)
    sharpe = r.mean() * 12 / vol
    return {
        "start": r.index.min().date(), "end": r.index.max().date(), "months": len(r),
        "cagr": wealth.iloc[-1] ** (1 / years) - 1, "annual_mean": r.mean() * 12,
        "annual_volatility": vol, "sharpe_0rf": sharpe,
        # Lo (2002) iid approximation, for scale only
        "sharpe_standard_error": np.sqrt((1 + 0.5 * sharpe ** 2) / years),
        "t_stat_mean": r.mean() / r.std() * np.sqrt(len(r)),
        "max_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min(),
        "hit_rate": (r > 0).mean(),
        "annual_turnover": traded.loc[r.index].mean() * 12,
    }


def slice_period(series, start, end):
    return series.loc[start:end] if end else series.loc[start:]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns, asset_map = read_full_sample_returns(), read_asset_map()
    strategies, diagnostics, ewma_vol, asset_class = build_all(returns, asset_map)
    assert diagnostics.max_budget_error.max() < 1e-8
    volume = trailing_contract_volume(returns.index, returns.columns)
    adv, _ = instrument_adv_usd(volume, asset_class, DEFAULT_PARAMETERS)

    monthly, summary, realized, exante, exposure = {}, [], [], [], []
    for name, formed in strategies.items():
        gross, _, executed = simulate(returns, formed)
        if name in CAPPED:
            assert executed.abs().sum(axis=1).max() <= GROSS_CAP + 1e-9
        traded = trade_weights(executed, returns, "drift").sum(axis=1)
        cost, _ = cost_breakdown(executed, ewma_vol, adv, asset_class, DEFAULT_PARAMETERS, returns)
        cases = {"gross": gross,
                 f"flat_{FLAT_BPS}bps_plus_roll": gross - traded * FLAT_BPS / 1e4 - cost.roll,
                 "lecture8_$1bn": gross - cost.total}
        instrument_returns = executed * returns.fillna(0)
        shares = class_risk_shares(formed, returns, asset_class, "ewma",
                                   dates=formed.index[formed.index >= pd.Timestamp(IS_START) - pd.DateOffset(months=1)])
        shares.index = shares.index + pd.offsets.MonthEnd(1)  # align with the execution month
        for case, r in cases.items():
            monthly[f"{name}_{case}"] = r.loc[IS_START:]
        monthly[f"{name}_turnover"] = traded.loc[IS_START:]
        for period, (start, end) in PERIODS.items():
            for case, r in cases.items():
                summary.append({"strategy": name, "costs": case, "period": period,
                                **statistics(slice_period(r, start, end), traded)})
            rr = realized_class_risk_shares(slice_period(instrument_returns, start, end), asset_class)
            realized.append({"strategy": name, "period": period, **rr.to_dict(),
                             "effective_classes": 1 / (rr ** 2).sum()})
            ex = slice_period(shares, start, end)
            exante.append({"strategy": name, "period": period, **ex.mean().to_dict(),
                           "effective_classes": effective_number(ex).mean(),
                           "largest_class_share": ex.max(axis=1).mean()})
            ge = slice_period(executed.abs().sum(axis=1), start, end)
            exposure.append({"strategy": name, "period": period, "average_gross_exposure": ge.mean(),
                             "maximum_gross_exposure": ge.max(),
                             "average_active_instruments": slice_period(executed.ne(0).sum(axis=1), start, end).mean()})
        executed.loc[IS_START:].to_csv(OUT / f"executed_weights_{name}.csv")

    summary, realized, exante = pd.DataFrame(summary), pd.DataFrame(realized), pd.DataFrame(exante)
    summary.to_csv(OUT / "performance_is_vs_oos.csv", index=False)
    realized.to_csv(OUT / "realized_class_risk_share.csv", index=False)
    exante.to_csv(OUT / "exante_class_risk_share.csv", index=False)
    pd.DataFrame(exposure).to_csv(OUT / "exposure_by_period.csv", index=False)
    monthly = pd.DataFrame(monthly).rename_axis("Date")
    monthly.to_csv(OUT / "monthly_returns.csv")
    diagnostics.to_csv(OUT / "risk_budget_formation_diagnostics.csv")
    plot(monthly, returns, strategies, asset_class)
    write_report(summary, exante, realized, diagnostics)
    view = summary[summary.costs == "lecture8_$1bn"].pivot(index="strategy", columns="period", values="sharpe_0rf")
    print(view.loc[list(MAIN)].round(3).to_string())


def plot(monthly, returns, strategies, asset_class):
    names = ("baseline", "ewma_cov_target", "enhanced", "rb_class")
    fig, axes = plt.subplots(3, 1, figsize=(12, 13))
    ax = axes[0]
    for name in names:
        ax.plot((1 + monthly[f"{name}_lecture8_$1bn"]).cumprod(), lw=1.3, label=name)
    ax.set_yscale("log")
    ax.axvspan(pd.Timestamp(OOS_START), monthly.index.max(), color="grey", alpha=0.15, label="out-of-sample")
    ax.set_title("Wealth net of Lecture 8 costs at \\$1bn (log); shaded = 2015-2025 out-of-sample")
    ax.legend(fontsize=8)
    ax = axes[1]
    for name in names:
        r = monthly[f"{name}_lecture8_$1bn"]
        ax.plot(r.rolling(36).mean() / r.rolling(36).std() * np.sqrt(12), lw=1.1, label=name)
    ax.axvspan(pd.Timestamp(OOS_START), monthly.index.max(), color="grey", alpha=0.15)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Rolling 36-month Sharpe (net, RF=0)")
    ax.legend(fontsize=8)
    ax = axes[2]
    for name, style in (("baseline", "--"), ("rb_class", "-")):
        shares = class_risk_shares(strategies[name], returns, asset_class, "ewma",
                                   dates=strategies[name].index[strategies[name].index >= IS_START])
        for c, color in zip(shares.columns, ("C0", "C1", "C2", "C3")):
            ax.plot(shares[c].rolling(12, min_periods=1).mean(), ls=style, color=color, label=f"{name} {c}")
    ax.axhline(0.25, color="black", ls=":", lw=1)
    ax.axvspan(pd.Timestamp(OOS_START), monthly.index.max(), color="grey", alpha=0.15)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title("Ex-ante asset-class risk share (EWMA covariance Euler PCR, 12m avg): baseline dashed, rb_class solid")
    ax.legend(fontsize=7, ncol=4)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "risk_budget_is_vs_oos.png", dpi=160)
    plt.close(fig)


def write_report(summary, exante, realized, diagnostics):
    def perf_table(cost):
        v = summary[summary.costs == cost].set_index(["strategy", "period"])
        lines = ["| Strategy | IS Sharpe | OOS Sharpe | IS vol | OOS vol | IS MaxDD | OOS MaxDD | IS turnover | OOS turnover |",
                 "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for n in MAIN:
            a, b = v.loc[(n, "in_sample_1976_2014")], v.loc[(n, "out_of_sample_2015_2025")]
            lines.append(f"| {n} | {a.sharpe_0rf:.2f} | {b.sharpe_0rf:.2f} | {a.annual_volatility:.1%} | "
                         f"{b.annual_volatility:.1%} | {a.max_drawdown:.1%} | {b.max_drawdown:.1%} | "
                         f"{a.annual_turnover:.1f} | {b.annual_turnover:.1f} |")
        return "\n".join(lines)

    lines = ["| Strategy | Period | Ex-ante COMM/EQ/FI/FX | Realized COMM/EQ/FI/FX | Realized effective classes |",
             "|---|---|---|---|---:|"]
    f = lambda x: " / ".join(f"{x[c]:.0%}" for c in CLASSES)
    for n in ("baseline", "enhanced", "rb_class"):
        for p, lab in (("in_sample_1976_2014", "IS"), ("out_of_sample_2015_2025", "OOS")):
            a = exante[(exante.strategy == n) & (exante.period == p)].iloc[0]
            b = realized[(realized.strategy == n) & (realized.period == p)].iloc[0]
            lines.append(f"| {n} | {lab} | {f(a)} | {f(b)} | {b.effective_classes:.2f} |")
    risk_md = "\n".join(lines)
    d = diagnostics
    report = f"""# R2: hierarchical risk budgeting, in-sample vs out-of-sample

**Execution timing convention (main results).** Weights formed from month-t closes earn the whole month-t+1
return, so trades are assumed to fill at the same close used to compute the signal, while the Lecture 8
market-impact cost assumes 5-day execution. `alpha_decay_execution.py` shows that a feasible schedule lowers
in-sample net Sharpe by about 0.07-0.09. Treat reported net Sharpe ratios as upper bounds by roughly this amount.

IS = Jan 1976 - Dec 2014 (all design choices were made here). OOS = Jan 2015 - May 2025 (evaluation only).
Data: `MonthlyReturns_FullSample.xlsx`; on 1969-2014 it matches `MonthlyReturns.csv` except six December 2014
cells that are now filled. AP (Australian equity) has no data from June 2022 to February 2025 and then prints
+23%/+43%/+44% in March-May 2025 (almost certainly a data error); the 12-month signal is undefined after the
gap, so no strategy holds AP then. EC (Eurodollar) is labelled FX in `AssetMapCsv.csv` but is a short-rate future.

## Method

Signed risk budgeting (Spinu 2013): with signs s from the 12-month signal, magnitudes x > 0 minimise
0.5 x'Cx - b'log x with C = diag(s) S diag(s), so every instrument's Euler PCR equals its budget b_i = 1/(K n_c):
each active asset class carries 1/K of ex-ante risk, split equally inside the class. S is the 6-month EWMA
covariance through the formation month. The portfolio is scaled to 10% predicted volatility and gross exposure
above 4x is cut proportionally (risk shares unchanged).

Solver: at most {d.solver_iterations.max()} Newton steps, max |PCR - budget| = {d.max_budget_error.max():.1e}.
The 4x cap binds in {d.gross_cap_binding.mean():.0%} of months, so average predicted volatility is
{d.predicted_volatility.mean():.1%} rather than 10%: equal risk for fixed income and FX needs large notional in
low-volatility rate futures.

## Performance net of Lecture 8 costs at $1bn

{perf_table("lecture8_$1bn")}

## Gross of costs

{perf_table("gross")}

Sharpe standard errors are about 0.19 IS and 0.31 OOS (Lo 2002, iid).

## Ex-ante vs realized asset-class risk shares

Ex-ante: average EWMA-covariance Euler PCR at formation. Realized: cov(r_class, r_portfolio) / var(r_portfolio)
over the period (sums to one).

{risk_md}

## Findings

1. Every TSMOM variant weakens OOS by roughly 0.8-1.1 net Sharpe, including the unmodified baseline, so the drop
   is mainly a regime effect (the 2015-2025 trend-following drought) rather than overfitting of the enhancements.
   The static long benchmark holds up.
2. R2 meets its ex-ante goal (OOS ex-ante shares 25/25/25/25) and has the smallest IS drawdown, but the budget is only
   partly realised (IS commodities ~32% budgeted vs ~48% realised): 6-month EWMA correlations are noisy.
3. R2's gross Sharpe is close to enhanced, but it trades 2-3x as much, because the full-covariance budget is
   re-solved every month (small correlation changes and any sign flip resize every position). Net Sharpe is
   therefore lower. Combine with the T1 no-trade band (`cost_aware_rebalance.py`) for the adopted comparison.

## Look-ahead audit

`python -m unittest test_lookahead.py` reruns every strategy on data truncated at 1990-06, 2014-12 and 2020-03
and checks that all weights, volatility estimates, Lecture 8 costs and T1 holding paths formed up to each cut are
identical to the full-sample run, plus the one-month execution lag. All tests pass.

Remaining sources of bias found by code inspection (none affects the headline strategy weights):

| Where | Issue | Severity |
|---|---|---|
| Research process | All parameters and the enhanced design were chosen after viewing 1976-2014; IS Sharpe is optimistic. Only 2015-2025 is clean OOS. | High (measured above) |
| `strategy_backtest.py` `full_sample_volatility`; `rolling_backtest.py` full-sample controls | Positions sized with full-sample volatility (true look-ahead). Controls only; never quote as tradable. | Medium |
| `strategy_backtest_adj.vol_matched_returns`; `generate_strategy_analysis.py` vol matching | Scales by full-sample realized vol. Sharpe unchanged; matched CAGR, drawdown and wealth plots are ex post. | Low (documented) |
| Return-attribution regimes; diagonal-validation high-vol quintile | Ex-post labels; fine for attribution, not as signals. | Low (documented) |
| `economic_trend.py` | Current-vintage FRED data: macro revisions were not known in real time. | Medium (that module) |
| `transaction_cost_model.py` ADV and spreads | Calibrated to recent liquidity and applied back to 1976; daily volume ends 2014, so OOS ADV uses class constants. | Medium (cost level) |
| Universe | The 58 markets were chosen with hindsight (survivorship / selection). | Medium |
| `tsmom_weights` 1/N divisor | Eligible instruments with no signal (stopped trading / data gap) still count in N, diluting positions (0.2 IS, 1.9 OOS on average). | Low |
| Execution timing | Fill at the signal close with 5-day impact (see top). | ~0.07-0.09 Sharpe |
"""
    (OUT / "risk_budget_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
