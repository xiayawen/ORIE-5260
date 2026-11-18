"""Volatility estimates, covariance and the common risk controls."""
import numpy as np
import pandas as pd

from futures_portfolio.portfolio.engine import risk_normalize


def monthly_ewma_vol(returns):
    vol = returns.ewm(halflife=6, min_periods=36, ignore_na=True).std()
    return vol.where(returns.notna().cumsum().ge(36)) * np.sqrt(12)


def monthly_sample_cov(history):
    """Original six-month EWMA covariance with pairwise overlap and PSD repair."""
    x = history.to_numpy(dtype=float)
    valid = np.isfinite(x).astype(float)
    x = np.nan_to_num(x, nan=0.0)
    decay = 2.0 ** (-np.arange(len(x)-1, -1, -1) / 6)
    mass = valid.T @ (valid * decay[:, None])
    squared = valid.T @ (valid * decay[:, None] ** 2)
    totals = x.T @ (valid * decay[:, None])
    cross = x.T @ (x * decay[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = (cross - totals * totals.T / mass) / (mass - squared / mass)
    sd = np.sqrt(np.diag(raw))
    corr = raw / np.outer(sd, sd)
    overlap = valid.T @ valid
    corr[(overlap < 36) | ~np.isfinite(corr)] = 0
    np.fill_diagonal(corr, 1)
    corr = (corr + corr.T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    repaired = (eigenvectors * np.maximum(eigenvalues, 0)) @ eigenvectors.T
    repaired /= np.outer(np.sqrt(np.diag(repaired)), np.sqrt(np.diag(repaired)))
    return repaired * np.outer(sd, sd) * 12


def monthly_covariance_cube(returns):
    cube = np.zeros((len(returns), returns.shape[1], returns.shape[1]))
    count = returns.notna().cumsum()
    variance = returns.expanding().var()
    for t in range(len(returns)):
        active = np.flatnonzero((count.iloc[t].ge(36) & variance.iloc[t].gt(0)).to_numpy())
        if len(active):
            cube[t][np.ix_(active, active)] = monthly_sample_cov(returns.iloc[:t+1, active])
    return cube


def daily_covariance_cube(daily, dates, eligible, window=252):
    cube = np.zeros((len(dates), daily.shape[1], daily.shape[1]))
    for t, date in enumerate(dates):
        active = np.flatnonzero(eligible.loc[date].to_numpy())
        if len(active):
            matrix = daily.loc[:date].iloc[-window:, active].cov(min_periods=100).fillna(0).to_numpy() * 252
            matrix = np.nan_to_num((matrix + matrix.T) / 2)
            values, vectors = np.linalg.eigh(matrix)
            cube[t][np.ix_(active, active)] = (vectors * np.maximum(values, 0)) @ vectors.T
    return cube


def normalize_sleeve(raw, eligible, cov):
    return risk_normalize(raw.fillna(0).to_numpy() * eligible, cov)
