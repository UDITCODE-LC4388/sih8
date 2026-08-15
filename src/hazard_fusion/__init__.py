"""
Module 4: Hazard Map Fusion.
"""

from src.hazard_fusion.fuzzy_fusion import (
    fuse_hazard_layers,
    compute_fuzzy_slope_severity,
    compute_fuzzy_feature_severity,
)
from src.hazard_fusion.pipeline import execute_hazard_pipeline

__all__ = [
    "fuse_hazard_layers",
    "compute_fuzzy_slope_severity",
    "compute_fuzzy_feature_severity",
    "execute_hazard_pipeline",
]
