"""Combined strategy: forward stepwise selection of enhancements on 1976-2014, then one OOS run.

Start: `enhanced` (12-month sign, EWMA-vol 40%/sigma/N sizing, EWMA-covariance 10% target,
4x gross / 2x scale caps). Candidates, each re-implemented on our monthly data and the
enhanced construction (never on the economic_trend.py "shared baseline"), with every
parameter fixed as previously chosen on pre-2015 data:

  risk_budget                R2 core (risk_budgeting.py): 25% ex-ante risk per asset class
                             replaces the enhanced sizing; 10% target, 4x cap
  economic_trend             20% sleeve of the five macro themes (economic_trend.py: signs,
                             3-month smoothing, US-relevant universe; chosen on 1980-1997)
  factor_overlay             20% NegativeSkew_12m cross-sectional sleeve (tsmom_factor_overlay.py,
                             chosen on 1995-2004)
  turning_point              halve a position when its 2m and 12m signs disagree AND >=4 of 5
                             macro themes oppose the 12m signal (turning_point_model, 1980-2014)
  half_short                 multiply short weights by 0.5 (short_budget_backtest.py) *
  net_cap                    |net exposure| <= 1x, trim the larger side (net_exposure_backtest.py)
  smooth_leverage            3-month smoothing of gross exposure (exposure_smoothing_backtest.py) *
  smooth_leverage_imbalance  ... and of the net share, 1.25x side cap *
  band_25                    +/-25% no-trade band on drifted weights (cost_aware_rebalance.py)

  * designed after the 2015-2025 data had been examined: 2015+ results are not a clean OOS test.

Pipeline order (fixed in advance): core -> blend sleeves (20% each, core keeps the rest) and
re-target to 10% with the EWMA covariance and 4x/2x caps -> turning_point -> half_short ->
net_cap -> smoothing -> 4x gross cap -> execution (band_25 or full rebalance).

Rebalance frequency (rebalance_frequency_backtest.py) is excluded: weekly/daily trading needs
daily closes after 2014, which are not available, so it could not be tested out of sample.

Selection protocol: the stepwise search runs on returns truncated at Dec 2014 (no 2015+ value is
loaded). A candidate is added only if it raises IS net Sharpe (Lecture 8 cost model, $1bn, 5-day
impact, drift turnover) by >= 0.05. The final phase reruns everything on the full sample once and
asserts that the IS numbers are unchanged.

Run from the project root:  python combined_strategy.py
"""

import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/orie5260-matplotlib")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import economic_trend as econ
from cost_aware_rebalance import rebalance_path
from covariance_risk_validation import covariance, HALFLIFE
from exposure_smoothing_backtest import smooth_exposure
from futures_factor_backtest import build_signals
from net_exposure_backtest import net_cap_weights
from portfolio_volatility_targeting import GROSS_CAP, cap_only_weights, target_weights
from risk_budgeting import ROOT, IS_START, IS_END, OOS_START, read_full_sample_returns, risk_budget_weights
from short_budget_backtest import short_budget
from strategy_backtest_adj import (
    read_asset_map, momentum_signal, expanding_volatility, ewma_volatility, tsmom_weights, BASELINE_LOOKBACK,
)
from transaction_cost_model import (
    DEFAULT_PARAMETERS, trailing_contract_volume, instrument_adv_usd, cost_breakdown, trade_weights,
)
from turning_point_model.macro_features import (
    economic_confirmation_features, four_of_five_opposition, macro_confirmed_binary_weights,
)
from turning_point_model.regime_features import disagreement_from_signals

OUT = ROOT / "outputs" / "combined_strategy_output"
MACRO_DIR = ROOT / "macro_data"
TARGET = 0.10
THRESHOLD = 0.05
SLEEVE_WEIGHT = {"economic_trend": econ.ENHANCED_WEIGHT, "factor_overlay": 0.20, "histgb_overlay": 0.30}
FACTOR = "NegativeSkew_12m"
HISTGB_WINDOW = 15        # rolling_sign_prediction.py: 15y window and 30% blend chosen on 2000-2004 validation
WF_FIRST_YEAR = 1990      # first return year traded with a walk-forward selection (fixed in advance)
TURNING_ALPHA = 0.50
HALF_SHORT = 0.50
BAND = ("band", 0.25)
PERIODS = {"IS 1976-2014": (IS_START, IS_END), "WF 1990-2014": ("1990-01-01", IS_END),
           "OOS 2015-2025": (OOS_START, None)}

