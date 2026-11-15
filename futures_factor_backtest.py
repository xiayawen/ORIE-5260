"""Price-based futures factors; run with python3 futures_factor_backtest.py.

Formation uses information through t and earns t+1 returns. Cross-sectional
factors are demeaned and gross-normalized within each asset class. These are
research portfolios, not externally supplied equity regression factors.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_backtest_adj import read_returns, read_asset_map, expanding_volatility

OUT = Path(__file__).resolve().parent / "outputs" / "futures_factor_output"


def build_signals(returns):
    vol = expanding_volatility(returns).replace(0, np.nan)
    downside = returns.clip(upper=0).pow(2).rolling(12, min_periods=12).mean().pow(0.5)
    signals = {
        "TSMOM": np.sign(returns.rolling(12, min_periods=12).sum()),
        "Reversal_1m": -returns / vol,
        "LowVol_12m": -returns.rolling(12, min_periods=12).std(),
        "LowDownside_12m": -downside,
        "XSMOM_12_1": returns.shift(1).rolling(11, min_periods=11).sum() / vol,
    }
    signals.update(additional_signals(returns))
    return {name: value.replace([np.inf, -np.inf], np.nan)
            for name, value in signals.items()}, vol


def additional_signals(r):
    """Twenty prespecified candidates; signs are hypotheses, not fitted choices.

    All price-path statistics use log wealth from returns, not futures spot prices.
    Windows require complete observations; no forward/backward filling.
    """
    sd = r.rolling(12, min_periods=12).std().replace(0, np.nan)
    log = np.log1p(r.where(r > -1))
    roll = r.rolling(12, min_periods=12)
    # Windows operate locally so missing observations cannot bridge price paths.
    def path_stat(x, kind):
        path = np.r_[0.0, np.cumsum(x)]
        if kind == "high":
            return path[-1] - path.max()
        if kind == "drawdown":
            return np.min(path - np.maximum.accumulate(path))
        return path[-1] / np.abs(x).sum() if np.abs(x).sum() else np.nan

    def persistence(x):
        if np.std(x[:-1]) == 0 or np.std(x[1:]) == 0:
            return np.nan
        return np.corrcoef(x[:-1], x[1:])[0, 1]

    seasonal = sum(r.shift(lag) for lag in (11, 23, 35, 47, 59)) / 5
    positive = r.gt(0).astype(float).where(r.notna())
    return {
        "Reversal_3m": -r.rolling(3, min_periods=3).sum() / sd,
        "LongReversal_36_12": -r.shift(12).rolling(24, min_periods=24).sum() / sd,
        "NegativeSkew_12m": -roll.skew(),
        "LowKurtosis_12m": -roll.kurt(),
        "LowMaxReturn_12m": -roll.max(),
        "MildWorstReturn_12m": roll.min(),
        "LowTailLoss_12m": roll.quantile(0.1),
        "LowUpsideRisk_12m": -r.clip(lower=0).pow(2).rolling(12, min_periods=12).mean().pow(0.5),
        "RiskAsymmetry_12m": (r.clip(lower=0).pow(2).rolling(12, min_periods=12).mean()
                                   - r.clip(upper=0).pow(2).rolling(12, min_periods=12).mean()) / sd.pow(2),
        "VolCompression_3_12": -r.rolling(3, min_periods=3).std() / sd,
        "LowVolOfVol_12m": -sd.rolling(12, min_periods=12).std() / sd.rolling(12, min_periods=12).mean(),
        "ReturnPersistence_12m": roll.apply(persistence, raw=True),
        "Seasonality_5y": seasonal,
        "TrendEfficiency_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "efficiency"), raw=True),
        "TrendAcceleration_3m": (r.rolling(3, min_periods=3).sum()
                                      - r.shift(3).rolling(3, min_periods=3).sum()) / sd,
        "MeanToVol_12m": roll.mean() / sd,
        "NearWealthHigh_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "high"), raw=True),
        "ShallowDrawdown_12m": log.rolling(12, min_periods=12).apply(lambda x: path_stat(x, "drawdown"), raw=True),
        "PositiveMonthShare_12m": positive.rolling(12, min_periods=12).mean(),
        "MedianReturn_12m": roll.median() / sd,
    }


def factor_weights(score, vol, classes, directional=False):
    eligible = score.where(vol.gt(0))
    weights = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for _, members in classes.groupby(classes):
        cols = members.index
        values = eligible[cols]
        if directional:
            raw = values / vol[cols]
        else:
            # Tied values receive the same rank; fewer than four markets abstain.
            ranks = values.rank(axis=1, pct=True)
            raw = ranks.sub(ranks.mean(axis=1), axis=0)
            raw = raw.where(values.count(axis=1).ge(4), np.nan)
        weights[cols] = raw.div(raw.abs().sum(axis=1).replace(0, np.nan), axis=0)
    # Equal gross allocation across active classes, total gross exposure = 1.
    active = pd.DataFrame({c: weights[m.index].abs().sum(axis=1).gt(0)
                           for c, m in classes.groupby(classes)}).sum(axis=1)
    return weights.div(active.replace(0, np.nan), axis=0).fillna(0)


def evaluate(returns):
    wealth = (1 + returns).cumprod()
    std = returns.std() * np.sqrt(12)
    return {"months": len(returns), "annual_mean": returns.mean() * 12,
            "annual_vol": std, "sharpe_zero_rf": returns.mean() * 12 / std if std else np.nan,
            "cagr": wealth.iloc[-1] ** (12 / len(returns)) - 1,
            "max_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    returns = read_returns()
    classes = read_asset_map().set_index("ID")["AssetClass"].reindex(returns.columns)
    if classes.isna().any():
        raise ValueError("Missing asset-class mapping")
    signals, vol = build_signals(returns)
    gross, net, turnover, available = {}, {}, {}, {}
    for name, score in signals.items():
        formation = factor_weights(score, vol, classes, directional=name == "TSMOM")
        executed = formation.shift(1).fillna(0)
        missing = executed.ne(0) & returns.isna()
        pnl = (executed * returns).sum(axis=1).mask(missing.any(axis=1))
        # Trade from drifted previous holdings; reject missing held returns.
        prior = executed.shift(1).fillna(0)
        previous_returns = returns.shift(1)
        previous_pnl = (prior * previous_returns).sum(axis=1)
        drifted = prior * (1 + previous_returns.fillna(0))
        drifted = drifted.div(1 + previous_pnl, axis=0)
        traded = (executed - drifted).abs().sum(axis=1)
        valid = executed.abs().sum(axis=1).gt(0) & ~missing.any(axis=1)
        valid &= ~(prior.ne(0) & previous_returns.isna()).any(axis=1)
        gross[name] = pnl.where(valid)
        net[name] = (pnl - traded * 0.001).where(valid)
        turnover[name] = traded
        available[name] = pd.DataFrame({"active": valid, "missing_held_returns": missing.sum(axis=1)})
        formation.to_csv(OUT / f"{name}_formation_weights.csv")
        available[name].to_csv(OUT / f"{name}_coverage.csv")
    gross = pd.DataFrame(gross).loc["1976-01-01":]
    net = pd.DataFrame(net).reindex(gross.index)
    common = gross.notna().all(axis=1) & net.notna().all(axis=1)
    gross.to_csv(OUT / "gross_monthly_returns.csv")
    net.to_csv(OUT / "net_monthly_returns_10bps.csv")
    pd.DataFrame(turnover).to_csv(OUT / "turnover.csv")
    gross.loc[common].corr().to_csv(OUT / "factor_correlations.csv")
    rows = []
    for name in gross:
        for label, data in (("gross", gross), ("net_10bps", net)):
            for period, mask in (("full_common", common),
                                 ("pre_2000", common & (gross.index < "2000-01-01")),
                                 ("2000_onward", common & (gross.index >= "2000-01-01"))):
                sample = data.loc[mask, name]
                if len(sample):
                    rows.append(dict(factor=name, costs=label, period=period,
                                     start=str(sample.index[0].date()), end=str(sample.index[-1].date()),
                                     **evaluate(sample)))
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "performance_summary.csv", index=False)
    comparison = summary.loc[summary.costs.eq("net_10bps")
                             & summary.period.eq("full_common")
                             & summary.factor.isin(additional_signals(returns))].copy()
    comparison["corr_TSMOM"] = comparison.factor.map(gross.loc[common].corr()["TSMOM"])
    comparison[["factor", "sharpe_zero_rf", "corr_TSMOM"]].to_csv(
        OUT / "additional_20_comparison.csv", index=False)
    print(summary.loc[summary.period.eq("full_common")].to_string(index=False))


if __name__ == "__main__":
    main()
