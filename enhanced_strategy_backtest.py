"""Enhanced TSMOM: EWMA instrument volatility + EWMA covariance portfolio targeting,
evaluated net of the Lecture 8 explicit/implicit transaction cost model.

Strategies (same 12-month sign signal throughout, one change at a time):
- baseline              expanding vol sizing, no portfolio targeting (course baseline)
- ewma_vol              EWMA (6m half-life) instrument vol sizing (E1)
- ewma_cov_target       baseline weights scaled to 10% using the EWMA covariance forecast
- enhanced              EWMA vol sizing + EWMA covariance targeting
- static_bmk            always-long, 40%/vol, 1/N (course static benchmark), for reference

Targeting rules (10% target, 4x gross cap, 2x scale cap) are reused unchanged from
portfolio_volatility_targeting.py. Every input is known at the formation date and
weights execute the following month. Run from the project root:

    python enhanced_strategy_backtest.py
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from covariance_risk_validation import ROOT, predict
from portfolio_volatility_targeting import target_weights, simulate, statistics, GROSS_CAP
from strategy_backtest_adj import (
    read_returns, read_asset_map, momentum_signal, expanding_volatility, ewma_volatility,
    tsmom_weights, static_weights, BASELINE_LOOKBACK, EVAL_START,
)
from transaction_cost_model import (
    DEFAULT_PARAMETERS, trailing_contract_volume, instrument_adv_usd, cost_breakdown, trade_weights,
)

OUT = ROOT / "outputs" / "enhanced_strategy_output"
AUM_SCENARIOS = (1e8, 1e9, 1e10)
CAPACITY_GRID = (1e7, 1e8, 3e8, 1e9, 3e9, 1e10, 3e10, 1e11)
# Lecture 8 slide 32 simple rule: fixed bps per unit of turnover plus futures roll.
# 2 bps is the lecture's own figure; 10 bps is a conservative comparison.
FLAT_BPS_GRID = (2, 10)
FLAT_CASES = tuple(f"flat_{b}bps" for b in FLAT_BPS_GRID)
EXECUTION_DAYS_GRID = (1, 5, 21)
ADV_MULTIPLIERS = (0.5, 2.0)
SUBPERIODS = (("1976-1999", "1976", "1999"), ("2000-2014", "2000", "2014"))


def build_strategies(returns, asset_map):
    signal = momentum_signal(returns, BASELINE_LOOKBACK)
    exp_vol, ewma_vol = expanding_volatility(returns), ewma_volatility(returns)
    base = tsmom_weights(signal, exp_vol, asset_map).fillna(0)
    ewma_sized = tsmom_weights(signal, ewma_vol, asset_map).fillna(0)
    strategies, details = {"baseline": base, "ewma_vol": ewma_sized}, {}
    for name, weights, vol in (("ewma_cov_target", base, exp_vol), ("enhanced", ewma_sized, ewma_vol)):
        forecast, _ = predict(returns, weights, vol)
        scaled, detail = target_weights(weights, forecast["ewma_covariance"].reindex(weights.index))
        strategies[name], details[name] = scaled.fillna(0), detail
    strategies["static_bmk"] = static_weights(exp_vol, asset_map).fillna(0)
    return strategies, details, ewma_vol, exp_vol


def label_aum(aum):
    return f"${aum/1e9:g}bn" if aum >= 1e9 else f"${aum/1e6:g}m"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns, asset_map = read_returns(), read_asset_map()
    asset_class = asset_map.set_index("ID")["AssetClass"].reindex(returns.columns)
    strategies, details, ewma_vol, exp_vol = build_strategies(returns, asset_map)

    volume = trailing_contract_volume(returns.index, returns.columns)
    adv, illiquid = instrument_adv_usd(volume, asset_class, DEFAULT_PARAMETERS)
    illiquid.loc[EVAL_START:].mean().rename("illiquid_month_share").to_csv(OUT / "illiquid_flags.csv")

    monthly, summary, components, by_class, capacity, periods, execution = {}, [], [], [], [], [], []
    sensitivity = []
    for name, formed in strategies.items():
        gross, _, executed = simulate(returns, formed)
        if name in details:
            assert executed.abs().sum(axis=1).max() <= GROSS_CAP + 1e-10
        window = slice(EVAL_START, None)
        executed.loc[window].to_csv(OUT / f"executed_weights_{name}.csv")
        # One turnover definition everywhere: the drift-adjusted trade actually executed.
        traded = trade_weights(executed, returns, "drift").sum(axis=1)
        traded_target = trade_weights(executed, None, "target").sum(axis=1)
        gross_e, traded_e = gross.loc[window], traded.loc[window]
        target_turnover = traded_target.loc[window].mean() * 12
        # Roll does not depend on AUM or on the trade, so it is shared by the flat cases.
        roll_e = cost_breakdown(executed, ewma_vol, adv, asset_class, DEFAULT_PARAMETERS, returns)[0].roll.loc[window]
        cases = {"gross": gross_e}
        for bps, case in zip(FLAT_BPS_GRID, FLAT_CASES):
            cases[case] = gross_e - traded_e * bps / 1e4 - roll_e
        for aum in sorted(set(AUM_SCENARIOS) | set(CAPACITY_GRID)):
            params = DEFAULT_PARAMETERS.with_aum(aum)
            cost, per_instrument = cost_breakdown(executed, ewma_vol, adv, asset_class, params, returns)
            cost = cost.loc[window]
            net = gross_e - cost.total
            stats = statistics(net, traded_e)
            capacity.append({"strategy": name, "aum_usd": aum, **stats,
                             "annual_total_cost": cost.total.mean() * 12,
                             "annual_drift_turnover": cost.turnover.mean() * 12})
            if aum not in AUM_SCENARIOS:
                continue
            tag = f"lecture8_{label_aum(aum)}"
            cases[tag] = net
            monthly[f"{name}_{tag}_cost"] = cost.total
            components.append({"strategy": name, "aum_usd": aum,
                               **(cost.drop(columns=["margin_to_equity", "max_participation", "gross_exposure"])
                                  .mean() * 12).rename(lambda c: f"annual_{c}"),
                               "average_gross_exposure": cost.gross_exposure.mean(),
                               "average_margin_to_equity": cost.margin_to_equity.mean(),
                               "maximum_margin_to_equity": cost.margin_to_equity.max(),
                               "median_max_participation": cost.max_participation.median()})
            class_cost = per_instrument.loc[window].T.groupby(asset_class).sum().T.mean() * 12
            by_class += [{"strategy": name, "aum_usd": aum, "asset_class": k, "annual_cost": v}
                         for k, v in class_cost.items()]
        for days in EXECUTION_DAYS_GRID:
            params = DEFAULT_PARAMETERS.replace(execution_days=days)
            cost, _ = cost_breakdown(executed, ewma_vol, adv, asset_class, params, returns)
            cost = cost.loc[window]
            execution.append({"strategy": name, "aum_usd": params.aum_usd, "execution_days": days,
                              "sharpe_0rf": statistics(gross_e - cost.total, traded_e)["sharpe_0rf"],
                              "annual_market_impact": cost.market_impact.mean() * 12,
                              "annual_total_cost": cost.total.mean() * 12,
                              "median_max_participation": cost.max_participation.median()})
        # Robustness of the $1bn result to the two least certain inputs: sigma and ADV.
        sens_cases = {"base (EWMA sigma, ADV x1)": (ewma_vol, adv),
                      "sigma = expanding vol": (exp_vol, adv)}
        sens_cases.update({f"ADV x{m:g}": (ewma_vol, adv * m) for m in ADV_MULTIPLIERS})
        for label, (sigma, adv_case) in sens_cases.items():
            cost, _ = cost_breakdown(executed, sigma, adv_case, asset_class, DEFAULT_PARAMETERS, returns)
            cost = cost.loc[window]
            sensitivity.append({"strategy": name, "case": label,
                                "sharpe_0rf": statistics(gross_e - cost.total, traded_e)["sharpe_0rf"],
                                "annual_market_impact": cost.market_impact.mean() * 12,
                                "annual_total_cost": cost.total.mean() * 12})
        for case, r in cases.items():
            monthly[f"{name}_{case}"] = r
            summary.append({"strategy": name, "costs": case, **statistics(r, traded_e),
                            "annual_target_turnover": target_turnover})
            for label, start, end in SUBPERIODS:
                sub = r.loc[start:end]
                periods.append({"strategy": name, "costs": case, "period": label,
                                **statistics(sub, traded_e.loc[sub.index])})

    summary = pd.DataFrame(summary)
    components = pd.DataFrame(components)
    capacity = pd.DataFrame(capacity)
    summary.to_csv(OUT / "performance_summary.csv", index=False)
    pd.DataFrame(periods).to_csv(OUT / "performance_by_period.csv", index=False)
    components.to_csv(OUT / "cost_components.csv", index=False)
    pd.DataFrame(by_class).to_csv(OUT / "cost_by_asset_class.csv", index=False)
    capacity.to_csv(OUT / "capacity_curve.csv", index=False)
    execution = pd.DataFrame(execution)
    execution.to_csv(OUT / "execution_days_sensitivity.csv", index=False)
    sensitivity = pd.DataFrame(sensitivity)
    sensitivity.to_csv(OUT / "cost_input_sensitivity.csv", index=False)
    pd.DataFrame(monthly).rename_axis("Date").to_csv(OUT / "monthly_returns_and_costs.csv")
    pd.concat({k: v for k, v in details.items()}, names=["strategy", "Date"]) \
        .to_csv(OUT / "targeting_diagnostics.csv")

    plot_results(monthly, components, capacity)
    write_report(summary, components, capacity, illiquid, execution, sensitivity)
    main_case = f"lecture8_{label_aum(1e9)}"
    print(summary[summary.costs.isin(["gross", *FLAT_CASES, main_case])]
          [["strategy", "costs", "cagr", "annual_volatility", "sharpe_0rf", "max_drawdown", "annual_turnover"]]
          .round(4).to_string(index=False))
    print(components.round(5).to_string(index=False))
    print(sensitivity.round(5).to_string(index=False))


def plot_results(monthly, components, capacity):
    names = ("baseline", "ewma_vol", "ewma_cov_target", "enhanced")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax = axes[0, 0]
    for name in names:
        line, = ax.plot((1 + monthly[f"{name}_gross"]).cumprod(), lw=1, alpha=0.5, ls="--")
        ax.plot((1 + monthly[f"{name}_lecture8_$1bn"]).cumprod(), lw=1.4, color=line.get_color(), label=name)
    ax.set_yscale("log")
    ax.set_title("Wealth: gross (dashed) vs net of Lecture 8 costs at $1bn (solid)")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    sel = components[components.aum_usd == 1e9].set_index("strategy").loc[list(names)]
    parts = ["annual_commission", "annual_roll", "annual_financing", "annual_half_spread", "annual_market_impact"]
    bottom = np.zeros(len(sel))
    for part in parts:
        ax.bar(sel.index, sel[part] * 1e4, bottom=bottom, label=part.replace("annual_", ""))
        bottom += sel[part].to_numpy() * 1e4
    ax.set_ylabel("bps per year")
    ax.set_title("Annual cost by component at $1bn AUM")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    for name in names:
        c = capacity[capacity.strategy == name]
        ax.plot(c.aum_usd, c.sharpe_0rf, marker="o", label=name)
    ax.set_xscale("log")
    ax.set_xlabel("AUM (USD)")
    ax.set_ylabel("Net Sharpe (RF=0)")
    ax.set_title("Capacity: net Sharpe vs AUM")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    for name in names:
        r = monthly[f"{name}_lecture8_$1bn"]
        ax.plot(r.rolling(12).std() * np.sqrt(12), lw=1, label=name)
    ax.axhline(0.10, color="black", ls="--", lw=1)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title("Trailing 12m realized volatility (net, $1bn)")
    ax.legend(fontsize=8)
    for a in axes.flat:
        a.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "enhanced_strategy_comparison.png", dpi=160)
    plt.close(fig)


def write_report(summary, components, capacity, illiquid, execution, sensitivity):
    p = DEFAULT_PARAMETERS
    lines = ["# Enhanced strategy: EWMA risk model + Lecture 8 transaction costs", "",
             "Evaluation January 1976–December 2014; identical dates for every strategy. Same 12-month sign signal; "
             "formation-date information only; one-month execution lag.", "",
             "## Strategies", "",
             "- `baseline`: expanding-vol sizing (40%/σ, 1/N), no portfolio target.",
             "- `ewma_vol`: EWMA instrument volatility (6-month half-life, 36-month entry rule).",
             "- `ewma_cov_target`: baseline weights scaled so EWMA-covariance forecast vol = 10% (4x gross cap, 2x scale cap).",
             "- `enhanced`: EWMA vol sizing, then EWMA-covariance targeting with the same limits.",
             "- `static_bmk`: always-long course static benchmark (reference only).", "",
             "## Cost model (fixed in advance, not fitted)", "",
             f"- Explicit — commission/fees {p.commission_bps} bp per unit notional traded; futures roll {p.roll_bps} bp of held "
             f"notional per roll, rolls/year by contract cycle (energy 12, grains/livestock 5-8, financials 4; class fallback {p.rolls_per_year}); margin rates {p.margin_rate}, financing at "
             f"{p.financing_spread_bps} bps/yr only on margin above {p.max_margin_to_equity:.0%} of equity; no borrow fee for futures shorts.",
             f"- Implicit — half-spread {p.half_spread_bps} bps per unit traded; square-root impact "
             f"MI = {p.impact_coefficient} × σ_daily × √(trade USD / (ADV USD × {p.execution_days} execution days)). ADV by class {p.adv_usd} (USD/day), "
             f"cut to {p.illiquid_adv_multiplier:.0%} when trailing 252-day median contract volume < {p.illiquid_contract_volume:,.0f}. "
             "σ is the formation-date EWMA instrument vol for all strategies.",
             f"- Turnover: {p.turnover}-adjusted, i.e. trades from last month's weights after they drifted with "
             "last month's returns. The same turnover is used by every cost case and in the Turnover/yr column; "
             "the target-weight change used elsewhere in the repo is shown alongside for reference.",
             f"- Flat cases (`flat_Nbps`, slide 32's simple rule): N bps per unit of turnover plus the same futures roll "
             f"cost; {FLAT_BPS_GRID[0]} bps is the lecture's figure. They do not depend on AUM.",
             "- Classification: slide 32 lists futures roll under implicit costs; it is reported here as explicit because "
             "each roll is a commission-bearing trade. Totals are unaffected.", "",
             "## Results", "",
             "| Strategy | Costs | CAGR | Vol | Sharpe | Max DD | Turnover/yr (drift) | Turnover/yr (target) |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in summary[summary.costs.isin(["gross", *FLAT_CASES, "lecture8_$1bn"])].itertuples():
        lines.append(f"| {r.strategy} | {r.costs} | {r.cagr:.2%} | {r.annual_volatility:.2%} | {r.sharpe_0rf:.3f} | "
                     f"{r.max_drawdown:.2%} | {r.annual_turnover:.2f} | {r.annual_target_turnover:.2f} |")
    lines += ["", "## Annual cost by component (bps/yr)", "",
              "| Strategy | AUM | Commission | Roll | Financing | Half-spread | Impact | Total | Avg margin/equity |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in components.itertuples():
        lines.append(f"| {r.strategy} | {label_aum(r.aum_usd)} | {r.annual_commission*1e4:.1f} | {r.annual_roll*1e4:.1f} | "
                     f"{r.annual_financing*1e4:.1f} | {r.annual_half_spread*1e4:.1f} | {r.annual_market_impact*1e4:.1f} | "
                     f"{r.annual_total*1e4:.1f} | {r.average_margin_to_equity:.1%} |")
    lines += ["", "## Capacity (net Sharpe by AUM)", "",
              "| Strategy | " + " | ".join(label_aum(a) for a in CAPACITY_GRID) + " |",
              "|---|" + "---:|" * len(CAPACITY_GRID)]
    for name, c in capacity.groupby("strategy", sort=False):
        lines.append(f"| {name} | " + " | ".join(f"{s:.3f}" for s in c.sort_values("aum_usd").sharpe_0rf) + " |")
    lines += ["", "## Execution-horizon sensitivity ($1bn)", "",
              "Impact scales with 1/√(execution days); trading the whole rebalance in one day is the upper bound.", "",
              "| Strategy | Days | Net Sharpe | Impact bps/yr | Total bps/yr | Median max participation |",
              "|---|---:|---:|---:|---:|---:|"]
    for r in execution.itertuples():
        lines.append(f"| {r.strategy} | {r.execution_days} | {r.sharpe_0rf:.3f} | {r.annual_market_impact*1e4:.1f} | "
                     f"{r.annual_total_cost*1e4:.1f} | {r.median_max_participation:.1%} |")
    lines += ["", "## Cost-input sensitivity ($1bn, 5 execution days)", "",
              "σ in the impact model describes the market, not the strategy, so one estimate (EWMA) is used for every "
              "strategy; the expanding-window row checks that conclusions do not depend on that choice. ADV is a "
              "class-level assumption, so it is halved and doubled.", "",
              "| Strategy | Case | Net Sharpe | Impact bps/yr | Total bps/yr |", "|---|---|---:|---:|---:|"]
    for r in sensitivity.itertuples():
        lines.append(f"| {r.strategy} | {r.case} | {r.sharpe_0rf:.3f} | {r.annual_market_impact*1e4:.1f} | "
                     f"{r.annual_total_cost*1e4:.1f} |")
    lines += ["", "## Limitations", "",
              "- Cost parameters are illustrative class-level assumptions; contract multipliers are unavailable, so contract "
              "volume only flags thin markets. ADV is not scaled back in time, so early-sample impact is likely understated.",
              "- Positions are rebalanced to target each month from drifted weights; missing returns are zero-filled; "
              "Sharpe uses RF = 0 and no collateral yield.",
              "- The full 1976–2014 sample was already examined; subperiods are descriptive, not an untouched holdout."]
    (OUT / "methodology_and_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