COMPONENTS = {
    "risk_budget": "R2 risk budget core (25% risk per asset class)",
    "economic_trend": "Economic trend sleeve, 20%",
    "factor_overlay": "NegativeSkew_12m factor sleeve, 20%",
    "turning_point": "Turning point: halve when 2m/12m disagree and >=4/5 macro oppose",
    "half_short": "Half-sized shorts (x0.5)",
    "net_cap": "Net exposure cap +/-1x",
    "smooth_leverage": "Smooth gross leverage (3m)",
    "smooth_leverage_imbalance": "Smooth leverage and imbalance (3m)",
    "band_25": "No-trade band +/-25%",
    "histgb_overlay": "HistGB sign-forecast sleeve, 30% (15y rolling, refit yearly, live from 1997)",
}
EXCLUSIVE = [{"smooth_leverage", "smooth_leverage_imbalance"}]
POST_2015_DESIGN = {"half_short", "smooth_leverage", "smooth_leverage_imbalance"}
CLEAN_POOL = tuple(c for c in COMPONENTS if c not in POST_2015_DESIGN)
SLEEVES = ("economic_trend", "factor_overlay", "histgb_overlay")
ALL_COMPONENTS = frozenset(COMPONENTS) - {"smooth_leverage"}  # superset used by the look-ahead test


def ewma_forecast(returns, weights):
    """Predicted annual vol of each formation-date weight vector (6m EWMA covariance through t)."""
    out = pd.Series(np.nan, index=weights.index)
    for date, row in weights.iterrows():
        row = row.fillna(0)
        active = row.index[row.ne(0)]
        if len(active):
            w = row[active].to_numpy()
            cov = covariance(returns.loc[:date, active], HALFLIFE)[0]
            out[date] = np.sqrt(max(float(w @ cov @ w), 0.0))
    return out


