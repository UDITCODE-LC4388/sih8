"""
Deterministic Ray-Casting Shadow and Illumination Model (Module 3 Component)

Casts rays across the 1m SR DEM according to planned descent Sun azimuth and elevation.
Flags illumination risk for polar landing sites where deep shadows impair optical TRN navigation.
"""

from __future__ import annotations

import numpy as np


def compute_raycast_shadows(
    sr_dem: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    cell_size_meters: float = 1.0,
    max_ray_steps: int = 100,
) -> np.ndarray:
    """
    Computes topographic ray-cast shadow mask on DEM using vectorized 2D slice shifts.
    
    Args:
        sr_dem: 2D float array of elevations in meters.
        sun_azimuth_deg: Sun azimuth angle in degrees clockwise from North.
        sun_elevation_deg: Sun elevation angle in degrees above horizon.
        cell_size_meters: Grid spacing in meters.
        max_ray_steps: Maximum pixel steps to trace towards the Sun.
        
    Returns:
        2D binary array (1 = in shadow, 0 = illuminated).
    """
    h, w = sr_dem.shape
    shadow_mask = np.zeros((h, w), dtype=bool)

    az_rad = np.radians(sun_azimuth_deg)
    el_rad = np.radians(max(sun_elevation_deg, 0.1))

    # Ray step direction towards the Sun
    dx = np.sin(az_rad)
    dy = -np.cos(az_rad)
    dz_step = cell_size_meters * np.tan(el_rad)

    for step in range(1, max_ray_steps):
        r_shift = int(round(step * dy))
        c_shift = int(round(step * dx))

        if abs(r_shift) >= h or abs(c_shift) >= w:
            break

        src_r_start = max(0, r_shift)
        src_r_end = min(h, h + r_shift)
        src_c_start = max(0, c_shift)
        src_c_end = min(w, w + c_shift)

        dst_r_start = max(0, -r_shift)
        dst_r_end = min(h, h - r_shift)
        dst_c_start = max(0, -c_shift)
        dst_c_end = min(w, w - c_shift)

        is_occluded = sr_dem[src_r_start:src_r_end, src_c_start:src_c_end] > (
            sr_dem[dst_r_start:dst_r_end, dst_c_start:dst_c_end] + step * dz_step
        )
        shadow_mask[dst_r_start:dst_r_end, dst_c_start:dst_c_end] |= is_occluded

    return shadow_mask.astype(np.uint8)
