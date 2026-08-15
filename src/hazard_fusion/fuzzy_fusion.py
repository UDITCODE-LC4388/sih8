"""
Weighted-Fuzzy Hazard Map Fusion (Module 4 Component)

Normalizes individual hazard layers (slope, crater/boulder, density, shadow, uncertainty)
into [0, 1] continuous fuzzy membership values and fuses them into:
1. A continuous graded severity map [0.0 = completely safe, 1.0 = lethal hazard]
2. A binary safe/hazard map following ISRO operational conventions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import numpy as np


def compute_fuzzy_slope_severity(slope_deg: np.ndarray, critical_slope: float = 10.0) -> np.ndarray:
    """Fuzzy membership curve for slope hazard."""
    # Sigmoidal transition around critical_slope
    return 1.0 / (1.0 + np.exp(-0.8 * (slope_deg - critical_slope)))


def compute_fuzzy_feature_severity(feature_mask: np.ndarray) -> np.ndarray:
    """Fuzzy severity for discrete hazard features."""
    return feature_mask.astype(np.float32)


def fuse_hazard_layers(
    slope_deg: np.ndarray,
    conservative_feature_mask: np.ndarray,
    density_map: np.ndarray,
    shadow_mask: np.ndarray,
    uncertainty_map: np.ndarray,
    weights: Optional[Dict[str, float]] = None,
    binary_cutoff_severity: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Combines hazard layers via weighted fuzzy aggregation.
    
    Args:
        slope_deg: 2D array of slope in degrees.
        conservative_feature_mask: 2D binary array of agreed + uncertain features.
        density_map: 2D float array [0, 1] of spatial hazard density.
        shadow_mask: 2D binary array of shadow regions.
        uncertainty_map: 2D float array of epistemic uncertainty.
        weights: Optional dictionary of layer weights.
        binary_cutoff_severity: Severity threshold above which a cell is marked hazardous (1).
        
    Returns:
        Tuple of (graded_severity_map [0, 1], binary_hazard_map [0=safe, 1=hazard]).
    """
    if weights is None:
        weights = {
            "slope": 0.35,
            "features": 0.30,
            "density": 0.15,
            "shadow": 0.10,
            "uncertainty": 0.10,
        }

    # Normalize weights
    total_w = sum(weights.values())
    w_slope = weights["slope"] / total_w
    w_feat = weights["features"] / total_w
    w_dens = weights["density"] / total_w
    w_shad = weights["shadow"] / total_w
    w_unc = weights["uncertainty"] / total_w

    s_slope = compute_fuzzy_slope_severity(slope_deg)
    s_feat = compute_fuzzy_feature_severity(conservative_feature_mask)
    s_dens = np.clip(density_map, 0.0, 1.0)
    s_shad = np.clip(shadow_mask.astype(np.float32), 0.0, 1.0)
    s_unc = np.clip(uncertainty_map, 0.0, 1.0)

    # Weighted fuzzy sum
    graded_severity = (
        w_slope * s_slope +
        w_feat * s_feat +
        w_dens * s_dens +
        w_shad * s_shad +
        w_unc * s_unc
    )

    graded_severity = np.clip(graded_severity, 0.0, 1.0).astype(np.float32)

    # ISRO Convention: binary hazard triggered by graded severity OR operational slope/feature thresholds
    is_hard_slope_hazard = slope_deg > 10.0
    is_hard_feature_hazard = conservative_feature_mask > 0
    binary_hazard = (
        (graded_severity >= binary_cutoff_severity) | is_hard_slope_hazard | is_hard_feature_hazard
    ).astype(np.uint8)

    return graded_severity, binary_hazard