class Pipeline:
    """Builds formation and executed weights for any component set on one return panel."""

    def __init__(self, returns, asset_map=None, macro_dir=MACRO_DIR):
        self.r = returns
        self.asset_map = read_asset_map() if asset_map is None else asset_map
        self.asset_class = self.asset_map.set_index("ID")["AssetClass"].reindex(returns.columns)
        self.macro_dir = macro_dir
        self.signal = momentum_signal(returns, BASELINE_LOOKBACK)
        self.exp_vol = expanding_volatility(returns)
        self.ewma_vol = ewma_volatility(returns)
        # Sleeves trade only markets with 12 consecutive observed months (EWMA vol alone is
        # carried forward after a market stops trading).
        live = returns.notna().rolling(12, min_periods=12).sum().eq(12)
        self.sleeve_vol = self.ewma_vol.where(live)
        volume = trailing_contract_volume(returns.index, returns.columns)
        self.adv, _ = instrument_adv_usd(volume, self.asset_class, DEFAULT_PARAMETERS)
        self._cache = {}

    def _cached(self, key, build):
        if key not in self._cache:
            self._cache[key] = build()
        return self._cache[key]

    def scale_to_target(self, weights):
        """Unconstrained scaling of a sleeve to 10% predicted vol (used before blending)."""
        forecast = ewma_forecast(self.r, weights)
        scale = (TARGET / forecast).where(forecast > 0, 0.0).fillna(0.0)
        return weights.mul(scale, axis=0)

    def retarget(self, weights):
        return target_weights(weights, ewma_forecast(self.r, weights).reindex(weights.index))[0].fillna(0)

    # ---------------------------------------------------------------- building blocks
    def course_baseline(self):
        return self._cached("course", lambda: tsmom_weights(self.signal, self.exp_vol, self.asset_map).fillna(0))

    def core(self, risk_budget):
        if risk_budget:
            return self._cached("core_rb", lambda: risk_budget_weights(
                self.r, self.signal, self.exp_vol.notna(), self.asset_class, "ewma", TARGET, GROSS_CAP)[0])
        return self._cached("core_enh", lambda: self.retarget(
            tsmom_weights(self.signal, self.ewma_vol, self.asset_map).fillna(0)))

    def economic_sleeve(self):
        def build():
            themes = econ.macro_signals(self.r, self.macro_dir).rolling(econ.SMOOTH_MONTHS, min_periods=1).mean()
            classes = self.asset_class.copy()
            classes[classes.index.isin(econ.RATE_FUTURES_IN_FX)] = "FI"
            universe = econ.macro_universe(self.r.columns)
            parts = []
            for theme in econ.SIGNS.index:
                d = econ.theme_direction(themes[theme], theme, self.r.columns, classes)
                d.loc[:, ~d.columns.isin(universe)] = 0.0
                parts.append(self.scale_to_target(econ.risk_weights(d, self.sleeve_vol)))
            return self.scale_to_target(sum(parts) / len(parts))
        return self._cached("econ", build)

    def factor_sleeve(self):
        def build():
            score_all = build_signals(self.r)[0][FACTOR]
            direction = pd.DataFrame(np.nan, index=self.r.index, columns=self.r.columns)
            for _, members in self.asset_class.groupby(self.asset_class):
                cols = members.index
                score = score_all[cols].where(self.sleeve_vol[cols].gt(0))
                rank = score.rank(axis=1, pct=True)
                centered = 2 * rank.sub(rank.mean(axis=1), axis=0)
                direction[cols] = centered.where(score.count(axis=1).ge(4))
            return self.scale_to_target(econ.risk_weights(direction, self.sleeve_vol))
        return self._cached("factor", build)

    def histgb_sleeve(self):
        """rolling_sign_prediction.py forecasts (unchanged model and refit schedule), sized on EWMA vol.

        prepare() drops formation months without a next-month label; a blank next-month row is
        appended so the latest formation month still gets a forecast (it has no label, so it never
        enters training). Without it the most recent position would be missing in live use.
        """
        def build():
            from rolling_sign_prediction import rolling_predictions
            from sign_return_prediction import prepare
            nxt = (self.r.index[-1].to_period("M") + 1).to_timestamp("M")
            padded = pd.concat([self.r, pd.DataFrame(np.nan, index=[nxt], columns=self.r.columns)])
            padded.index.name = self.r.index.name
            data, x, y, _, _ = prepare(padded)
            prob = rolling_predictions(data, x, y, HISTGB_WINDOW)[0]
            prob = prob.unstack("instrument").reindex(index=self.r.index, columns=self.r.columns)
            return self.scale_to_target(econ.risk_weights(2 * prob - 1, self.sleeve_vol))
        return self._cached("histgb", build)

    def turning_flags(self):
        def build():
            fast = np.sign(self.r.rolling(2, min_periods=2).sum())
            disagreement = disagreement_from_signals(self.signal, fast)
            features = economic_confirmation_features(self.r, self.asset_map, self.signal, self.macro_dir)
            return disagreement, four_of_five_opposition(features)
        return self._cached("turning", build)

    # ---------------------------------------------------------------- pipeline
    def targeted(self, config):
        rb = "risk_budget" in config
        sleeves = tuple(s for s in SLEEVES if s in config)
        def build():
            core = self.core(rb)
            if not sleeves:
                return core
            builders = {"economic_trend": self.economic_sleeve, "factor_overlay": self.factor_sleeve,
                        "histgb_overlay": self.histgb_sleeve}
            # A sleeve with no positions at a date (e.g. HistGB before 1997) gives its share back to
            # the core, and dates with no active sleeve keep the core unchanged (no re-targeting),
            # so an inactive component is an exact no-op.
            parts = {s: builders[s]() for s in sleeves}
            share = {s: parts[s].abs().sum(axis=1).gt(0) * SLEEVE_WEIGHT[s] for s in sleeves}
            core_share = 1 - sum(share.values())
            mix = core.mul(core_share, axis=0) + sum(parts[s].mul(share[s], axis=0) for s in sleeves)
            any_active = core_share.lt(1)
            out = self.retarget(mix)
            out.loc[~any_active] = core.loc[~any_active]
            return out
        return self._cached(("targeted", rb, sleeves), build)

    def formed(self, config):
        config = frozenset(config)
        w = self.targeted(config)
        if "turning_point" in config:
            disagreement, opposition = self.turning_flags()
            w = macro_confirmed_binary_weights(w, disagreement, opposition, TURNING_ALPHA)
        if "half_short" in config:
            w = short_budget(w, HALF_SHORT)
        if "net_cap" in config:
            w = net_cap_weights(w)
        if "smooth_leverage" in config:
            w = smooth_exposure(w)[0]
        if "smooth_leverage_imbalance" in config:
            w = smooth_exposure(w)[1]
        return cap_only_weights(w.fillna(0))[0]

    def executed(self, config):
        formed = self.formed(config)
        if "band_25" in frozenset(config):
            return rebalance_path(formed, self.r, BAND, GROSS_CAP)
        return formed.shift(1).fillna(0.0)

    def evaluate(self, executed):
        gross = (executed * self.r.fillna(0)).sum(axis=1)
        cost, _ = cost_breakdown(executed, self.ewma_vol, self.adv, self.asset_class, DEFAULT_PARAMETERS, self.r)
        traded = trade_weights(executed, self.r, "drift").sum(axis=1)
        return pd.DataFrame({"gross": gross, "net": gross - cost.total, "cost": cost.total,
                             "turnover": traded, "gross_exposure": executed.abs().sum(axis=1)})

    def run(self, config):
        config = frozenset(config)
        return self._cached(("run", config), lambda: self.evaluate(self.executed(config)))


