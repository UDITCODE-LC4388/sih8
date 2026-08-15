"""
Sliding-Window Safe Landing Patch Search (Module 5 Component)

Searches the fused hazard map for contiguous safe zones meeting ISRO's 24 m x 24 m
landing footprint requirement at 1 m spatial granularity.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
from scipy import ndimage

from src.common.constants import (
    LANDER_PATCH_GRID_CELLS,
    SLOPE_HAZARD_THRESHOLD_DEG,
)


def find_candidate_landing_patches(
    binary_hazard_map: np.ndarray,
    slope_deg_map: np.ndarray,
    graded_severity_map: np.ndarray,
    patch_size_cells: int = LANDER_PATCH_GRID_CELLS,
    stride_cells: int = 4,
    nominal_aim_point: Tuple[int, int] = (128, 128),
) -> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
    """
    Scans the terrain map for candidate 24m x 24m landing patches.
    
    Returns:
        Tuple of (accepted_candidates_list, rejected_candidates_list_with_discard_reasons).
    """
    h, w = binary_hazard_map.shape
    accepted_candidates: List[Dict[str, any]] = []
    rejected_candidates: List[Dict[str, any]] = []

    # Vectorized fast check using integral image / 2D uniform filter sum of hazards
    kernel = np.ones((patch_size_cells, patch_size_cells), dtype=np.float32)
    hazard_count_window = ndimage.convolve(binary_hazard_map.astype(np.float32), kernel, mode="constant", cval=1.0)
    mean_slope_window = ndimage.convolve(slope_deg_map.astype(np.float32), kernel, mode="constant", cval=90.0) / (patch_size_cells**2)
    mean_severity_window = ndimage.convolve(graded_severity_map.astype(np.float32), kernel, mode="constant", cval=1.0) / (patch_size_cells**2)

    half_p = patch_size_cells // 2

    for r in range(half_p, h - half_p, stride_cells):
        for c in range(half_p, w - half_p, stride_cells):
            haz_count = hazard_count_window[r, c]
            avg_slope = mean_slope_window[r, c]
            avg_severity = mean_severity_window[r, c]

            # Delta-v / distance cost from nominal aim point
            dist_from_aim_m = float(np.hypot(r - nominal_aim_point[0], c - nominal_aim_point[1]))

            candidate_info = {
                "center_r": r,
                "center_c": c,
                "patch_size_m": patch_size_cells,
                "hazard_pixel_count": int(haz_count),
                "mean_slope_deg": float(avg_slope),
                "mean_severity": float(avg_severity),
                "distance_from_aim_m": dist_from_aim_m,
            }

            # Safety evaluation
            if haz_count > 0:
                candidate_info["discard_reason"] = f"Hazard pixels detected inside 24m patch ({int(haz_count)} cells)"
                rejected_candidates.append(candidate_info)
            elif avg_slope > SLOPE_HAZARD_THRESHOLD_DEG:
                candidate_info["discard_reason"] = f"Mean patch slope ({avg_slope:.1f}°) exceeds threshold ({SLOPE_HAZARD_THRESHOLD_DEG}°)"
                rejected_candidates.append(candidate_info)
            else:
                accepted_candidates.append(candidate_info)

    return accepted_candidates, rejected_candidates
