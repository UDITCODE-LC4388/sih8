"""
Geometric Crater & Boulder Feature Detector (Module 3 Component)

Scans the 1 m SR DEM for depressions (craters exceeding ~1.0 m depth)
and prominences (boulders exceeding ~1.0 m height).
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
from scipy import ndimage
from skimage import morphology

from src.common.constants import (
    CRATER_DEPTH_HAZARD_THRESHOLD_M,
    BOULDER_HEIGHT_DEM_THRESHOLD_M,
)


def detect_geometric_hazards(
    sr_dem: np.ndarray,
    crater_depth_threshold: float = CRATER_DEPTH_HAZARD_THRESHOLD_M,
    boulder_height_threshold: float = BOULDER_HEIGHT_DEM_THRESHOLD_M,
    filter_radius_cells: int = 5,
) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, float]]]:
    """
    Identifies geometric terrain hazards from elevation relief.
    
    Args:
        sr_dem: 2D float array of 1m SR DEM.
        crater_depth_threshold: Minimum crater depth (m) to classify as hazard (e.g. 1.0m).
        boulder_height_threshold: Minimum boulder prominence (m) to classify as hazard (e.g. 1.0m).
        filter_radius_cells: Radius of structuring element for local relief baseline.
        
    Returns:
        Tuple of:
          - crater_hazard_mask (binary 2D array)
          - boulder_hazard_mask (binary 2D array)
          - list of detected feature dictionaries (type, center_x, center_y, magnitude)
    """
    selem = morphology.disk(filter_radius_cells)

    # White top-hat extracts local positive prominences (boulders/ridges)
    boulder_prominence = morphology.white_tophat(sr_dem, selem)
    # Black top-hat extracts local negative depressions (craters)
    crater_depression = morphology.black_tophat(sr_dem, selem)

    boulder_mask = (boulder_prominence >= boulder_height_threshold).astype(np.uint8)
    crater_mask = (crater_depression >= crater_depth_threshold).astype(np.uint8)

    detected_features: List[Dict[str, float]] = []

    # Extract crater centroid coordinates
    crater_labels, num_craters = ndimage.label(crater_mask)
    if num_craters > 0:
        crater_objs = ndimage.find_objects(crater_labels)
        for idx, sl in enumerate(crater_objs, start=1):
            if sl is not None:
                mask_patch = crater_labels[sl] == idx
                depth_max = float(np.max(crater_depression[sl][mask_patch]))
                cy = float(sl[0].start + sl[0].stop) / 2.0
                cx = float(sl[1].start + sl[1].stop) / 2.0
                detected_features.append({
                    "type": "crater_depression",
                    "x": cx,
                    "y": cy,
                    "depth_m": depth_max,
                })

    # Extract boulder centroid coordinates
    boulder_labels, num_boulders = ndimage.label(boulder_mask)
    if num_boulders > 0:
        boulder_objs = ndimage.find_objects(boulder_labels)
        for idx, sl in enumerate(boulder_objs, start=1):
            if sl is not None:
                mask_patch = boulder_labels[sl] == idx
                height_max = float(np.max(boulder_prominence[sl][mask_patch]))
                cy = float(sl[0].start + sl[0].stop) / 2.0
                cx = float(sl[1].start + sl[1].stop) / 2.0
                detected_features.append({
                    "type": "boulder_prominence",
                    "x": cx,
                    "y": cy,
                    "height_m": height_max,
                })

    return crater_mask, boulder_mask, detected_features