def stats(series, start, end=None):
    s = series.loc[start:end] if end else series.loc[start:]
    net, gross = s.net, s.gross
    years = len(net) / 12
    wealth = (1 + net).cumprod()
    vol = net.std() * np.sqrt(12)
    return {
        "start": f"{s.index.min():%Y-%m}", "end": f"{s.index.max():%Y-%m}", "months": len(net),
        "net_cagr": wealth.iloc[-1] ** (1 / years) - 1,
        "annual_gross_return": gross.mean() * 12, "annual_net_return": net.mean() * 12,
        "annual_volatility": vol, "net_sharpe": net.mean() * 12 / vol,
        "gross_sharpe": gross.mean() / gross.std() * np.sqrt(12),
        "max_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min(),
        "annual_turnover": s.turnover.mean() * 12, "annual_cost_drag": s.cost.mean() * 12,
        "average_gross_exposure": s.gross_exposure.mean(),
    }


def label(config):
    return "enhanced" if not config else "enhanced + " + " + ".join(c for c in COMPONENTS if c in config)


def compatible(config, candidate):
    return not any(candidate in group and config & group for group in EXCLUSIVE)


def stepwise(pipe, pool=tuple(COMPONENTS), start=IS_START, end=IS_END, verbose=True):
    """Forward stepwise on net Sharpe over [start, end]. Only months <= end are ever scored."""
    def sharpe(config):
        return stats(pipe.run(config), start, end)["net_sharpe"]

    current, current_sharpe = frozenset(), sharpe(frozenset())
    rows, step = [{"round": 0, "candidate": "(start: enhanced)", "is_net_sharpe": current_sharpe,
                   "delta_vs_current": 0.0, "best_in_round": True, "accepted": True, "combination": "enhanced"}], 1
    while True:
        trials = {c: sharpe(current | {c}) for c in pool if c not in current and compatible(current, c)}
        if not trials:
            break
        best = max(trials, key=trials.get)
        accept = trials[best] - current_sharpe >= THRESHOLD
        for c, value in sorted(trials.items(), key=lambda kv: -kv[1]):
            rows.append({"round": step, "candidate": c, "is_net_sharpe": value,
                         "delta_vs_current": value - current_sharpe, "best_in_round": c == best,
                         "accepted": accept and c == best, "combination": label(current | {c})})
        if verbose:
            print(f"round {step}: best {best} {trials[best]:.3f} (current {current_sharpe:.3f}) -> "
                  f"{'add' if accept else 'stop'}")
        if not accept:
            break
        current, current_sharpe, step = current | {best}, trials[best], step + 1
    return current, pd.DataFrame(rows)


def return_year(index):
    """Calendar year of the return month earned by each formation date."""
    return pd.Series((index.to_period("M") + 1).year, index=index)


