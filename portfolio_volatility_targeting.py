"""Causal portfolio volatility targeting at fixed, predeclared parameters."""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from covariance_risk_validation import ROOT, MODELS, predict
from strategy_backtest_adj import (
    read_returns, read_asset_map, build_baseline, expanding_volatility, EVAL_START,
)
from baseline_output_loader import load_baseline_outputs

OUT = ROOT / "outputs" / "portfolio_volatility_targeting_output"
TARGET = 0.10
GROSS_CAP = 4.0
SCALE_CAP = 2.0
COST_BPS = (0, 5, 10, 25)


def cap_only_weights(weights):
    """Reduce gross exposure above 4x; never enlarge baseline positions."""
    gross = weights.abs().sum(axis=1)
    scale = (GROSS_CAP / gross.replace(0, np.nan)).clip(upper=1).fillna(1)
    return weights.mul(scale, axis=0), pd.DataFrame({
        "applied_scale": scale,
        "gross_exposure": gross * scale,
        "gross_cap_binding": gross > GROSS_CAP,
    })


def target_weights(weights, forecast):
    """Scale formation-date weights using only the formation-date forecast."""
    gross = weights.abs().sum(axis=1)
    valid = forecast.notna() & np.isfinite(forecast) & (forecast > 0) & (gross > 0)
    desired = (TARGET / forecast).where(valid, 0.0)
    leverage_limit = (GROSS_CAP / gross.replace(0, np.nan)).fillna(0)
    scale = pd.concat([desired, leverage_limit, pd.Series(SCALE_CAP, index=weights.index)], axis=1).min(axis=1)
    scaled = weights.mul(scale, axis=0)
    details = pd.DataFrame({
        "unscaled_predicted_volatility": forecast,
        "desired_scale": desired, "applied_scale": scale,
        "predicted_volatility": forecast * scale,
        "gross_exposure": scaled.abs().sum(axis=1),
        "scale_cap_binding": valid & (desired > SCALE_CAP),
        "gross_cap_binding": valid & (desired.clip(upper=SCALE_CAP) > leverage_limit),
        "invalid_forecast": ~valid,
    })
    return scaled, details


def simulate(returns, formed):
    executed = formed.shift(1).fillna(0)
    gross = (executed * returns.fillna(0)).sum(axis=1)
    traded = executed.diff().fillna(executed).abs().sum(axis=1)
    return gross, traded, executed


