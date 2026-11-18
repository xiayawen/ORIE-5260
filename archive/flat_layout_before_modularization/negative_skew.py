"""Within-asset-class rank of trailing 12-month negative skewness."""
import numpy as np
import pandas as pd
from risk_model import normalize_sleeve


def skew_sleeve(returns, classes, monthly_vol, covariance, eligible):
    score = -returns.rolling(12, min_periods=12).skew()
    direction = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    for _, members in classes.groupby(classes):
        values = score[members.index].where(monthly_vol[members.index].gt(0))
        ranks = values.rank(axis=1, pct=True)
        direction[members.index] = (2 * ranks.sub(ranks.mean(axis=1), axis=0)).where(values.count(axis=1).ge(4))
    raw = direction.div(monthly_vol).where(direction.ne(0))
    count = raw.notna().sum(axis=1).replace(0, np.nan)
    raw = raw.div(count, axis=0)
    return normalize_sleeve(raw, eligible, covariance)