def mixed_rebalance(formed, returns, band_flag, gross_cap=GROSS_CAP):
    """cost_aware_rebalance.rebalance_path with the band switched on/off per formation month."""
    targets = formed.fillna(0).shift(1).fillna(0)
    flags = band_flag.reindex(formed.index).fillna(False).astype(bool).shift(1, fill_value=False).to_numpy()
    r = returns.reindex_like(targets).fillna(0).to_numpy()
    goal_all, held = targets.to_numpy(), np.zeros(targets.shape)
    previous = np.zeros(targets.shape[1])
    for t in range(len(goal_all)):
        drifted = previous * (1 + r[t - 1]) / (1 + previous @ r[t - 1]) if t > 0 else previous
        goal = goal_all[t]
        w = np.clip(drifted, goal - BAND[1] * np.abs(goal), goal + BAND[1] * np.abs(goal)) if flags[t] else goal.copy()
        gross = np.abs(w).sum()
        if gross > gross_cap:
            w *= gross_cap / gross
        held[t] = w
        previous = w
    return pd.DataFrame(held, index=targets.index, columns=targets.columns)


def walk_forward(pipe, pool, first_year=WF_FIRST_YEAR):
    """Each Dec-31 close: stepwise on net Sharpe over Jan 1976 .. that date (expanding window), then
    trade the chosen combination for the next 12 formation months. Months before first_year trade
    `enhanced`. Relies on truncation invariance (tested): scores use only months <= the decision date."""
    years = return_year(pipe.r.index)
    last_year = int(years.max())
    choice = {y: frozenset() for y in range(int(years.min()), first_year)}
    decisions = []
    for year in range(first_year, last_year + 1):
        decision_date = f"{year - 1}-12-31"
        selected, _ = stepwise(pipe, pool, IS_START, decision_date, verbose=False)
        choice[year] = selected
        decisions.append({"return_year": year, "decision_date": decision_date,
                          "selected": " + ".join(c for c in COMPONENTS if c in selected) or "(enhanced only)",
                          "window_net_sharpe": stats(pipe.run(selected), IS_START, decision_date)["net_sharpe"]})
    formed = pd.DataFrame(0.0, index=pipe.r.index, columns=pipe.r.columns)
    band = pd.Series(False, index=pipe.r.index)
    for year, config in choice.items():
        mask = years.eq(year).to_numpy()
        formed.loc[mask] = pipe.formed(config).loc[mask].to_numpy()
        band.loc[mask] = "band_25" in config
    executed = mixed_rebalance(formed, pipe.r, band)
    return formed, executed, pd.DataFrame(decisions)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns, asset_map = read_full_sample_returns(), read_asset_map()

    # ---- phase 1: selection on 1969-2014 data only
    is_pipe = Pipeline(returns.loc[:IS_END], asset_map)
    selected, table = stepwise(is_pipe)
    table.to_csv(OUT / "stepwise_selection_in_sample.csv", index=False)
    (OUT / "selected_components.json").write_text(json.dumps({
        "selected": [c for c in COMPONENTS if c in selected], "threshold": THRESHOLD,
        "criterion": "IS (1976-01..2014-12) net Sharpe, Lecture 8 costs at $1bn, 5-day impact",
        "selection_data_end": IS_END}, indent=2), encoding="utf-8")
    is_check = {c: stats(is_pipe.run(c), IS_START, IS_END) for c in (frozenset(), frozenset(selected))}

    # ---- phase 2: one out-of-sample evaluation (after selection is frozen)
    pipe = Pipeline(returns, asset_map)
    configs = {"enhanced": frozenset(), **{c: frozenset({c}) for c in COMPONENTS}, "final": frozenset(selected)}
    runs = {"baseline": pipe.evaluate(pipe.course_baseline().shift(1).fillna(0.0))}
    runs.update({name: pipe.run(cfg) for name, cfg in configs.items()})
    for cfg, expected in is_check.items():  # IS numbers must not move when post-2014 data are added
        got = stats(pipe.run(cfg), IS_START, IS_END)
        assert np.isclose(got["net_sharpe"], expected["net_sharpe"], atol=1e-10), "IS changed with OOS data"

    # ---- phase 3: walk-forward selection (expanding window, annual reselection)
    probe = pipe.formed(frozenset())
    for flag, reference in ((True, rebalance_path(probe, returns, BAND, GROSS_CAP)), (False, probe.shift(1).fillna(0.0))):
        np.testing.assert_allclose(mixed_rebalance(probe, returns, pd.Series(flag, index=probe.index)).to_numpy(),
                                   reference.to_numpy(), atol=1e-12)
    clean_2015, _ = stepwise(is_pipe, CLEAN_POOL, verbose=False)  # computed on data truncated at 2014
    decisions = {}
    for name, pool in (("walk_forward_clean", CLEAN_POOL), ("walk_forward_all", tuple(COMPONENTS))):
        _, executed, decisions[name] = walk_forward(pipe, pool)
        runs[name] = pipe.evaluate(executed)
        executed.loc[IS_START:].to_csv(OUT / f"executed_weights_{name}.csv")
    d2015 = decisions["walk_forward_clean"].set_index("return_year").loc[2015, "selected"]
    assert d2015 == (" + ".join(c for c in COMPONENTS if c in clean_2015) or "(enhanced only)"), \
        "walk-forward 2015 decision differs from selection on truncated data"
    pd.concat(decisions, names=["run"]).reset_index(level=0).to_csv(OUT / "walk_forward_decisions.csv", index=False)

    tainted = set(POST_2015_DESIGN) | {"walk_forward_all"} | ({"final"} if selected & POST_2015_DESIGN else set())
    rows = []
    for name, series in runs.items():
        for period, (start, end) in PERIODS.items():
            rows.append({"strategy": name, "description": describe(name, configs), "period": period,
                         "clean_oos": name not in tainted, **stats(series, start, end)})
    results = pd.DataFrame(rows)
    results.to_csv(OUT / "is_vs_oos_performance.csv", index=False)
    pd.DataFrame({n: s.net for n, s in runs.items()}).loc[IS_START:].to_csv(OUT / "monthly_net_returns.csv")
    plot(runs, selected)
    write_report(table, results, selected, decisions, tainted)
    view = results.pivot(index="strategy", columns="period", values="net_sharpe").loc[list(runs)]
    print(view[list(PERIODS)].round(3).to_string())
    for name, d in decisions.items():
        print(f"\n{name}\n" + d[["return_year", "selected"]].to_string(index=False))


