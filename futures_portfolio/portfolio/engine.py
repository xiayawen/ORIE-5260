"""Portfolio volatility scaling for causally dated target weights."""
import numpy as np


def risk_normalize(weights, covariance, target=.11):
    """Scale each formation portfolio to its annualized ex-ante volatility target."""
    variance = np.einsum("ti,tij,tj->t", weights, covariance, weights)
    scale = np.divide(
        target, np.sqrt(np.maximum(variance, 0)),
        out=np.zeros(len(weights)), where=variance > 1e-16,
    )
    return weights * scale[:, None]
