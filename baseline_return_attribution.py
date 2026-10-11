"""Attribute adjusted-baseline returns without changing the strategy.

This is item 4 of the baseline-analysis plan. It attributes the existing adjusted
TSMOM baseline by instrument, asset class, position direction, decade, drawdown
event, and an S&P 500 futures proxy bull/bear regime. It does not implement signal
diagnostics, performance extensions, or any covariance enhancement.
"""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strategy_backtest_adj import build_baseline, read_asset_map, read_returns


TRADING_MONTHS = 12
BEAR_THRESHOLD = -0.20
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "baseline_return_attribution_output"


def sp_futures_regimes(sp_returns: pd.Series) -> pd.DataFrame:
    """Classify peak-to-recovery episodes that breach -20% as bear regimes."""
    clean = sp_returns.dropna()
    wealth = (1.0 + clean).cumprod()
    regime = pd.Series("Bull", index=clean.index, dtype="object")
    events = []
    peak_pos = 0
    pos = 1
    while pos < len(wealth):
        if wealth.iloc[pos] >= wealth.iloc[peak_pos]:
            peak_pos = pos
            pos += 1
            continue
        drawdown = wealth.iloc[pos] / wealth.iloc[peak_pos] - 1.0
        if drawdown > BEAR_THRESHOLD:
            pos += 1
            continue

        trough_pos = pos
        recovery_pos = None
        scan = pos + 1
        while scan < len(wealth):
            if wealth.iloc[scan] < wealth.iloc[trough_pos]:
                trough_pos = scan
            if wealth.iloc[scan] >= wealth.iloc[peak_pos]:
                recovery_pos = scan
                break
            scan += 1

        end_pos = recovery_pos if recovery_pos is not None else len(wealth) - 1
        regime.iloc[peak_pos + 1 : end_pos + 1] = "Bear"
        events.append(
            {
                "peak_date": wealth.index[peak_pos],
                "trough_date": wealth.index[trough_pos],
                "recovery_date": wealth.index[recovery_pos]
                if recovery_pos is not None
                else pd.NaT,
                "maximum_drawdown": wealth.iloc[trough_pos] / wealth.iloc[peak_pos]
                - 1.0,
                "months_peak_to_trough": trough_pos - peak_pos,
                "months_peak_to_recovery": recovery_pos - peak_pos
                if recovery_pos is not None
                else np.nan,
            }
        )
        if recovery_pos is None:
            break
        peak_pos = recovery_pos
        pos = recovery_pos + 1

    output = pd.DataFrame(
        {
            "sp_futures_return": clean,
            "sp_futures_wealth": wealth,
            "sp_futures_drawdown": wealth / wealth.cummax() - 1.0,
            "regime": regime,
        }
    )
    return output, pd.DataFrame(events)


def contribution_summary(series: pd.Series) -> dict[str, float]:
    return {
        "annualized_mean_contribution": series.mean() * TRADING_MONTHS,
        "total_arithmetic_contribution": series.sum(),
        "monthly_contribution_volatility": series.std(),
        "positive_month_share": (series > 0).mean(),
    }


