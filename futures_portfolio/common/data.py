"""Shared data loading and trading calendar for the final submission."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from futures_portfolio.paths import ROOT
DATA = ROOT / "data"


def monthly_returns():
    frame = pd.read_excel(DATA / "MonthlyReturns_FullSample.xlsx", index_col=0)
    frame.index = pd.to_datetime(frame.index)
    frame.columns = frame.columns.astype(str)
    return frame.sort_index().apply(pd.to_numeric, errors="coerce")


def asset_map():
    frame = pd.read_csv(DATA / "AssetMapCsv.csv")
    frame["ID"] = frame["ID"].astype(str).str.strip()
    return frame


def daily_returns(instruments):
    """Back-adjusted close-to-close returns; missing trading days stay missing."""
    columns = ["Date", "Open", "High", "Low", "Close", "Volume", "OpenInterest"]
    output = {}
    with ZipFile(DATA / "FuturesUnderlyingData_FullSample.zip") as archive:
        lookup = {Path(name).name.upper(): name for name in archive.namelist()
                  if name.upper().endswith(".CSV")}
        for instrument in instruments:
            name = lookup.get(f"{instrument}_RAD.CSV".upper())
            if name is None:
                name = lookup.get(f"{instrument}__RAD.CSV".upper())
            if name is None:
                raise FileNotFoundError(f"Missing raw daily series for {instrument}")
            frame = pd.read_csv(BytesIO(archive.read(name)), header=None,
                                names=columns, usecols=[0, 4], parse_dates=["Date"])
            frame = frame.drop_duplicates("Date", keep="last")
            close = pd.to_numeric(frame["Close"], errors="coerce")
            close.index = frame["Date"]
            close = close.where(close > 0).dropna().sort_index()
            output[instrument] = close.pct_change(fill_method=None).iloc[1:]
    return pd.DataFrame(output).sort_index().rename_axis("Date")


def rebalance_dates(index, anchor=pd.Timestamp("2014-12-31"), step=21):
    location = index.get_indexer([anchor], method="pad")[0]
    return index[location % step::step]


def period_returns(daily, dates):
    wealth = (1 + daily.fillna(0)).cumprod().loc[dates]
    result = wealth / wealth.shift(1) - 1
    traded = daily.notna().astype(int).cumsum().loc[dates].diff().gt(0)
    return result.where(traded)
