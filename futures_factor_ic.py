"""Monthly cross-sectional IC: formation score at t vs raw return at t+1."""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from futures_factor_backtest import OUT, build_signals, read_returns, read_asset_map


def monthly_ic(score, target, minimum=4):
    valid = score.notna() & target.notna()
    x, y = score.where(valid), target.where(valid)
    count = valid.sum(axis=1)
    return pd.DataFrame({
        "IC": x.corrwith(y, axis=1).where(count.ge(minimum)),
        "RankIC": x.rank(axis=1).corrwith(y.rank(axis=1), axis=1).where(count.ge(minimum)),
        "n_instruments": count,
    })


def summarize(series):
    data = series.dropna()
    if len(data) < 2:
        return {"months": len(data)}
    # Keep calendar spacing for HAC: missing months contribute zero score to
    # the mean estimating equation, rather than closing gaps in calendar time.
    residual = (series - data.mean()).fillna(0)
    fit = sm.OLS(residual.to_numpy(), np.ones((len(series), 1))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3, "use_correction": True})
    se = fit.bse[0] * len(series) / len(data)
    std = data.std()
    return {"months": len(data), "mean": data.mean(), "std": std,
            "ICIR_monthly": data.mean() / std if std else np.nan,
            "ICIR_annualized": data.mean() / std * np.sqrt(12) if std else np.nan,
            "positive_fraction": data.gt(0).mean(),
            "hac3_t": data.mean() / se if se else np.nan}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = read_returns()
    signals, vol = build_signals(r)
    classes = read_asset_map().set_index("ID")["AssetClass"].reindex(r.columns)
    target = r.shift(-1)  # Last row has no observed forward return.
    details = []
    for factor, score in signals.items():
        score = score.where(vol.gt(0))
        groups = {"all_markets": r.columns}
        groups.update({str(c): members.index for c, members in classes.groupby(classes)})
        class_results = []
        for group, cols in groups.items():
            result = monthly_ic(score[cols], target[cols])
            if group != "all_markets":
                class_results.append(result[["IC", "RankIC"]])
            result["factor"], result["scope"] = factor, group
            details.append(result.rename_axis("formation_date").reset_index())
        # Same class weighting philosophy as portfolio construction. Require a
        # valid correlation in at least two classes to avoid a one-class label.
        result = pd.DataFrame(index=r.index)
        for metric in ("IC", "RankIC"):
            panel = pd.concat([x[metric] for x in class_results], axis=1)
            result[metric] = panel.mean(axis=1).where(panel.notna().sum(axis=1).ge(2))
        result["factor"], result["scope"] = factor, "within_class_equal"
        details.append(result.rename_axis("formation_date").reset_index())
    monthly = pd.concat(details, ignore_index=True)
    # Match backtest realized-return start: formation in Dec 1975 earns Jan 1976.
    dates = pd.Series(r.index[1:], index=r.index[:-1])
    monthly["return_date"] = monthly.formation_date.map(dates)
    monthly = monthly.loc[monthly.return_date.ge(pd.Timestamp("1976-01-01"))
                          & monthly.return_date.notna()]
    monthly.to_csv(OUT / "ic_monthly.csv", index=False)
    rows = []
    for (factor, scope), data in monthly.groupby(["factor", "scope"], sort=False):
        for period, sample in (("full", data),
                               ("pre_2000", data.loc[data.return_date.lt("2000-01-01")]),
                               ("2000_onward", data.loc[data.return_date.ge("2000-01-01")])):
            for metric in ("IC", "RankIC"):
                rows.append(dict(factor=factor, scope=scope, period=period,
                                 metric=metric, **summarize(sample[metric])))
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "ic_summary.csv", index=False)
    print(summary.loc[summary.scope.eq("within_class_equal") & summary.period.eq("full")
                      & summary.metric.eq("RankIC"),
                      ["factor", "months", "mean", "ICIR_annualized", "hac3_t"]]
          .sort_values("mean", ascending=False).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