def drawdown_events(portfolio_returns: pd.Series) -> pd.DataFrame:
    """Return completed and unrecovered peak-to-trough portfolio drawdowns."""
    wealth = (1.0 + portfolio_returns.fillna(0.0)).cumprod()
    events = []
    peak_pos = 0
    pos = 1
    event_id = 0
    while pos < len(wealth):
        if wealth.iloc[pos] >= wealth.iloc[peak_pos]:
            peak_pos = pos
            pos += 1
            continue
        trough_pos = pos
        scan = pos + 1
        while scan < len(wealth) and wealth.iloc[scan] < wealth.iloc[peak_pos]:
            if wealth.iloc[scan] < wealth.iloc[trough_pos]:
                trough_pos = scan
            scan += 1
        recovery_pos = scan if scan < len(wealth) else None
        event_id += 1
        events.append(
            {
                "event_id": event_id,
                "peak_date": wealth.index[peak_pos],
                "trough_date": wealth.index[trough_pos],
                "recovery_date": wealth.index[recovery_pos]
                if recovery_pos is not None
                else pd.NaT,
                "maximum_drawdown": wealth.iloc[trough_pos] / wealth.iloc[peak_pos]
                - 1.0,
                "months_peak_to_trough": trough_pos - peak_pos,
                "months_peak_to_recovery": recovery_pos - peak_pos
                if recovery_pos is not None
                else np.nan,
            }
        )
        if recovery_pos is None:
            break
        peak_pos = recovery_pos
        pos = recovery_pos + 1
    return pd.DataFrame(events)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    asset_map = read_asset_map()
    baseline, _ = build_baseline(returns, asset_map)
    contributions = baseline["instrument_returns"].copy()
    execution_weights = baseline["execution_weights"].reindex(contributions.index)
    portfolio = baseline["returns"].reindex(contributions.index)
    metadata = asset_map.set_index("ID")
    class_lookup = metadata["AssetClass"].to_dict()

    instrument_rows = []
    for instrument in contributions.columns:
        row = {
            "ID": instrument,
            "Name": metadata.at[instrument, "Name"]
            if instrument in metadata.index
            else np.nan,
            "AssetClass": class_lookup.get(instrument),
        }
        row.update(contribution_summary(contributions[instrument]))
        instrument_rows.append(row)
    instrument_summary = pd.DataFrame(instrument_rows).sort_values(
        "annualized_mean_contribution", ascending=False
    )

    class_monthly = contributions.T.groupby(
        contributions.columns.map(class_lookup)
    ).sum().T
    class_summary = pd.DataFrame(
        [
            {"asset_class": column, **contribution_summary(class_monthly[column])}
            for column in class_monthly
        ]
    ).sort_values("annualized_mean_contribution", ascending=False)

    long_contribution = contributions.where(execution_weights > 0, 0.0).sum(axis=1)
    short_contribution = contributions.where(execution_weights < 0, 0.0).sum(axis=1)
    direction_monthly = pd.DataFrame(
        {
            "Long": long_contribution,
            "Short": short_contribution,
            "Total": portfolio,
        }
    )
    direction_summary = pd.DataFrame(
        [
            {"direction": column, **contribution_summary(direction_monthly[column])}
            for column in direction_monthly
        ]
    )

    decade = (contributions.index.year // 10 * 10).astype(str) + "s"
    decade_instrument = contributions.groupby(decade).mean() * TRADING_MONTHS
    decade_class = class_monthly.groupby(decade).mean() * TRADING_MONTHS
    decade_portfolio = portfolio.groupby(decade).mean() * TRADING_MONTHS

    regimes, sp_events = sp_futures_regimes(returns["SP"])
    regime_labels = regimes["regime"].reindex(contributions.index)
    regime_instrument = contributions.groupby(regime_labels).mean() * TRADING_MONTHS
    regime_class = class_monthly.groupby(regime_labels).mean() * TRADING_MONTHS
    regime_portfolio = portfolio.groupby(regime_labels).agg(["count", "mean", "std"])
    regime_portfolio["annualized_mean_return"] = regime_portfolio["mean"] * TRADING_MONTHS
    regime_portfolio["annualized_volatility"] = regime_portfolio["std"] * np.sqrt(
        TRADING_MONTHS
    )

    events = drawdown_events(portfolio)
    largest_events = events.nsmallest(5, "maximum_drawdown")
    event_attribution_rows = []
    for event in largest_events.itertuples(index=False):
        window = contributions.loc[event.peak_date : event.trough_date]
        totals = window.sum().sort_values()
        for instrument, value in totals.items():
            event_attribution_rows.append(
                {
                    "event_id": event.event_id,
                    "peak_date": event.peak_date,
                    "trough_date": event.trough_date,
                    "maximum_drawdown": event.maximum_drawdown,
                    "ID": instrument,
                    "Name": metadata.at[instrument, "Name"]
                    if instrument in metadata.index
                    else np.nan,
                    "AssetClass": class_lookup.get(instrument),
                    "arithmetic_contribution": value,
                }
            )
    event_attribution = pd.DataFrame(event_attribution_rows)

    reconciliation = pd.DataFrame(
        {
            "portfolio_return": portfolio,
            "sum_instrument_contributions": contributions.sum(axis=1),
            "difference": portfolio - contributions.sum(axis=1),
        }
    )

    contributions.to_csv(OUT_DIR / "monthly_instrument_contributions.csv")
    class_monthly.to_csv(OUT_DIR / "monthly_asset_class_contributions.csv")
    direction_monthly.to_csv(OUT_DIR / "monthly_direction_contributions.csv")
    instrument_summary.to_csv(OUT_DIR / "contribution_by_instrument.csv", index=False)
    class_summary.to_csv(OUT_DIR / "contribution_by_asset_class.csv", index=False)
    direction_summary.to_csv(OUT_DIR / "contribution_by_direction.csv", index=False)
    decade_instrument.to_csv(OUT_DIR / "contribution_by_decade_and_instrument.csv")
    decade_class.to_csv(OUT_DIR / "contribution_by_decade_and_asset_class.csv")
    decade_portfolio.rename("annualized_mean_return").to_csv(
        OUT_DIR / "portfolio_return_by_decade.csv"
    )
    regimes.to_csv(OUT_DIR / "sp_futures_proxy_regimes.csv")
    sp_events.to_csv(OUT_DIR / "sp_futures_proxy_bear_events.csv", index=False)
    regime_instrument.to_csv(OUT_DIR / "contribution_by_regime_and_instrument.csv")
    regime_class.to_csv(OUT_DIR / "contribution_by_regime_and_asset_class.csv")
    regime_portfolio.to_csv(OUT_DIR / "portfolio_return_by_regime.csv")
    events.to_csv(OUT_DIR / "drawdown_events.csv", index=False)
    event_attribution.to_csv(OUT_DIR / "drawdown_event_attribution.csv", index=False)
    reconciliation.to_csv(OUT_DIR / "contribution_reconciliation.csv")

    top = instrument_summary.head(12).sort_values("annualized_mean_contribution")
    bottom = instrument_summary.tail(12)
    plotted = pd.concat([bottom, top]).drop_duplicates("ID").sort_values(
        "annualized_mean_contribution"
    )
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(
        plotted["ID"],
        plotted["annualized_mean_contribution"],
        color=np.where(plotted["annualized_mean_contribution"] >= 0, "#1f4e79", "#c44e52"),
    )
    ax.axvline(0, color="#666666", linewidth=0.8)
    ax.set_title("Largest and smallest baseline return contributions by instrument")
    ax.set_xlabel("Annualized arithmetic contribution")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "instrument_contribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    class_summary.sort_values("annualized_mean_contribution").plot.barh(
        x="asset_class", y="annualized_mean_contribution", ax=axes[0], legend=False
    )
    direction_summary.plot.bar(
        x="direction", y="annualized_mean_contribution", ax=axes[1], legend=False
    )
    axes[0].set_title("Contribution by asset class")
    axes[0].set_xlabel("Annualized arithmetic contribution")
    axes[0].set_ylabel("Asset class")
    axes[0].xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[1].set_title("Contribution by position direction")
    axes[1].set_xlabel("Position direction")
    axes[1].set_ylabel("Annualized arithmetic contribution")
    axes[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[0].axvline(0, color="#666666", linewidth=0.8)
    axes[1].axhline(0, color="#666666", linewidth=0.8)
    axes[0].grid(axis="x", alpha=0.25)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "asset_class_and_direction_contribution.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    regime_class.T.plot.bar(ax=ax)
    ax.set_title("Annualized baseline contribution by S&P 500 futures proxy regime")
    ax.set_xlabel("Asset class")
    ax.set_ylabel("Annualized arithmetic contribution")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.axhline(0, color="#666666", linewidth=0.8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "asset_class_contribution_by_regime.png", dpi=180)
    plt.close(fig)

    max_reconciliation_error = reconciliation["difference"].abs().max()
    if max_reconciliation_error > 1e-12:
        raise AssertionError(f"Contribution reconciliation failed: {max_reconciliation_error}")
    print(f"Wrote return-attribution outputs to {OUT_DIR}")
    print(f"Maximum contribution reconciliation error: {max_reconciliation_error:.3g}")


if __name__ == "__main__":
    main()
