"""
Shading-Guided Photoclinometric Fusion (Module 2 Component)

Refines the 1m SR DEM's fine-scale relief using the SR orthoimage's shading gradients
under the scene's real Sun illumination geometry (sun elevation and azimuth angles).
"""

from __future__ import annotations

import numpy as np
import torch
from scipy import ndimage
from src.common.geo_utils import compute_lambertian_shading


def refine_dem_with_shading(
    sr_dem: np.ndarray,
    sr_ortho: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    cell_size_meters: float = 1.0,
    refinement_iterations: int = 15,
    step_size: float = 0.05,
    albedo: float = 0.12,
) -> np.ndarray:
    """
    Refines high-frequency elevation details of the SR DEM using photoclinometry (Shape-from-Shading).
    
    Args:
        sr_dem: 2D float array of the initial super-resolved DEM (1 m grid).
        sr_ortho: 2D float array of the 1 m super-resolved orthoimage [0, 1].
        sun_azimuth_deg: Sun azimuth in degrees clockwise from North.
        sun_elevation_deg: Sun elevation in degrees above horizon.
        cell_size_meters: Grid spacing in meters.
        refinement_iterations: Number of gradient descent steps.
        step_size: Gradient step size.
        albedo: Average lunar surface albedo.
        
    Returns:
        Refined 2D float array of the super-resolved DEM.
    """
    refined_dem = sr_dem.copy().astype(np.float64)

    # Illumination unit vector
    az_rad = np.radians(sun_azimuth_deg)
    el_rad = np.radians(sun_elevation_deg)
    sx = np.sin(az_rad) * np.cos(el_rad)
    sy = np.cos(az_rad) * np.cos(el_rad)
    sz = np.sin(el_rad)

    # Horn kernels
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64) / (8.0 * cell_size_meters)
    ky = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float64) / (8.0 * cell_size_meters)

    # Target observed intensity normalized to reflectance
    target_intensity = np.clip(sr_ortho.astype(np.float64), 0.0, 1.0)
    if target_intensity.shape != refined_dem.shape:
        zoom_factors = (refined_dem.shape[0] / target_intensity.shape[0], refined_dem.shape[1] / target_intensity.shape[1])
        target_intensity = ndimage.zoom(target_intensity, zoom_factors, order=1)

    for _ in range(refinement_iterations):
        p = ndimage.convolve(refined_dem, kx, mode="reflect")
        q = ndimage.convolve(refined_dem, ky, mode="reflect")

        norm = np.sqrt(p**2 + q**2 + 1.0)
        nx = -p / norm
        ny = -q / norm
        nz = 1.0 / norm

        cos_i = np.clip(nx * sx + ny * sy + nz * sz, 0.0, 1.0)
        synth_intensity = albedo * cos_i

        # Photoclinometry residual
        residual = target_intensity - synth_intensity

        # Delta update based on illumination direction
        delta_p = residual * sx
        delta_q = residual * sy

        # Propagate gradient corrections back to elevation relief
        delta_z = ndimage.convolve(delta_p, -kx, mode="reflect") + ndimage.convolve(delta_q, -ky, mode="reflect")
        refined_dem += step_size * delta_z

    return refined_dem.astype(np.float32)
