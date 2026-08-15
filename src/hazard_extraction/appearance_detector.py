"""
Appearance-Based Crater & Boulder Detector (Module 3 Component)

Detects craters and boulders from photometric shadow/highlight pairs in the SR orthoimage.
Performs shadow-length photogrammetry to estimate sub-meter boulder heights down to
ISRO's operational 32 cm threshold:
    h = L * tan(theta_sun_elevation)
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
from scipy import ndimage
from skimage import morphology

from src.common.constants import BOULDER_HEIGHT_SHADOW_THRESHOLD_M


def detect_appearance_hazards(
    sr_ortho: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    cell_size_meters: float = 1.0,
    boulder_min_height_m: float = BOULDER_HEIGHT_SHADOW_THRESHOLD_M,
) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, float]]]:
    """
    Detects small boulders and crater rims from photometric shadows and highlights.
    
    Args:
        sr_ortho: 2D float array of the SR orthoimage [0, 1].
        sun_azimuth_deg: Sun azimuth angle in degrees.
        sun_elevation_deg: Sun elevation angle in degrees above horizon.
        cell_size_meters: Spatial resolution in meters per pixel.
        boulder_min_height_m: Operational minimum boulder height threshold (e.g. 0.32m).
        
    Returns:
        Tuple of:
          - appearance_crater_mask (2D binary array)
          - appearance_boulder_mask (2D binary array)
          - detected_boulders list with estimated shadow heights
    """
    # 1. Segment strong shadow regions (low pixel values) and highlights (high pixel values)
    # Use Otsu or percentile thresholds
    shadow_thresh = np.percentile(sr_ortho, 15)
    highlight_thresh = np.percentile(sr_ortho, 85)

    shadow_mask = sr_ortho < shadow_thresh
    highlight_mask = sr_ortho > highlight_thresh

    # Remove speckle noise
    shadow_clean = morphology.remove_small_objects(shadow_mask, max_size=2)
    highlight_clean = morphology.remove_small_objects(highlight_mask, max_size=2)

    # 2. Shadow-length photogrammetry
    # Sun direction vector in pixel space
    tan_el = np.tan(np.radians(max(sun_elevation_deg, 1.0)))

    labeled_shadows, num_shadows = ndimage.label(shadow_clean)
    boulder_mask = np.zeros_like(sr_ortho, dtype=np.uint8)
    crater_mask = np.zeros_like(sr_ortho, dtype=np.uint8)
    boulder_catalogue: List[Dict[str, float]] = []

    if num_shadows > 0:
        shadow_objs = ndimage.find_objects(labeled_shadows)
        for idx, sl in enumerate(shadow_objs, start=1):
            if sl is not None:
                patch = labeled_shadows[sl] == idx
                # Measure shadow length in pixels along shadow major axis
                shadow_len_px = max(patch.shape[0], patch.shape[1])
                shadow_len_m = shadow_len_px * cell_size_meters
                estimated_height_m = shadow_len_m * tan_el

                # Check if highlight exists directly adjacent opposite to shadow (classic boulder signature)
                cy = (sl[0].start + sl[0].stop) // 2
                cx = (sl[1].start + sl[1].stop) // 2

                if estimated_height_m >= boulder_min_height_m:
                    boulder_mask[sl] = np.maximum(boulder_mask[sl], patch.astype(np.uint8))
                    boulder_catalogue.append({
                        "type": "photometric_boulder",
                        "x": float(cx),
                        "y": float(cy),
                        "shadow_length_m": float(shadow_len_m),
                        "estimated_height_m": float(estimated_height_m),
                    })
                else:
                    crater_mask[sl] = np.maximum(crater_mask[sl], patch.astype(np.uint8))

    return crater_mask, boulder_mask, boulder_catalogue
