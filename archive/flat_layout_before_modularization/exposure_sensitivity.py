"""Appendix: sensitivity of the capped, cost-aware four-sleeve variant to exposure limits.

Adapted from JodieeT's gross/net cap and gross-matched-control experiment.
The reference variant is decompose_steps.py step 4 (four limits + gamma=5), not
the selected final strategy, which has no exposure caps. All variants retain the
same signals, 10% portfolio risk ceiling, 5% class risk ceiling, 21-business-day
formations, gamma=5 execution and cost model; they are diagnostics only.
"""
from dataclasses import replace
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from costs_and_execution import execute, mark_daily
from data_utils import ROOT
from portfolio_engine import blended_target
from risk_model import LIMITS
from run_final_strategy import BUDGETS, EVALUATION, build_portfolio_inputs, summary

OUT = ROOT / "outputs" / "exposure_sensitivity"


def gross_match(control, selected):
    """Match each no-net-cap target's gross notional to the selected target.

    This is proportional scaling, so the control retains its long/short mix.
    Since removing a cap cannot shrink a radially constrained target, matching
    never requires raising the control's risk or violating its other limits.
    """
    selected_gross = np.abs(selected).sum(axis=1)
    control_gross = np.abs(control).sum(axis=1)
    scale = np.divide(selected_gross, control_gross,
                      out=np.zeros_like(selected_gross), where=control_gross > 0)
    if np.any(scale > 1 + 1e-10):
        raise AssertionError("Gross matching would increase the control's risk")
    return control * scale[:, None]


def drawdown(returns):
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax().clip(lower=1) - 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    x = build_portfolio_inputs()
    monthly, daily, dates = x["monthly"], x["daily"], x["dates"]
    covariance, eligible, basis, groups, forward = (x["covariance"], x["eligible"], x["basis"],
                                                    x["groups"], x["forward"])

    no_gross = replace(LIMITS, gross=np.inf)
    no_net = replace(LIMITS, net=np.inf)
    neither = replace(LIMITS, gross=np.inf, net=np.inf)
    capped = blended_target(basis, BUDGETS, covariance, groups, LIMITS)
    no_net_target = blended_target(basis, BUDGETS, covariance, groups, no_net)
    variants = {
        "capped_gamma5": (capped, LIMITS),
        "no_gross_cap": (blended_target(basis, BUDGETS, covariance, groups, no_gross), no_gross),
        "no_net_cap": (no_net_target, no_net),
        "no_exposure_caps": (blended_target(basis, BUDGETS, covariance, groups, neither), neither),
        "no_net_gross_matched": (gross_match(no_net_target, capped), no_net),
    }
    if not np.allclose(np.abs(variants["no_net_gross_matched"][0]).sum(axis=1),
                       np.abs(capped).sum(axis=1), atol=1e-10):
        raise AssertionError("Control does not match capped target gross exposure")

    marked, performance, effects, exposures = {}, [], [], []
    for name, (target, limits) in variants.items():
        actual, _ = execute(target, covariance, forward, groups, eligible, limits)
        weights = pd.DataFrame(actual, index=dates, columns=monthly.columns)
        marked[name] = mark_daily(daily, weights)
        target_diff = np.abs(target - capped).sum(axis=1)
        for period, (start, end) in EVALUATION.items():
            performance.append({"variant": name, "period": period,
                                **summary(marked[name], start, end)})
            mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
            effects.append({"variant": name, "period": period,
                            "formation_dates": int(mask.sum()),
                            "target_change_frequency": float((target_diff[mask] > 1e-10).mean()),
                            "mean_target_weight_distance": float(target_diff[mask].mean()),
                            "maximum_formed_gross": float(weights.loc[start:end].abs().sum(axis=1).max()),
                            "maximum_formed_absolute_net": float(weights.loc[start:end].sum(axis=1).abs().max())})
        exposures.append(pd.DataFrame({"variant": name, "formation_date": dates,
                                       "target_gross": np.abs(target).sum(axis=1),
                                       "target_net": target.sum(axis=1),
                                       "formed_gross": weights.abs().sum(axis=1).to_numpy(),
                                       "formed_net": weights.sum(axis=1).to_numpy()}))

    pd.DataFrame(performance).to_csv(OUT / "performance_summary.csv", index=False)
    pd.DataFrame(effects).to_csv(OUT / "target_effects.csv", index=False)
    pd.concat(exposures, ignore_index=True).to_csv(OUT / "formation_exposures.csv", index=False)
    pd.DataFrame({name: frame.net_return for name, frame in marked.items()}).to_csv(
        OUT / "daily_net_returns.csv", index_label="Date")

    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = {"capped_gamma5": "#1f77b4", "no_gross_cap": "#2ca02c",
              "no_net_cap": "#ff7f0e", "no_exposure_caps": "#d62728"}
    for name, frame in marked.items():
        if name == "no_net_gross_matched":
            continue  # Exact duplicate of capped_gamma5 under radial net scaling.
        series = drawdown(frame.loc["2015-01-01":"2025-05-31", "net_return"])
        ax.plot(series.index, series, label=name.replace("_", " "),
                color=colors[name], linewidth=2 if name == "capped_gamma5" else 1.3)
    ax.set(title="Appendix: exposure-limit sensitivity of the capped variant, 2015–May 2025",
           xlabel="Trading day", ylabel="Daily drawdown")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=.2)
    ax.legend(fontsize=9, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "drawdown_sensitivity.png", dpi=170)
    plt.close(fig)
    print(pd.DataFrame(performance).loc[lambda d: d.period.isin(
        ["IS_1976_2014", "OOS_2015_2025"])].to_string(index=False))


if __name__ == "__main__":
    main()