def statistics(r, traded):
    wealth = (1+r).cumprod()
    rolling_vol = r.rolling(12).std() * np.sqrt(12)
    vol = r.std() * np.sqrt(12)
    return {
        "months": len(r), "cagr": wealth.iloc[-1] ** (12/len(r)) - 1,
        "annual_volatility": vol, "sharpe_0rf": r.mean()*12/vol,
        "max_drawdown": (wealth/wealth.cummax().clip(lower=1)-1).min(),
        "annual_turnover": traded.mean()*12,
        "rolling_12m_volatility_std": rolling_vol.std(),
        "rolling_12m_vol_above_target_frequency": (rolling_vol.dropna() > TARGET).mean(),
        "rolling_12m_vol_above_125pct_target_frequency": (rolling_vol.dropna() > 1.25*TARGET).mean(),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    baseline, _ = build_baseline(returns, read_asset_map())
    formed = baseline["weights"]
    forecasts, _ = predict(returns, formed, expanding_volatility(returns))
    cap_weights, cap_detail = cap_only_weights(formed)
    strategies = {"baseline": formed, "cap_only": cap_weights}
    diagnostics = []
    for model in MODELS:
        targeted, detail = target_weights(formed, forecasts[model].reindex(formed.index))
        strategies[model] = targeted
        detail["model"] = model
        diagnostics.append(detail.rename_axis("Date").reset_index())
    forecasts.to_csv(OUT / "formation_risk_forecasts.csv")
    pd.concat(diagnostics, ignore_index=True).to_csv(OUT / "formation_scaling_diagnostics.csv", index=False)
    monthly, summaries, exposure_rows, period_rows = {}, [], [], []
    original = load_baseline_outputs()["monthly_returns"]["TSMOM_Baseline"]
    for name, weights in strategies.items():
        gross, traded, executed = simulate(returns, weights)
        gross, traded = gross.loc[EVAL_START:], traded.loc[EVAL_START:]
        if name == "baseline":
            np.testing.assert_allclose(gross.loc[original.index], original, atol=1e-12)
        if name != "baseline":
            assert executed.abs().sum(axis=1).max() <= GROSS_CAP + 1e-10
        executed.loc[EVAL_START:].to_csv(OUT / f"executed_weights_{name}.csv")
        monthly[name] = gross
        monthly[f"{name}_turnover"] = traded
        exposure = executed.loc[EVAL_START:].abs().sum(axis=1)
        row = {"strategy": name, "average_gross_exposure": exposure.mean(), "maximum_gross_exposure": exposure.max()}
        if name == "cap_only":
            aligned = cap_detail.reindex(returns.index).shift(1).loc[EVAL_START:]
            row["gross_cap_binding_frequency"] = aligned.gross_cap_binding.astype(float).mean()
        elif name != "baseline":
            detail = next(d for d in diagnostics if d.model.iloc[0] == name).set_index("Date")
            # Formation diagnostics are lagged to align with evaluated execution months.
            aligned = detail.reindex(returns.index).shift(1).loc[EVAL_START:]
            row.update({f"{c}_frequency": aligned[c].astype(float).mean() for c in ("scale_cap_binding", "gross_cap_binding", "invalid_forecast")})
            row["average_predicted_volatility"] = aligned.predicted_volatility.mean()
        exposure_rows.append(row)
        for bps in COST_BPS:
            net = gross - traded*bps/10000
            monthly[f"{name}_net_{bps}bps"] = net
            summaries.append({"strategy": name, "cost_bps": bps, **statistics(net, traded)})
            for label, subset in (("1976-1999", net.loc[:"1999"]), ("2000-2014", net.loc["2000":])):
                period_rows.append({"strategy": name, "cost_bps": bps, "period": label, **statistics(subset, traded.loc[subset.index])})
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "performance_summary.csv", index=False)
    pd.DataFrame(period_rows).to_csv(OUT / "performance_by_period.csv", index=False)
    pd.DataFrame(exposure_rows).to_csv(OUT / "exposure_and_limits.csv", index=False)
    pd.DataFrame(monthly).rename_axis("Date").to_csv(OUT / "monthly_returns_and_turnover.csv")
    cap_detail.rename_axis("Date").to_csv(OUT / "cap_only_formation_diagnostics.csv")
    # Differences describe successive comparisons; nonlinear metrics such as
    # drawdown do not provide an additive causal decomposition.
    differences = []
    metrics = ("cagr", "annual_volatility", "sharpe_0rf", "max_drawdown", "annual_turnover")
    comparisons = [("baseline", "cap_only"), ("cap_only", "diagonal")]
    comparisons += [("cap_only", model) for model in MODELS if model != "diagonal"]
    comparisons += [("diagonal", model) for model in MODELS if model != "diagonal"]
    for bps in COST_BPS:
        selected = summary[summary.cost_bps == bps].set_index("strategy")
        for reference, candidate in comparisons:
            differences.append({"cost_bps": bps, "reference": reference, "candidate": candidate,
                                **{f"delta_{metric}": selected.loc[candidate, metric] - selected.loc[reference, metric]
                                   for metric in metrics}})
    pd.DataFrame(differences).to_csv(OUT / "ablation_differences.csv", index=False)
    lines = ["# Gross exposure cap ablation", "",
             "Same 1976–2014 sample, original signals and one-month execution lag. Cap-only scales all baseline positions proportionally only when gross exposure exceeds 4x; otherwise positions are unchanged. It uses no risk forecast and never increases baseline exposure.", "",
             "## Results at 10 bps per one-way target-weight change", "",
             "| Strategy | CAGR | Annual volatility | Sharpe (RF=0) | Maximum drawdown | Annual turnover |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in summary[summary.cost_bps == 10].itertuples():
        lines.append(f"| {row.strategy} | {row.cagr:.2%} | {row.annual_volatility:.2%} | {row.sharpe_0rf:.3f} | {row.max_drawdown:.2%} | {row.annual_turnover:.2f} |")
    cap_frequency = next(row for row in exposure_rows if row["strategy"] == "cap_only")["gross_cap_binding_frequency"]
    selected = summary[summary.cost_bps == 10].set_index("strategy")
    baseline_dd = selected.loc["baseline", "max_drawdown"]
    cap_dd = selected.loc["cap_only", "max_drawdown"]
    ewma_dd = selected.loc["ewma_covariance", "max_drawdown"]
    lines += ["", f"Cap-only reduces exposure in {cap_frequency:.1%} of evaluation months.", "",
              f"At 10 bps costs, maximum drawdown is {baseline_dd:.2%} for baseline, {cap_dd:.2%} for cap-only, and {ewma_dd:.2%} for EWMA targeting. The cap improves drawdown by {(cap_dd-baseline_dd)*100:.2f} percentage points; EWMA targeting improves it by a further {(ewma_dd-cap_dd)*100:.2f} percentage points relative to cap-only. The gross cap alone therefore does not reproduce the full EWMA result in this historical sample.", "",
              "Baseline vs cap-only isolates the 4x cap intervention. Cap-only vs full targeting measures the additional effect of forecast-based scaling and its multiplier limit under the same gross cap. Diagonal vs covariance targeting compares risk models under identical targeting rules; EWMA changes variances as well as correlations.", "",
              "Differences are descriptive strategy comparisons, not an additive attribution of drawdown or proof of a causal covariance mechanism. Risk levels differ, parameters were not optimized here, and the historical sample is not an untouched holdout. Costs and missing-return assumptions match the main methodology."]
    (OUT / "cap_ablation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    for name in strategies:
        r = monthly[f"{name}_net_10bps"]
        ((1+r).cumprod()).plot(ax=axes[0], label=name)
        (r.rolling(12).std()*np.sqrt(12)).plot(ax=axes[1], label=name)
    axes[0].set_yscale("log")
    axes[0].set_title("Wealth after 10 bps costs (log scale)")
    axes[1].axhline(TARGET, color="black", linestyle="--", label="10% target")
    axes[1].set_title("Trailing 12-month realized volatility after 10 bps costs")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:
        ax.legend(fontsize=8)
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "targeting_comparison.png", dpi=160)
    plt.close(fig)
    (OUT / "methodology.md").write_text(
        "# Portfolio volatility targeting\n\n"
        "Fixed parameters: 10% annual portfolio volatility target, 4x gross exposure cap, "
        "2x maximum multiplier on baseline weights. No tuning to performance. "
        "All four models scale the same baseline positions; original baseline and a cap-only control are also reported. "
        "Cap-only applies min(1, 4/gross exposure), with no volatility targeting or position amplification. "
        "Formation-month forecasts use history through that month; weights execute one month later. "
        "Full pre-evaluation history is used for prior weights and initial evaluation turnover.\n\n"
        "Covariance estimation follows covariance_risk_validation.py (expanding pairwise covariance, "
        "six-month EWMA, fixed 50% shrinkage, 36-month overlap, PSD repair). "
        "Invalid forecasts cause zero exposure. Caps can prevent reaching target. "
        "Realized risk may exceed target even when forecast risk does not.\n\n"
        "Evaluation: January 1976–December 2014, same dates across strategies. Costs: "
        "0/5/10/25 bps per one-way target-weight change. Missing realized returns are zero-filled. "
        "No cash yield, financing, margin, position drift, roll costs or market impact. "
        "Sharpe assumes zero risk-free rate. Drawdowns include starting wealth of one. "
        "Subperiods 1976–1999 and 2000–2014 are descriptive stability checks, not untouched "
        "out-of-sample evidence: this full dataset was already examined. No parameter "
        "selection or fitted optimization is performed.\n\n"
        "Diagonal targeting versus baseline measures scaling and cap effects. Covariance targeting "
        "versus diagonal targeting measures model effects under common targeting rules. EWMA also "
        "changes marginal variances. No claim of optimal model selection is made.\n",
        encoding="utf-8",
    )
    print(summary[summary.cost_bps == 10].to_string(index=False))


if __name__ == "__main__":
    main()
