"""Compatibility API for the former combined feature-filter/training module.

Implementations are split by responsibility; old function imports still work.
"""
from orie5260.factors.selection import feature_frames, select_inputs, panel
from orie5260.models.training import fit_model
