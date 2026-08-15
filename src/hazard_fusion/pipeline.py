"""
Module 4: Hazard Map Fusion Pipeline Entrypoint
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import numpy as np

from src.hazard_extraction.slope import extract_slope_hazard
from src.hazard_extraction.geometric_detector import detect_geometric_hazards
from src.hazard_extraction.appearance_detector import detect_appearance_hazards
from src.hazard_extraction.cross_check import cross_check_hazard_detections
from src.hazard_extraction.shadow_model import compute_raycast_shadows
from src.hazard_extraction.distribution import compute_hazard_density_map
from src.hazard_fusion.fuzzy_fusion import fuse_hazard_layers


def execute_hazard_pipeline(
    sr_dem: np.ndarray,
    sr_ortho: np.ndarray,
    uncertainty_map: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    cell_size_meters: float = 1.0,
) -> Dict[str, np.ndarray]:
    """
    Executes full hazard extraction and weighted-fuzzy fusion.
    """
    # Ensure spatial grid dimensions match DEM grid
    if sr_ortho.shape != sr_dem.shape:
        import cv2
        sr_ortho = cv2.resize(sr_ortho, (sr_dem.shape[1], sr_dem.shape[0]), interpolation=cv2.INTER_LINEAR)
    if uncertainty_map.shape != sr_dem.shape:
        import cv2
        uncertainty_map = cv2.resize(uncertainty_map, (sr_dem.shape[1], sr_dem.shape[0]), interpolation=cv2.INTER_LINEAR)

    # 1. Slope
    slope_deg, slope_hazard_mask = extract_slope_hazard(sr_dem, cell_size_meters=cell_size_meters)

    # 2. Geometric detections
    g_crater, g_boulder, _ = detect_geometric_hazards(sr_dem)

    # 3. Appearance detections
    a_crater, a_boulder, _ = detect_appearance_hazards(
        sr_ortho, sun_azimuth_deg=sun_azimuth_deg, sun_elevation_deg=sun_elevation_deg, cell_size_meters=cell_size_meters
    )

    # 4. Cross-check
    agreed, uncertain, conservative_features = cross_check_hazard_detections(
        g_crater, g_boulder, a_crater, a_boulder, uncertainty_map
    )

    # 5. Shadows
    shadow_mask = compute_raycast_shadows(
        sr_dem, sun_azimuth_deg=sun_azimuth_deg, sun_elevation_deg=sun_elevation_deg, cell_size_meters=cell_size_meters
    )

    # 6. Spatial density
    density_map = compute_hazard_density_map(conservative_features)

    # 7. Fuzzy Fusion
    graded_severity, binary_hazard = fuse_hazard_layers(
        slope_deg=slope_deg,
        conservative_feature_mask=conservative_features,
        density_map=density_map,
        shadow_mask=shadow_mask,
        uncertainty_map=uncertainty_map,
    )

    return {
        "slope_deg": slope_deg,
        "slope_hazard_mask": slope_hazard_mask,
        "conservative_features": conservative_features,
        "agreed_features": agreed,
        "uncertain_features": uncertain,
        "shadow_mask": shadow_mask,
        "density_map": density_map,
        "graded_severity": graded_severity,
        "binary_hazard": binary_hazard,
    }
