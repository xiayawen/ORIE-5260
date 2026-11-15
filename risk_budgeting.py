"""Shared tools for R1 (Euler risk decomposition) and R2 (hierarchical risk budgeting).

Reference: Zivot, "Portfolio Risk Budgeting" (reading/Riskbudgetingslides_UWash.pdf).
For portfolio volatility sigma(w) = sqrt(w' S w), which is homogeneous of degree one,
Euler's theorem gives
    MCR_i = (S w)_i / sigma,  CR_i = w_i * MCR_i,  PCR_i = CR_i / sigma,  sum_i PCR_i = 1.

Risk budgeting (Spinu 2013 convex form): for signed positions w = s * x with known
signs s and x > 0, minimise 0.5 x' C x - b' log(x) with C = diag(s) S diag(s).
The first-order condition x_i (C x)_i = b_i makes every PCR equal its budget b_i
(budgets sum to one). Asset-class budgets 1/K split equally across the n_c active
instruments of each class give b_i = 1 / (K * n_c): every class carries the same
share of total ex-ante risk, correlations included.

Every input to a month-t weight uses returns through month t only.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from covariance_risk_validation import covariance, HALFLIFE

ROOT = Path(__file__).resolve().parent
FULL_SAMPLE_FILE = ROOT / "MonthlyReturns_FullSample.xlsx"
IS_START, IS_END = "1976-01-01", "2014-12-31"
OOS_START = "2015-01-01"


def read_full_sample_returns(path: Path = FULL_SAMPLE_FILE) -> pd.DataFrame:
    """Monthly returns Feb 1969 - May 2025. Same 58 columns as MonthlyReturns.csv."""
    returns = pd.read_excel(path, index_col=0)
    returns.index = pd.to_datetime(returns.index, errors="coerce")
    returns = returns.loc[returns.index.notna()].sort_index()
    returns.index.name = "Date"
    returns.columns = [str(c).strip() for c in returns.columns]
    returns = returns.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if returns.index.has_duplicates:
        raise ValueError("Duplicate dates in full-sample returns")
    return returns


def covariance_matrix(history: pd.DataFrame, model: str = "ewma") -> np.ndarray:
    """Annualised covariance from history through the formation date (inclusive).

    'ewma' uses the 6-month half-life of covariance_risk_validation.py; 'expanding'
    uses all available history.
    """
    if model == "ewma":
        return covariance(history, HALFLIFE)[0]
    if model == "expanding":
        return covariance(history)[0]
    raise ValueError(f"Unknown covariance model {model}")


def euler_decomposition(w: np.ndarray, cov: np.ndarray) -> dict:
    """MCR, CR, PCR for portfolio volatility (Zivot slides, Euler's theorem)."""
    w = np.asarray(w, dtype=float)
    sigma = float(np.sqrt(max(w @ cov @ w, 0.0)))
    if sigma == 0:
        nan = np.full(len(w), np.nan)
        return {"sigma": 0.0, "mcr": nan, "cr": nan, "pcr": nan}
    mcr = cov @ w / sigma
    cr = w * mcr
    return {"sigma": sigma, "mcr": mcr, "cr": cr, "pcr": cr / sigma}


def solve_risk_budget(cov_signed: np.ndarray, budgets: np.ndarray,
                      tol: float = 1e-11, max_iter: int = 200) -> tuple[np.ndarray, int]:
    """Newton's method on 0.5 x'Cx - b'log x (strictly convex for x > 0).

    Steps are halved only to stay inside the log barrier (x > 0). Returns x scaled
    so that x'Cx = 1, and the iteration count.
    """
    b = np.asarray(budgets, dtype=float)
    x = b / np.sqrt(np.clip(np.diag(cov_signed), 1e-16, None))
    x /= np.sqrt(x @ cov_signed @ x)
    for iteration in range(1, max_iter + 1):
        gradient = cov_signed @ x - b / x
        if np.max(np.abs(gradient * x)) < tol:
            break
        step = np.linalg.solve(cov_signed + np.diag(b / x ** 2), gradient)
        t = 1.0
        while np.any(x - t * step <= 0):
            t *= 0.5
        x = x - t * step
    else:
        raise RuntimeError("Risk-budget solver did not converge")
    return x / np.sqrt(x @ cov_signed @ x), iteration


def class_budgets(classes: pd.Series) -> np.ndarray:
    """1/K per active asset class, split equally inside the class: b_i = 1 / (K n_c)."""
    counts = classes.map(classes.value_counts())
    return (1.0 / (classes.nunique() * counts)).to_numpy(dtype=float)


def risk_budget_weights(returns: pd.DataFrame, signal: pd.DataFrame, eligibility: pd.DataFrame,
                        asset_class: pd.Series, cov_model: str = "ewma",
                        target: float = 0.10, gross_cap: float = 4.0):
    """Formation-date signed risk-budget weights scaled to a predicted `target` volatility.

    Active set at t: eligible (36 months of history, as in the baseline) with a
    nonzero 12-month signal at t. The covariance uses returns.loc[:t]. Gross
    exposure above `gross_cap` is cut proportionally (risk shares are unchanged).
    """
    weights = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    rows = []
    for date in returns.index:
        s_row = signal.loc[date]
        active = s_row.index[eligibility.loc[date].fillna(False).astype(bool)
                             & s_row.notna() & s_row.ne(0)]
        if len(active) == 0:
            continue
        signs = np.sign(s_row[active].to_numpy(dtype=float))
        cov = covariance_matrix(returns.loc[:date, active], cov_model)
        classes = asset_class.reindex(active)
        budgets = class_budgets(classes)
        x, iterations = solve_risk_budget(cov * np.outer(signs, signs), budgets)
        w = signs * x * target  # predicted volatility of signs * x is exactly 1
        gross = np.abs(w).sum()
        cap_binding = gross > gross_cap
        if cap_binding:
            w *= gross_cap / gross
        euler = euler_decomposition(w, cov)
        weights.loc[date, active] = w
        rows.append({
            "Date": date, "active_instruments": len(active), "active_classes": classes.nunique(),
            "solver_iterations": iterations,
            "max_budget_error": float(np.max(np.abs(euler["pcr"] - budgets))),
            "predicted_volatility": euler["sigma"], "gross_exposure": np.abs(w).sum(),
            "gross_cap_binding": cap_binding,
        })
    return weights, pd.DataFrame(rows).set_index("Date")


def class_risk_shares(weights: pd.DataFrame, returns: pd.DataFrame, asset_class: pd.Series,
                      cov_model: str = "ewma", dates=None) -> pd.DataFrame:
    """Ex-ante PCR by asset class for formation-date weights (history through each date)."""
    out = {}
    for date in (weights.index if dates is None else dates):
        row = weights.loc[date].fillna(0)
        active = row.index[row.ne(0)]
        if len(active) == 0:
            continue
        cov = covariance_matrix(returns.loc[:date, active], cov_model)
        pcr = pd.Series(euler_decomposition(row[active].to_numpy(), cov)["pcr"], index=active)
        out[date] = pcr.groupby(asset_class.reindex(active)).sum()
    return pd.DataFrame(out).T.reindex(columns=sorted(asset_class.unique())).fillna(0.0)


def realized_class_risk_shares(instrument_returns: pd.DataFrame, asset_class: pd.Series) -> pd.Series:
    """Ex-post Euler decomposition with the realized covariance of class sleeves.

    PCR_c = cov(r_c, r_p) / var(r_p) (Zivot: beta of the sleeve on the portfolio);
    the shares sum to one by construction.
    """
    sleeves = instrument_returns.T.groupby(asset_class.reindex(instrument_returns.columns)).sum().T
    portfolio = sleeves.sum(axis=1)
    return sleeves.apply(lambda c: c.cov(portfolio)) / portfolio.var()


def effective_number(shares: pd.DataFrame) -> pd.Series:
    """1 / sum(PCR^2): number of equally sized risk sources."""
    return 1.0 / shares.pow(2).sum(axis=1)
