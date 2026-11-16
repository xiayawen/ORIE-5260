"""Data loading and adjusted-baseline construction for turning-point research."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from strategy_backtest_adj import build_baseline, read_asset_map

from turning_point_model import ROOT


FULL_SAMPLE_FILE = ROOT / "MonthlyReturns_FullSample.xlsx"
HISTORICAL_FILE = ROOT / "MonthlyReturns.csv"


def _read_return_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Monthly return input not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        raw = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported monthly return format: {path.suffix}")
    if raw.shape[1] < 2:
        raise ValueError(f"Monthly return input has no instrument columns: {path}")
    raw = raw.rename(columns={raw.columns[0]: "Date"})
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    returns = raw.dropna(subset=["Date"]).set_index("Date").sort_index()
    returns = returns.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if returns.index.has_duplicates:
        raise ValueError(f"Monthly return input contains duplicate dates: {path}")
    if returns.columns.duplicated().any():
        raise ValueError(f"Monthly return input contains duplicate instruments: {path}")
    return returns


def load_monthly_returns(path: str | Path | None = None) -> tuple[pd.DataFrame, Path]:
    """Load the requested return panel, preferring the local full sample."""
    selected = Path(path).expanduser().resolve() if path else (
        FULL_SAMPLE_FILE if FULL_SAMPLE_FILE.exists() else HISTORICAL_FILE
    )
    returns = _read_return_file(selected)
    asset_map = read_asset_map()
    # AssetMapCsv.csv also contains contracts outside the 58-instrument course
    # universe. MonthlyReturns.csv is the authoritative baseline column set.
    expected = set(_read_return_file(HISTORICAL_FILE).columns)
    missing = sorted(expected.difference(returns.columns))
    extra = sorted(set(returns.columns).difference(expected))
    if missing or extra:
        raise ValueError(
            f"Return columns do not match the 58-instrument baseline universe; missing={missing}, extra={extra}"
        )
    unmapped = sorted(set(returns.columns).difference(asset_map["ID"].astype(str)))
    if unmapped:
        raise ValueError(f"Return instruments are missing from AssetMapCsv.csv: {unmapped}")
    return returns, selected


def build_adjusted_baseline_inputs(
    path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, Path]:
    """Return data, asset map, adjusted baseline, full panel, and reconciliation."""
    from baseline_performance_analysis import build_turning_point_panel

    returns, asset_map, baseline, source = build_baseline_inputs(path)
    panel, reconciliation = build_turning_point_panel(returns, asset_map, baseline)
    if panel.empty:
        raise ValueError("No eligible turning-point observations were produced")
    error = reconciliation["difference"].abs().max()
    if not np.isfinite(error) or error > 1e-12:
        raise AssertionError(f"Turning-point panel does not reconcile to baseline; max error={error}")
    return returns, asset_map, baseline, panel, reconciliation, source


def build_baseline_inputs(
    path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, Path]:
    """Build the adjusted baseline without loading diagnostic-report modules."""
    returns, source = load_monthly_returns(path)
    asset_map = read_asset_map()
    baseline, _ = build_baseline(returns, asset_map)
    return returns, asset_map, baseline, source