def describe(name, configs):
    if name == "baseline":
        return "Course baseline (40%/expanding vol, 1/N, no target)"
    if name == "enhanced":
        return "EWMA vol + EWMA-covariance 10% target (start point)"
    if name == "final":
        return label(configs["final"])
    if name == "walk_forward_clean":
        return "Walk-forward selection, clean pool (expanding window, annual)"
    if name == "walk_forward_all":
        return "Walk-forward selection, all candidates incl. post-2015-designed rules"
    return "enhanced + " + COMPONENTS[name]


def plot(runs, selected):
    fig, ax = plt.subplots(figsize=(12, 6.5))
    main_lines = ("baseline", "enhanced", "final", "walk_forward_clean", "walk_forward_all")
    for name, series in runs.items():
        if name in main_lines:
            continue
        ax.plot((1 + series.net.loc[IS_START:]).cumprod(), lw=0.8, alpha=0.35, color="grey")
    styles = {"baseline": ("#7f7f7f", "--"), "enhanced": ("#1f77b4", "-"), "final": ("#d62728", "-"),
              "walk_forward_clean": ("#2ca02c", "-"), "walk_forward_all": ("#2ca02c", ":")}
    for name, (color, ls) in styles.items():
        lab = f"final: {label(selected)}" if name == "final" else name
        ax.plot((1 + runs[name].net.loc[IS_START:]).cumprod(), color=color, ls=ls, lw=1.8, label=lab)
    ax.plot([], [], color="grey", alpha=0.5, label="enhanced + one component")
    ax.axvline(pd.Timestamp("1990-01-01"), color="#2ca02c", lw=0.8, ls="--")
    ax.axvspan(pd.Timestamp(OOS_START), runs["final"].index.max(), color="grey", alpha=0.15, label="out-of-sample")
    ax.set_yscale("log")
    ax.set_title("Wealth net of Lecture 8 costs at $1bn (log); shaded = Jan 2015 - May 2025 out-of-sample")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "combined_wealth_is_vs_oos.png", dpi=160)
    plt.close(fig)


