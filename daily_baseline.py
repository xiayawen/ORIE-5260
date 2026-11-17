"""Lecture 11 baseline on daily data, rebalanced every 21 business days (slides 17-21 and 30).

Slide 21 / 30 baseline: binary 12-month signal, 12-month volatility scaling, 11% ex-ante volatility
target, 21-business-day holding periods, net of 2 bps per unit turnover + 4 rolls a year at 2 bps.
This script rebuilds it from the daily back-adjusted closes (`*_RAD.CSV`), which reproduce the
monthly returns in MonthlyReturns_FullSample.xlsx exactly at month ends.

Specification (fixed before any result was computed):
- Universe: the 58 markets of MonthlyReturns_FullSample.xlsx (primary) and, as a check, all 66 markets of the
  course AssetMapCsv.csv (adds BC, BG, EN, ER, ES, FF, SC, ZH); daily return = close-to-close % change.
- Rebalance grid: every 21 rows of the union trading calendar, anchored so 31 Dec 2014 is a rebalance date.
- Signal: sign of the trailing 252-day compounded return. Vol: std of the trailing 252 daily returns x sqrt(252)
  (at least 200 observations). Raw weight = signal / vol / N over markets with both.
- Ex-ante target (primary): book scaled to 11% predicted vol, covariance = trailing 252-day daily sample
  covariance (pairwise) x 252. Variants: EWMA covariance of daily returns (126-day half-life), and the
  realized-vol replica (10% on trailing 36 periods of realized strategy vol). No caps in any version.
- Weights formed at the close of a rebalance date earn the next 21 days' compounded returns.
- Costs as combined_strategy.Pipeline.evaluate: roll = sum|w| x 2bp x 4/12 per period; grown = w x (1 + r - roll);
  turnover = sum|w - grown|; cost = 2bp x turnover + roll. 12 periods a year (252 / 21).

    python daily_baseline.py            # needs ../FuturesUnderlyingData_FullSample (or DAILY_FULL_DIR)
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

from risk_budgeting import read_full_sample_returns

ROOT = Path(__file__).resolve().parent
DAILY_DIR = Path(os.environ.get("DAILY_FULL_DIR", ROOT.parent / "FuturesUnderlyingData_FullSample"))
OUT = ROOT / "outputs" / "daily_baseline_output"
STEP, YEAR, MIN_OBS, HALFLIFE = 21, 252, 200, 126
PER_YEAR = YEAR / STEP
C = 2.0 / 1e4
TARGET_EXANTE, TARGET_REALIZED = 0.11, 0.10
ANCHOR = pd.Timestamp("2014-12-31")
ANCHOR_OFFSETS = (0, 3, 6, 9, 12, 15, 18)
PERIODS = {"IS 1976-2014": ("1976-01-01", "2014-12-31"), "OOS 2015-2025": ("2015-01-01", "2025-06-30")}
SLIDES = {"IS 1976-2014": dict(annual_net_return=0.111, annual_volatility=0.099, net_sharpe=1.13,
                               annual_turnover=13.42, annual_cost_drag=0.0059, average_gross_exposure=4.0,
                               average_names=39.5, average_net_exposure=1.3),
          "OOS 2015-2025": dict(annual_net_return=0.030, annual_volatility=0.095, net_sharpe=0.31,
                                annual_turnover=30.46, annual_cost_drag=np.nan, average_gross_exposure=7.94,
                                average_names=56.3, average_net_exposure=2.7)}


def read_daily_returns(ids):
    """Daily close-to-close returns on the union calendar (NaN where a market does not trade)."""
    out = {}
    for i in ids:
        path = DAILY_DIR / f"{i}_RAD.CSV"
        if not path.exists():
            path = DAILY_DIR / f"{i}__RAD.CSV"
        d = pd.read_csv(path, header=None, usecols=[0, 4], names=["date", "close"])
        d["date"] = pd.to_datetime(d["date"], format="%m/%d/%Y")
        close = d.set_index("date")["close"]
        out[i] = close[close > 0].pct_change().iloc[1:]
    return pd.DataFrame(out).sort_index()


def rebalance_dates(index, anchor_date=ANCHOR):
    anchor = index.get_indexer([anchor_date], method="pad")[0]
    return index[anchor % STEP::STEP]


def formation_inputs(daily, dates):
    """Signal and vol at each rebalance date, from the trailing 252 trading days of that market."""
    filled = np.log1p(daily)
    trailing_ret = filled.rolling(YEAR, min_periods=MIN_OBS).sum()
    vol = daily.rolling(YEAR, min_periods=MIN_OBS).std() * np.sqrt(YEAR)
    # a market must still be trading: a print within the last 5 days
    live = daily.notna().rolling(5, min_periods=1).sum().gt(0)
    signal = np.sign(trailing_ret).where(live)
    return signal.loc[dates], vol.where(live).loc[dates]


def raw_weights(signal, vol):
    raw = signal / vol
    valid = raw.notna() & signal.ne(0)
    return raw.where(valid).div(valid.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)


def forecast_vol(daily, raw, method):
    out = pd.Series(np.nan, index=raw.index)
    for date, w in raw.iterrows():
        active = w.index[w.ne(0)]
        if not len(active):
            continue
        window = daily.loc[:date, active]
        if method == "sample":
            cov = window.iloc[-YEAR:].cov(min_periods=MIN_OBS // 2).fillna(0.0).to_numpy() * YEAR
        else:  # EWMA, half-life 126 days, last 4 half-lives
            x = window.iloc[-4 * HALFLIFE:]
            weights = 0.5 ** (np.arange(len(x))[::-1] / HALFLIFE)
            demeaned = (x - x.mul(weights, axis=0).sum() / x.notna().mul(weights, axis=0).sum()).fillna(0.0)
            cov = (demeaned.mul(weights, axis=0).T @ demeaned).to_numpy() / weights.sum() * YEAR
        v = w[active].to_numpy()
        out[date] = np.sqrt(max(float(v @ cov @ v), 0.0))
    return out


def period_returns(daily, dates):
    """Compounded return of each market over (date_k, date_{k+1}], indexed by the period end."""
    wealth = (1 + daily.fillna(0.0)).cumprod()
    level = wealth.loc[dates]
    r = level / level.shift(1) - 1
    traded = daily.notna().astype(int).cumsum().loc[dates].diff().gt(0)
    return r.where(traded).iloc[1:]


def evaluate(formed, r):
    """formed: weights at rebalance dates; r: period returns indexed by period end."""
    executed = formed.shift(1).reindex(r.index).fillna(0.0)
    rr = r.fillna(0.0)
    gross = (executed * rr).sum(axis=1)
    exposure = executed.abs().sum(axis=1)
    roll = exposure * C * 4 / 12
    grown = executed.mul(1 + rr).sub(executed.mul(roll, axis=0)).shift(1).fillna(0)
    turnover = (executed - grown).abs().sum(axis=1)
    cost = turnover * C + roll
    return pd.DataFrame({"gross": gross, "net": gross - cost, "cost": cost, "turnover": turnover,
                         "gross_exposure": exposure, "net_exposure": executed.sum(axis=1),
                         "names": executed.ne(0).sum(axis=1)})


def stats(s, start, end):
    s = s.loc[start:end]
    vol = s.net.std() * np.sqrt(PER_YEAR)
    wealth = (1 + s.net).cumprod()
    return {"periods": len(s), "first_end": f"{s.index.min():%Y-%m-%d}", "last_end": f"{s.index.max():%Y-%m-%d}",
            "annual_gross_return": s.gross.mean() * PER_YEAR, "annual_net_return": s.net.mean() * PER_YEAR,
            "annual_volatility": vol, "net_sharpe": s.net.mean() * PER_YEAR / vol,
            "max_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min(),
            "annual_turnover": s.turnover.mean() * PER_YEAR, "annual_cost_drag": s.cost.mean() * PER_YEAR,
            "average_gross_exposure": s.gross_exposure.mean(), "average_net_exposure": s.net_exposure.mean(),
            "average_names": s.names.mean()}


def build(daily, anchor_date=ANCHOR):
    dates = rebalance_dates(daily.index, anchor_date)
    signal, vol = formation_inputs(daily, dates)
    raw = raw_weights(signal, vol)
    r = period_returns(daily, dates)
    out = {}
    for name, method in (("exante_11_sample", "sample"), ("exante_11_ewma", "ewma")):
        f = forecast_vol(daily, raw, method)
        out[name] = raw.mul((TARGET_EXANTE / f).where(f > 0, 0.0).fillna(0.0), axis=0)
    # realized replica: scale by trailing 36-period realized vol of the unscaled book (known at t)
    unscaled = (raw.shift(1).reindex(r.index).fillna(0.0) * r.fillna(0.0)).sum(axis=1)
    realized = unscaled.rolling(36, min_periods=36).std() * np.sqrt(PER_YEAR)
    out["realized_10_36p"] = raw.mul((TARGET_REALIZED / realized).reindex(raw.index), axis=0).fillna(0.0)
    return {k: evaluate(w, r) for k, w in out.items()}, out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ids58 = list(read_full_sample_returns().columns)
    ids66 = ids58 + sorted(set(pd.read_csv(ROOT / "AssetMapCsv.csv").ID) - set(ids58))
    results, daily = {}, {}
    for tag, ids in (("58", ids58), ("66", ids66)):
        daily[tag] = read_daily_returns(ids)
        res, _ = build(daily[tag])
        results.update({f"{name}_u{tag}": s for name, s in res.items()})
    rows = []
    for name, s in results.items():
        for period, (start, end) in PERIODS.items():
            rows.append({"strategy": name, "period": period, **stats(s, start, end)})
        s.to_csv(OUT / f"periods_{name}.csv")
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "daily_baseline_stats.csv", index=False)
    metrics = [("annual_net_return", "Avg net return", "{:.1%}"), ("annual_gross_return", "Avg gross return", "{:.1%}"),
               ("annual_volatility", "Std", "{:.1%}"), ("net_sharpe", "Sharpe", "{:.2f}"),
               ("max_drawdown", "Max DD", "{:.1%}"), ("annual_turnover", "Turnover", "{:.2f}"),
               ("annual_cost_drag", "T-costs", "{:.2%}"), ("average_gross_exposure", "Leverage", "{:.2f}"),
               ("average_names", "#Names", "{:.1f}"), ("average_net_exposure", "Imbalance", "{:.2f}")]
    lines = []
    for period in PERIODS:
        sub = table[table.period == period].set_index("strategy")
        lines += [f"## {period}", "", "| | Slide | " + " | ".join(sub.index) + " |",
                  "|---|---:|" + "---:|" * len(sub)]
        for k, lab, f in metrics:
            ref = SLIDES[period].get(k, np.nan)
            lines.append(f"| {lab} | {'—' if pd.isna(ref) else f.format(ref)} | "
                         + " | ".join(f.format(sub.loc[n, k]) for n in sub.index) + " |")
        lines.append("")
    # Diagnostic, not a choice: the same strategies with the 21-day grid shifted (58 markets).
    shifts = []
    for offset in ANCHOR_OFFSETS:
        res = results if offset == 0 else build(daily["58"], ANCHOR + pd.offsets.BDay(offset))[0]
        for name in ("exante_11_sample", "exante_11_ewma", "realized_10_36p"):
            s = res[f"{name}_u58"] if offset == 0 else res[name]
            for period, (start, end) in PERIODS.items():
                shifts.append({"offset_days": offset, "strategy": name, "period": period,
                               "net_sharpe": stats(s, start, end)["net_sharpe"]})
    shifts = pd.DataFrame(shifts)
    shifts.to_csv(OUT / "anchor_sensitivity.csv", index=False)
    grid = shifts.pivot_table(index="offset_days", columns=["period", "strategy"], values="net_sharpe")
    cols = list(grid.columns)
    sens = ["## Sensitivity to the rebalance grid (58 markets, net Sharpe)", "",
            "The same strategies with the 21-business-day grid started 0-18 business days after 31 Dec 2014. "
            "Offset 0 is the specification above. Nothing is chosen from this table: it shows how much of a "
            "10-year Sharpe ratio depends on which days the book happens to rebalance.", "",
            "| Offset (days) | " + " | ".join(f"{p.split()[0]} {n}" for p, n in cols) + " |",
            "|---:|" + "---:|" * len(cols)]
    sens += [f"| {o} | " + " | ".join(f"{grid.loc[o, c]:.2f}" for c in cols) + " |" for o in grid.index]
    sens += ["| **Mean** | " + " | ".join(f"**{grid[c].mean():.2f}**" for c in cols) + " |",
             "| Min - max | " + " | ".join(f"{grid[c].min():.2f} - {grid[c].max():.2f}" for c in cols) + " |", "",
             "## Reading", "",
             "- With the grid anchored at 31 Dec 2014 (offset 0), OOS net return matches slide 30 (3.2% vs 3.0%), "
             f"but the OOS Sharpe of the primary version ranges from {grid[cols[4]].min():.2f} to "
             f"{grid[cols[4]].max():.2f} across grid starts (mean {grid[cols[4]].mean():.2f}), all below slide 30's "
             "0.31; offset 0 happens to be the highest.",
             "- Leverage, volatility and turnover are 35-55% above slides 21/30 in both periods, so the scale of the "
             "book (how much low-volatility rate futures it holds) still differs from the professor's.",
             "- The 66-market course asset map adds Fed funds futures (FF), whose tiny volatility pushes leverage to "
             "about 22x; the 58-market universe is the closer match.", ""]
    (OUT / "daily_baseline_report.md").write_text(
        "# Lecture 11 baseline on daily data (21-business-day periods)\n\n" + __doc__.split("    python")[0]
        + "\n" + "\n".join(lines + sens), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
