"""
GCS Dashboard Backend Data Formatter (Module 6 Component)

Structures hazard layers, 3D terrain meshes, and candidate landing zones
for ground control station (GCS) visualization dashboards (Cesium / Leaflet / React).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
import numpy as np


def generate_dashboard_payload(
    sr_ortho: np.ndarray,
    sr_dem: np.ndarray,
    binary_hazard: np.ndarray,
    graded_severity: np.ndarray,
    uncertainty_map: np.ndarray,
    candidates: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Constructs a JSON-serializable dashboard state dictionary.
    """
    return {
        "grid_dimensions": {
            "height": int(sr_dem.shape[0]),
            "width": int(sr_dem.shape[1]),
            "resolution_m": 1.0,
        },
        "elevation_stats": {
            "min_m": float(np.min(sr_dem)),
            "max_m": float(np.max(sr_dem)),
            "mean_m": float(np.mean(sr_dem)),
        },
        "hazard_summary": {
            "total_pixels": int(binary_hazard.size),
            "hazard_pixels": int(np.sum(binary_hazard)),
            "hazard_percentage": float(np.mean(binary_hazard) * 100.0),
            "mean_severity": float(np.mean(graded_severity)),
        },
        "candidate_landing_sites": candidates,
        "rejected_patches_count": len(rejected),
        "rejected_summary": rejected[:20],  # sample top 20 rejected with reasons
    }
