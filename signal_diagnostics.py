"""Test whether past futures returns contain information about subsequent returns.

This is items 1 and 2 of the baseline-analysis plan.

Item 1 measures monthly return autocorrelation at lags 1-12 and autocorrelation of
absolute and squared returns (volatility persistence), by instrument, asset class,
and period.

Item 2 tests the 1-, 3-, 6-, and 12-month momentum signals defined in
``strategy_backtest_adj.py``. It reports next-month returns after positive and
negative signals, the positive-minus-negative spread, directional hit rates, and
the signed (signal x return) return, by lookback, instrument, asset class, and period.

Timing follows the adjusted baseline: a signal formed with returns through month
t-1 is evaluated against the return earned in month t, and periods are assigned by
the month in which the return is earned. All available instrument history
(1969-2014) is used, not only the 1976+ baseline evaluation window, because the
information content of a signal does not depend on portfolio eligibility. The
vol-scaled signed return additionally requires the baseline's expanding-volatility
estimate (36 valid months). This script does not change the strategy.
"""

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from strategy_backtest_adj import (
    LECTURE_VOL_TARGET,
    MULTI_LOOKBACKS,
    expanding_volatility,
    momentum_signal,
    read_asset_map,
    read_returns,
)


TRADING_MONTHS = 12
LAGS = tuple(range(1, 13))
MIN_PERIOD_OBSERVATIONS = 36
HAC_LAGS = 3
MIN_HAC_MONTHS = 24
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "signal_diagnostics_output"


def period_labels(index: pd.DatetimeIndex) -> pd.Series:
    """Decade buckets; the short first (1969) and last (2010s) stubs are labelled by span."""
    years = index.year
    labels = np.select(
        [years < 1980, years < 1990, years < 2000, years < 2010],
        [f"{years.min()}-1979", "1980-1989", "1990-1999", "2000-2009"],
        default=f"2010-{years.max()}",
    )
    return pd.Series(labels, index=index)


# ---------------------------------------------------------------- item 1: autocorrelation


def autocorrelation_row(series: pd.Series) -> dict[str, float]:
    """Lag 1-12 autocorrelations, significance counts, and a Ljung-Box Q(12) test.

    Gaps are kept in place so that lag k always pairs months exactly k apart.
    """
    observations = int(series.count())
    row = {"observations": observations}
    rhos = []
    for lag in LAGS:
        rho = series.autocorr(lag) if observations > lag + 2 else np.nan
        row[f"lag_{lag}"] = rho
        rhos.append(rho)
    rhos = np.array(rhos)
    band = 1.96 / np.sqrt(observations) if observations > 0 else np.nan
    row["sum_lags_1_12"] = np.nansum(rhos) if np.isfinite(rhos).any() else np.nan
    row["significance_band_95"] = band
    row["significant_positive_lags"] = int((rhos > band).sum())
    row["significant_negative_lags"] = int((rhos < -band).sum())
    lags = np.array(LAGS)
    valid = np.isfinite(rhos) & (observations > lags)
    if valid.any():
        q_stat = observations * (observations + 2) * np.sum(
            rhos[valid] ** 2 / (observations - lags[valid])
        )
        row["ljung_box_q12"] = q_stat
        row["ljung_box_pvalue"] = stats.chi2.sf(q_stat, df=int(valid.sum()))
    else:
        row["ljung_box_q12"] = np.nan
        row["ljung_box_pvalue"] = np.nan
    return row


def measure_frames(returns: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"return": returns, "absolute": returns.abs(), "squared": returns.pow(2)}


