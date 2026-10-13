"""Load the standardized adjusted-baseline outputs produced by item 3."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
BASELINE_OUTPUT_DIR = ROOT / "outputs" / "baseline_performance_output"


def _read_csv(filename: str, *, index: bool = True, date_columns=None) -> pd.DataFrame:
    path = BASELINE_OUTPUT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python baseline_performance_analysis.py` first."
        )
    if index:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    return pd.read_csv(path, parse_dates=date_columns)


def load_baseline_outputs() -> dict[str, pd.DataFrame]:
    """Return item 3 outputs with dates parsed and execution alignment preserved."""
    return {
        "monthly_returns": _read_csv("baseline_monthly_returns.csv"),
        "instrument_returns": _read_csv("baseline_instrument_returns.csv"),
        "executed_weights": _read_csv("baseline_executed_weights.csv"),
        "volatility_estimates": _read_csv("baseline_volatility_estimates.csv"),
        "exposures": _read_csv("baseline_exposures.csv"),
        "turnover": _read_csv("baseline_turnover.csv"),
        "rolling_performance": _read_csv(
            "rolling_performance.csv", index=False, date_columns=["Date"]
        ),
        "drawdown_events": _read_csv(
            "drawdown_events.csv",
            index=False,
            date_columns=["peak_date", "trough_date", "recovery_date"],
        ),
        "performance_summary": _read_csv(
            "baseline_performance_summary.csv", index=False
        ),
    }


def formation_date_risk_inputs(
    outputs: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert execution-month item 3 files back to formation-date alignment.

    Item 3 stores the executed weight and its associated volatility estimate on the
    month in which the return is earned. Shifting both one row earlier recovers the
    weight and volatility estimate formed at month t for forecasts starting at t+1.
    """
    return (
        outputs["executed_weights"].shift(-1),
        outputs["volatility_estimates"].shift(-1),
    )
