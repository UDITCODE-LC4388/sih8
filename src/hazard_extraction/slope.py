"""
Slope Hazard Layer (Module 3 Component)

Calculates terrain slope angles from the 1m SR DEM using Horn's 3x3 finite-difference
gradient operator, and applies the operational 10 degree hazard threshold (ISRO Chandrayaan-3 standard).
"""

from __future__ import annotations

import numpy as np
from src.common.constants import SLOPE_HAZARD_THRESHOLD_DEG
from src.common.geo_utils import compute_horn_slope


def extract_slope_hazard(
    sr_dem: np.ndarray,
    cell_size_meters: float = 1.0,
    slope_threshold_deg: float = SLOPE_HAZARD_THRESHOLD_DEG,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes slope angles and binary slope hazard mask.
    
    Args:
        sr_dem: 2D float array of the super-resolved DEM (1m grid).
        cell_size_meters: Grid resolution in meters.
        slope_threshold_deg: Maximum safe slope in degrees (default: 10.0°).
        
    Returns:
        tuple of (slope_degrees_map, binary_slope_hazard_mask [0=safe, 1=hazard]).
    """
    slope_deg = compute_horn_slope(sr_dem, cell_size_meters=cell_size_meters)
    slope_hazard_mask = (slope_deg > slope_threshold_deg).astype(np.uint8)
    return slope_deg, slope_hazard_mask