def write_report(table, results, selected, decisions, tainted):
    step_lines = ["| Round | Candidate | IS net Sharpe | Change vs current | Added |", "|---:|---|---:|---:|:---:|"]
    for r in table.itertuples():
        step_lines.append(f"| {r.round} | {r.candidate} | {r.is_net_sharpe:.3f} | {r.delta_vs_current:+.3f} | "
                          f"{'yes' if r.accepted and r.round else ''} |")
    cols = [("net_cagr", "Net CAGR", "{:.2%}"), ("annual_gross_return", "Gross ret", "{:.2%}"),
            ("annual_net_return", "Net ret", "{:.2%}"), ("annual_volatility", "Vol", "{:.2%}"),
            ("net_sharpe", "Sharpe", "{:.2f}"), ("max_drawdown", "Max DD", "{:.1%}"),
            ("annual_turnover", "Turnover", "{:.1f}"), ("annual_cost_drag", "Cost drag", "{:.2%}")]
    perf = ["| Strategy | " + " | ".join(f"IS {c[1]} | OOS {c[1]}" for c in cols) + " |",
            "|---|" + "---:|" * (2 * len(cols))]
    get = lambda name, period: results[(results.strategy == name) & (results.period == period)].iloc[0]
    for name in results.strategy.unique():
        if name.startswith("walk_forward"):
            continue
        a, b = get(name, "IS 1976-2014"), get(name, "OOS 2015-2025")
        tag = name + (" †" if name in tainted else "")
        perf.append(f"| {tag} | " + " | ".join(f"{f.format(a[k])} | {f.format(b[k])}" for k, _, f in cols) + " |")
    wf_rows = ["| Strategy | " + " | ".join(f"1990-2014 {c[1]} | OOS {c[1]}" for c in cols) + " |",
               "|---|" + "---:|" * (2 * len(cols))]
    for name in ("baseline", "enhanced", "final", "walk_forward_clean", "walk_forward_all"):
        a, b = get(name, "WF 1990-2014"), get(name, "OOS 2015-2025")
        tag = name + (" †" if name in tainted else "")
        wf_rows.append(f"| {tag} | " + " | ".join(f"{f.format(a[k])} | {f.format(b[k])}" for k, _, f in cols) + " |")
    merged = decisions["walk_forward_clean"][["return_year", "selected"]].merge(
        decisions["walk_forward_all"][["return_year", "selected"]], on="return_year", suffixes=("_clean", "_all"))
    choice_rows = ["| Return year | Clean pool selects | All-candidates pool selects † |", "|---:|---|---|"]
    choice_rows += [f"| {r.return_year} | {r.selected_clean} | {r.selected_all} |" for r in merged.itertuples()]
    final_tainted = sorted(POST_2015_DESIGN & set(selected))
    report = f"""# Combined strategy: in-sample selection, out-of-sample evaluation

**Final combination:** `{label(selected)}`.

## Protocol

- In-sample (IS) = Jan 1976 - Dec 2014; out-of-sample (OOS) = Jan 2015 - May 2025
  (`MonthlyReturns_FullSample.xlsx`).
- Forward stepwise from `enhanced`: each round adds the candidate with the highest IS net Sharpe if it
  improves the current IS net Sharpe by at least {THRESHOLD}. Net = Lecture 8 cost model
  (`transaction_cost_model.py`) at $1bn, 5-day impact, drift-adjusted turnover.
- The selection ran on returns truncated at Dec 2014, so no 2015+ value was available to it. The OOS run
  was done once afterwards; the script asserts the IS numbers are identical with and without 2015+ data.
- All component parameters are those fixed in their original scripts on pre-2015 data; nothing was tuned
  here. Each rule is re-implemented on the monthly data and the enhanced construction, not on the
  `economic_trend.py` shared baseline (12-month vol with a 1% floor).
- Pipeline order (fixed in advance): core -> sleeves blended at 20% each and re-targeted to 10% with the
  EWMA covariance (4x gross, 2x scale caps) -> turning point -> half-short -> net cap -> smoothing ->
  4x gross cap -> execution (band_25 or monthly full rebalance).
- Rebalance frequency was not a candidate: weekly/daily trading needs daily closes after 2014, which are
  not available here, so it cannot be tested out of sample.

## Stepwise selection (in-sample only)

{chr(10).join(step_lines)}

Sharpe standard errors are about 0.19 over 39 IS years, so a 0.05 step is not statistically significant
on its own; the threshold only guards against adding near-zero improvements.

## In-sample vs out-of-sample (net of Lecture 8 costs at $1bn unless labelled gross)

Rows other than `baseline`, `enhanced` and `final` are `enhanced` plus that one component.
Turnover is annual drift-adjusted traded notional (x NAV).

{chr(10).join(perf)}

† Designed after the 2015-2025 data had been examined (half-short rule, exposure smoothing): their OOS
columns are **not a clean out-of-sample test**.{" The final combination contains " + ", ".join(final_tainted) + ", so its OOS result is not clean either." if final_tainted else " None of these entered the final combination."}

## Walk-forward selection

The one-shot selection above fixes the combination once, using all of 1976-2014. As a test of the
selection *procedure*, the same stepwise rule (+{THRESHOLD} net Sharpe threshold) is rerun at every Dec-31
close on an expanding window from Jan 1976 to that date, and the chosen combination is traded for the next
12 formation months. Switching combinations is traded and charged through the cost model; the no-trade
band applies only in months whose combination includes `band_25`. The window type (expanding), first
traded year ({WF_FIRST_YEAR}) and candidate pools were fixed before any walk-forward result was computed.

- **Clean pool:** {", ".join(CLEAN_POOL)} (excludes the rules designed after viewing 2015+ data).
- **All-candidates pool †:** also half_short and the smoothing rules; its 2015+ results are not clean.
- 1990-2014 decisions are causal, but the component designs themselves were developed on data covering
  that period, so it is a pseudo-out-of-sample check; 2015-2025 is the out-of-sample period.
- Blending rule: a sleeve with no positions at a date returns its share to the core, and dates with no
  active sleeve keep the core unchanged. This was corrected after a first walk-forward run showed the
  inactive (pre-1997) HistGB sleeve being "selected" only because its unused 30% share rescaled the
  portfolio. It is a correctness fix (an inactive component must be a no-op), not a tuned parameter, but
  it was made after seeing that run.
- Scores at each decision date use only months up to that date; this relies on truncation invariance,
  verified by `test_lookahead.py`, and the 2015 decision is asserted equal to a selection run on data
  truncated at Dec 2014.

{chr(10).join(wf_rows)}

{chr(10).join(choice_rows)}

![Wealth, IS vs OOS](combined_wealth_is_vs_oos.png)

## Caveats

- **Execution timing.** Main results fill at the signal close while impact costs assume 5-day execution;
  `alpha_decay_execution.py` shows this overstates IS net Sharpe by about 0.07-0.09.
- **Research look-ahead.** The repository had already analysed 2015-2025 for other strategies, so the OOS
  period is strategy-specific OOS, not a pristine holdout. The 58-market universe was chosen with hindsight.
- **Macro data.** FRED current vintages (INDPRO, CPIAUCSL, GS2, BAA10Y) include later revisions that were
  not known in real time. Publication lags: INDPRO and CPI usable one month after the reference month;
  GS2 and BAA10Y monthly averages of daily data, known at month-end.
- **Turning point.** Flags use only trailing 2- and 12-month return sums and the macro vote; no
  smoothing, filtering or ex-post peak/trough dating.
- **HistGB sleeve.** `rolling_sign_prediction.py` model and schedule unchanged (15-year rolling window,
  refit before each return year, labels strictly before the first formation date, forecasts from 1997;
  window and 30% weight chosen on 2000-2004 validation). It is inactive before 1997, so it cannot add
  in-sample Sharpe in 1976-1996. Feature eligibility uses `economic_trend.instrument_vol` as in the
  original; sizing uses EWMA vol like the other sleeves. The most recent formation month is kept for
  forecasting (the original `prepare` drops it because it has no label yet).
- **Costs after 2014.** Daily volume ends Dec 2014, so OOS liquidity uses the asset-class ADV constants.
- **Look-ahead test.** `python -m unittest test_lookahead.py` truncates returns and macro files at 1990-06,
  2014-12 and 2020-03 and checks that the final and all-components pipelines give identical weights and
  costs up to each cut.
"""
    (OUT / "combined_strategy_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