def instrument_autocorrelation(
    returns: pd.DataFrame, asset_map: pd.DataFrame
) -> pd.DataFrame:
    metadata = asset_map.set_index("ID")
    rows = []
    for measure, frame in measure_frames(returns).items():
        for instrument in frame.columns:
            row = {
                "measure": measure,
                "ID": instrument,
                "Name": metadata.at[instrument, "Name"] if instrument in metadata.index else np.nan,
                "AssetClass": metadata.at[instrument, "AssetClass"]
                if instrument in metadata.index
                else np.nan,
            }
            row.update(autocorrelation_row(frame[instrument]))
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_autocorrelation(instrument_table: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Cross-instrument mean/median autocorrelation per lag, including an 'All' class."""
    table = pd.concat(
        [instrument_table, instrument_table.assign(AssetClass="All")], ignore_index=True
    )
    rows = []
    for key_values, group in table.groupby(keys + ["AssetClass"]):
        base = dict(zip(keys + ["asset_class"], key_values))
        for lag in LAGS:
            rho = group[f"lag_{lag}"]
            valid = rho.notna()
            rows.append(
                {
                    **base,
                    "lag": lag,
                    "instruments": int(valid.sum()),
                    "mean_autocorrelation": rho.mean(),
                    "median_autocorrelation": rho.median(),
                    "positive_share": (rho[valid] > 0).mean(),
                    "significant_positive_share": (
                        rho[valid] > group.loc[valid, "significance_band_95"]
                    ).mean(),
                    "significant_negative_share": (
                        rho[valid] < -group.loc[valid, "significance_band_95"]
                    ).mean(),
                }
            )
    return pd.DataFrame(rows)


def period_autocorrelation(returns: pd.DataFrame, asset_map: pd.DataFrame) -> pd.DataFrame:
    """Instrument autocorrelations within each period, then averaged by asset class."""
    periods = period_labels(returns.index)
    rows = []
    for period in periods.unique():
        subset = returns.loc[periods == period]
        enough = subset.count() >= MIN_PERIOD_OBSERVATIONS
        if not enough.any():
            continue
        table = instrument_autocorrelation(subset.loc[:, enough], asset_map)
        table.insert(0, "period", period)
        rows.append(table)
    instrument_table = pd.concat(rows, ignore_index=True)
    return summarize_autocorrelation(instrument_table, ["period", "measure"])


# ---------------------------------------------------------------- item 2: signal predictiveness


def to_long(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    return (
        frame.rename_axis("Date")
        .reset_index()
        .melt(id_vars="Date", var_name="ID", value_name=name)
    )


def signal_panel(returns: pd.DataFrame, asset_map: pd.DataFrame) -> pd.DataFrame:
    """Instrument-month panel of lagged signals and the returns they are evaluated against."""
    volatility = expanding_volatility(returns).shift(1)
    class_lookup = asset_map.set_index("ID")["AssetClass"]
    panels = []
    for lookback in MULTI_LOOKBACKS:
        signal = momentum_signal(returns, lookback).shift(1)
        panel = (
            to_long(signal, "signal")
            .merge(to_long(returns, "forward_return"), on=["Date", "ID"])
            .merge(to_long(volatility, "formation_volatility"), on=["Date", "ID"])
        )
        # Exact-zero trailing sums carry no direction and are excluded.
        panel = panel.dropna(subset=["signal", "forward_return"])
        panel = panel.loc[panel["signal"] != 0].copy()
        panel["lookback"] = lookback
        panels.append(panel)

    panel = pd.concat(panels, ignore_index=True)
    panel["AssetClass"] = panel["ID"].map(class_lookup)
    panel["period"] = period_labels(pd.DatetimeIndex(panel["Date"])).to_numpy()
    panel["signed_return"] = panel["signal"] * panel["forward_return"]
    panel["vol_scaled_signed_return"] = (
        panel["signed_return"] * LECTURE_VOL_TARGET / panel["formation_volatility"]
    )
    direction = np.sign(panel["forward_return"])
    panel["hit"] = (direction == panel["signal"]).astype(float).where(direction != 0)
    return panel


def hac_mean_tstat(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < MIN_HAC_MONTHS or clean.std() == 0:
        return np.nan
    fit = sm.OLS(clean.to_numpy(), np.ones(len(clean))).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}
    )
    return float(fit.tvalues[0])


def predictiveness_summary(group: pd.DataFrame) -> dict[str, float]:
    """Pooled conditional returns and hit rates, plus a time-series test of signed returns.

    Instrument-months within a month are cross-sectionally correlated, so inference uses
    the monthly equal-weighted average signed return with HAC standard errors.
    """
    positive = group.loc[group["signal"] > 0]
    negative = group.loc[group["signal"] < 0]
    monthly_signed = group.groupby("Date")["signed_return"].mean()
    monthly_scaled = group.groupby("Date")["vol_scaled_signed_return"].mean().dropna()
    scaled_vol = monthly_scaled.std() * np.sqrt(TRADING_MONTHS)
    return {
        "instrument_months": len(group),
        "months": int(monthly_signed.size),
        "instruments": int(group["ID"].nunique()),
        "positive_signal_share": len(positive) / len(group) if len(group) else np.nan,
        "mean_return_after_positive": positive["forward_return"].mean(),
        "mean_return_after_negative": negative["forward_return"].mean(),
        "return_spread_positive_minus_negative": positive["forward_return"].mean()
        - negative["forward_return"].mean(),
        "hit_rate": group["hit"].mean(),
        "positive_signal_hit_rate": positive["hit"].mean(),
        "negative_signal_hit_rate": negative["hit"].mean(),
        "mean_signed_return": group["signed_return"].mean(),
        "annualized_signed_return": monthly_signed.mean() * TRADING_MONTHS,
        "signed_return_hac_t": hac_mean_tstat(monthly_signed),
        "annualized_vol_scaled_signed_return": monthly_scaled.mean() * TRADING_MONTHS,
        "vol_scaled_sharpe_0rf": monthly_scaled.mean() * TRADING_MONTHS / scaled_vol
        if scaled_vol > 0
        else np.nan,
        "vol_scaled_signed_return_hac_t": hac_mean_tstat(monthly_scaled),
    }


def grouped_predictiveness(panel: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    for key_values, group in panel.groupby(keys):
        row = dict(zip(keys, key_values))
        row.update(predictiveness_summary(group))
        rows.append(row)
    return pd.DataFrame(rows)


def with_all_class(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([panel, panel.assign(AssetClass="All")], ignore_index=True)


def directional_hit_rates(panel: pd.DataFrame, by_instrument: pd.DataFrame) -> pd.DataFrame:
    """Pooled hit rates by lookback and class, plus how many instruments beat 50%."""
    rows = []
    instruments = with_all_class(by_instrument)
    for (lookback, asset_class), group in with_all_class(panel).groupby(
        ["lookback", "AssetClass"]
    ):
        hits = group["hit"].dropna()
        members = instruments.loc[
            (instruments["lookback"] == lookback) & (instruments["AssetClass"] == asset_class)
        ]
        rows.append(
            {
                "lookback": lookback,
                "asset_class": asset_class,
                "directional_observations": len(hits),
                "hit_rate": hits.mean(),
                "hit_rate_minus_50pct": hits.mean() - 0.5,
                "positive_signal_hit_rate": group.loc[group["signal"] > 0, "hit"].mean(),
                "negative_signal_hit_rate": group.loc[group["signal"] < 0, "hit"].mean(),
                "instruments": len(members),
                "instruments_with_hit_rate_above_50pct": int((members["hit_rate"] > 0.5).sum()),
                "share_instruments_above_50pct": (members["hit_rate"] > 0.5).mean(),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- plots


def plot_return_autocorrelation(by_class: pd.DataFrame, by_period: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    returns_by_class = by_class.loc[by_class["measure"] == "return"]
    for asset_class, group in returns_by_class.groupby("asset_class"):
        style = {"color": "black", "linewidth": 2.4} if asset_class == "All" else {"linewidth": 1.4}
        axes[0].plot(group["lag"], group["mean_autocorrelation"], marker="o", label=asset_class, **style)
    axes[0].set_title("Mean return autocorrelation by asset class")

    returns_by_period = by_period.loc[
        (by_period["measure"] == "return") & (by_period["asset_class"] == "All")
    ]
    for period, group in returns_by_period.groupby("period"):
        axes[1].plot(group["lag"], group["mean_autocorrelation"], marker="o", label=period)
    axes[1].set_title("Mean return autocorrelation by period (all instruments)")

    for ax in axes:
        ax.axhline(0, color="#666666", linewidth=0.8)
        ax.set_xlabel("Lag (months)")
        ax.set_xticks(LAGS)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel("Cross-instrument mean autocorrelation")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "return_autocorrelation_lags.png", dpi=180)
    plt.close(fig)


def plot_volatility_autocorrelation(by_class: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    for ax, measure in zip(axes, ("absolute", "squared")):
        subset = by_class.loc[by_class["measure"] == measure]
        for asset_class, group in subset.groupby("asset_class"):
            style = {"color": "black", "linewidth": 2.4} if asset_class == "All" else {"linewidth": 1.4}
            ax.plot(group["lag"], group["mean_autocorrelation"], marker="o", label=asset_class, **style)
        ax.set_title(f"Mean autocorrelation of {measure} returns")
        ax.axhline(0, color="#666666", linewidth=0.8)
        ax.set_xlabel("Lag (months)")
        ax.set_xticks(LAGS)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel("Cross-instrument mean autocorrelation")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "volatility_autocorrelation_lags.png", dpi=180)
    plt.close(fig)


def plot_signal_spread(by_lookback: pd.DataFrame, by_class: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(by_lookback))
    labels = [f"{lb}m" for lb in by_lookback["lookback"]]
    axes[0].bar(x - 0.2, by_lookback["mean_return_after_positive"], 0.4, label="After positive signal", color="#1f4e79")
    axes[0].bar(x + 0.2, by_lookback["mean_return_after_negative"], 0.4, label="After negative signal", color="#c44e52")
    axes[0].set_xticks(x, labels)
    axes[0].set_title("Mean next-month return after positive and negative signals")
    axes[0].legend(frameon=False)

    pivot = by_class.pivot(
        index="lookback", columns="AssetClass", values="return_spread_positive_minus_negative"
    )
    pivot.index = [f"{lb}m" for lb in pivot.index]
    pivot.plot.bar(ax=axes[1], rot=0)
    axes[1].set_title("Positive-minus-negative return spread by asset class")
    axes[1].legend(frameon=False, fontsize=8)

    for ax in axes:
        ax.axhline(0, color="#666666", linewidth=0.8)
        ax.set_xlabel("Signal lookback")
        ax.set_ylabel("Monthly return")
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "signal_return_spread_by_lookback.png", dpi=180)
    plt.close(fig)


def plot_hit_rates(hit_rates: pd.DataFrame) -> None:
    pivot = hit_rates.pivot(index="asset_class", columns="lookback", values="hit_rate")
    pivot.columns = [f"{lb}m" for lb in pivot.columns]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    pivot.plot.bar(ax=ax, rot=0)
    ax.axhline(0.5, color="#c44e52", linewidth=1.0, linestyle="--", label="50%")
    lower = max(0.0, np.floor(pivot.min().min() * 20) / 20 - 0.05)
    ax.set_ylim(lower, min(1.0, pivot.max().max() + 0.05))
    ax.set_title("Directional hit rate by asset class and lookback")
    ax.set_xlabel("Asset class")
    ax.set_ylabel("Share of instrument-months with correct direction")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, title="Lookback", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "signal_hit_rate_by_asset_class.png", dpi=180)
    plt.close(fig)


def plot_predictiveness_by_period(by_period: pd.DataFrame) -> None:
    subset = by_period.loc[by_period["AssetClass"] == "All"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    panels = [
        ("return_spread_positive_minus_negative", "Positive-minus-negative spread", True),
        ("hit_rate", "Directional hit rate", True),
        ("annualized_vol_scaled_signed_return", "Annualized vol-scaled signed return", True),
    ]
    for ax, (column, title, percent) in zip(axes, panels):
        pivot = subset.pivot(index="period", columns="lookback", values=column)
        pivot.columns = [f"{lb}m" for lb in pivot.columns]
        pivot.plot(ax=ax, marker="o")
        ax.set_title(title)
        ax.set_xlabel("Period (return month)")
        ax.axhline(0.5 if column == "hit_rate" else 0.0, color="#666666", linewidth=0.8)
        if percent:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.tick_params(axis="x", rotation=20)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, title="Lookback", fontsize=8)
    fig.suptitle("Signal predictiveness by period, all instruments")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "signal_predictiveness_by_period.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    asset_map = read_asset_map()

    # Item 1: autocorrelation.
    instrument_ac = instrument_autocorrelation(returns, asset_map)
    class_ac = summarize_autocorrelation(instrument_ac, ["measure"])
    period_ac = period_autocorrelation(returns, asset_map)

    # Item 2: signal predictiveness.
    panel = signal_panel(returns, asset_map)
    by_lookback = grouped_predictiveness(panel, ["lookback"])
    by_class = grouped_predictiveness(panel, ["lookback", "AssetClass"])
    by_instrument = grouped_predictiveness(panel, ["lookback", "ID", "AssetClass"])
    by_period = grouped_predictiveness(with_all_class(panel), ["lookback", "period", "AssetClass"])
    hit_rates = directional_hit_rates(panel, by_instrument)

    instrument_ac.loc[instrument_ac["measure"] == "return"].drop(columns="measure").to_csv(
        OUT_DIR / "return_autocorrelation_by_instrument.csv", index=False
    )
    class_ac.to_csv(OUT_DIR / "return_autocorrelation_by_asset_class.csv", index=False)
    instrument_ac.loc[instrument_ac["measure"] != "return"].to_csv(
        OUT_DIR / "volatility_autocorrelation.csv", index=False
    )
    period_ac.to_csv(OUT_DIR / "autocorrelation_by_period.csv", index=False)
    by_lookback.to_csv(OUT_DIR / "signal_predictiveness_by_lookback.csv", index=False)
    by_class.to_csv(OUT_DIR / "signal_predictiveness_by_asset_class.csv", index=False)
    by_instrument.to_csv(OUT_DIR / "signal_predictiveness_by_instrument.csv", index=False)
    by_period.to_csv(OUT_DIR / "signal_predictiveness_by_period.csv", index=False)
    hit_rates.to_csv(OUT_DIR / "directional_hit_rates.csv", index=False)

    plot_return_autocorrelation(class_ac, period_ac)
    plot_volatility_autocorrelation(class_ac)
    plot_signal_spread(by_lookback, by_class)
    plot_hit_rates(hit_rates)
    plot_predictiveness_by_period(by_period)

    print(f"Wrote signal-diagnostics outputs to {OUT_DIR}")
    all_returns = class_ac.loc[(class_ac["measure"] == "return") & (class_ac["asset_class"] == "All")]
    print("\nMean return autocorrelation, all instruments:")
    print(all_returns[["lag", "instruments", "mean_autocorrelation", "positive_share"]].round(4).to_string(index=False))
    columns = [
        "lookback",
        "instrument_months",
        "return_spread_positive_minus_negative",
        "hit_rate",
        "annualized_vol_scaled_signed_return",
        "vol_scaled_sharpe_0rf",
        "vol_scaled_signed_return_hac_t",
    ]
    print("\nSignal predictiveness by lookback:")
    print(by_lookback[columns].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
