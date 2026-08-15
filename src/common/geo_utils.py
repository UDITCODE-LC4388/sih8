"""
Geospatial and photogrammetric numerical utilities.
Includes Horn's finite-difference slope algorithm, Lambertian shading synthesis,
and radiometric normalization.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def compute_horn_slope(dem: np.ndarray, cell_size_meters: float = 1.0) -> np.ndarray:
    """
    Computes slope in degrees using Horn's (1981) 3x3 finite difference operator.
    Standard algorithm in planetary DEM processing (USGS/ISIS/RichDEM).
    
    Args:
        dem: 2D numpy array of elevations in meters.
        cell_size_meters: Spatial resolution in meters per pixel.
        
    Returns:
        2D numpy array of slope angles in degrees [0, 90].
    """
    if dem.ndim != 2:
        raise ValueError(f"DEM must be a 2D array, got shape {dem.shape}")

    # Horn's kernel weights for dz/dx and dz/dy
    # [ -1  0  1 ]          [  1  2  1 ]
    # [ -2  0  2 ] / (8*dx) [  0  0  0 ] / (8*dy)
    # [ -1  0  1 ]          [ -1 -2 -1 ]
    kernel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64) / (8.0 * cell_size_meters)
    kernel_y = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float64) / (8.0 * cell_size_meters)

    # Use reflection boundary conditions
    dz_dx = ndimage.convolve(dem.astype(np.float64), kernel_x, mode="reflect")
    dz_dy = ndimage.convolve(dem.astype(np.float64), kernel_y, mode="reflect")

    # Slope = arctan(sqrt((dz/dx)^2 + (dz/dy)^2))
    gradient_mag = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_rad = np.arctan(gradient_mag)
    slope_deg = np.degrees(slope_rad)
    return slope_deg.astype(np.float32)


def compute_lambertian_shading(
    dem: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    cell_size_meters: float = 1.0,
    albedo: float = 0.12,
) -> np.ndarray:
    """
    Computes theoretical Lambertian surface shading given DEM relief and sun vector.
    Used in shading-guided fusion and photoclinometry consistency loss.
    
    Args:
        dem: 2D numpy array of elevations in meters.
        sun_azimuth_deg: Sun azimuth angle in degrees (clockwise from North).
        sun_elevation_deg: Sun elevation angle in degrees above lunar horizon.
        cell_size_meters: Grid resolution in meters.
        albedo: Nominal lunar surface albedo.
        
    Returns:
        2D numpy array of normalized reflected intensities [0, 1].
    """
    kernel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64) / (8.0 * cell_size_meters)
    kernel_y = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float64) / (8.0 * cell_size_meters)

    p = ndimage.convolve(dem.astype(np.float64), kernel_x, mode="reflect")  # dz/dx
    q = ndimage.convolve(dem.astype(np.float64), kernel_y, mode="reflect")  # dz/dy

    # Surface normal: N = (-p, -q, 1) / sqrt(p^2 + q^2 + 1)
    norm_denom = np.sqrt(p**2 + q**2 + 1.0)
    nx = -p / norm_denom
    ny = -q / norm_denom
    nz = 1.0 / norm_denom

    # Illumination vector: S = (sin(az)*cos(el), cos(az)*cos(el), sin(el))
    az_rad = np.radians(sun_azimuth_deg)
    el_rad = np.radians(sun_elevation_deg)
    sx = np.sin(az_rad) * np.cos(el_rad)
    sy = np.cos(az_rad) * np.cos(el_rad)
    sz = np.sin(el_rad)

    # Cosine of incidence angle: cos(i) = N . S
    cos_i = nx * sx + ny * sy + nz * sz
    cos_i = np.clip(cos_i, 0.0, 1.0)

    shaded = albedo * cos_i
    return shaded.astype(np.float32)


def radiometric_mean_2sigma_stretch(image: np.ndarray) -> np.ndarray:
    """
    Standard planetary radiometric normalization: Mean ± 2σ linear stretch to [0, 1].
    Idempotent on already scaled data.
    """
    valid_mask = np.isfinite(image)
    if not np.any(valid_mask):
        return np.zeros_like(image, dtype=np.float32)

    mean_val = np.mean(image[valid_mask])
    std_val = np.std(image[valid_mask])

    if std_val < 1e-8:
        return np.zeros_like(image, dtype=np.float32)

    min_val = mean_val - 2.0 * std_val
    max_val = mean_val + 2.0 * std_val

    stretched = np.clip((image - min_val) / (max_val - min_val), 0.0, 1.0)
    return stretched.astype(np.float32)
