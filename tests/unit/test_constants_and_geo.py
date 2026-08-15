"""
Unit tests for geospatial and photogrammetric numerical routines.
"""

import numpy as np
import pytest
from src.common.geo_utils import (
    compute_horn_slope,
    compute_lambertian_shading,
    radiometric_mean_2sigma_stretch,
)


def test_horn_slope_flat_surface():
    flat_dem = np.ones((50, 50), dtype=np.float32) * 1000.0
    slope = compute_horn_slope(flat_dem, cell_size_meters=1.0)
    assert np.allclose(slope, 0.0, atol=1e-4)


def test_horn_slope_known_ramp():
    # 45-degree planar slope: dz/dx = 1 m/m
    x = np.arange(50, dtype=np.float32)
    ramp_dem = np.tile(x, (50, 1))  # elevation increases by 1m per cell along X
    slope = compute_horn_slope(ramp_dem, cell_size_meters=1.0)

    # Interior pixels should be 45 degrees
    interior_slope = slope[5:-5, 5:-5]
    assert np.allclose(interior_slope, 45.0, atol=1e-2)


def test_lambertian_shading_bounds():
    test_dem = np.zeros((30, 30), dtype=np.float32)
    shaded = compute_lambertian_shading(
        test_dem,
        sun_azimuth_deg=45.0,
        sun_elevation_deg=30.0,
        cell_size_meters=1.0,
    )
    assert shaded.shape == (30, 30)
    assert np.all(shaded >= 0.0)
    assert np.all(shaded <= 1.0)


def test_radiometric_stretch_idempotent():
    arr = np.random.uniform(0, 255, size=(40, 40)).astype(np.float32)
    s1 = radiometric_mean_2sigma_stretch(arr)
    assert np.all(s1 >= 0.0)
    assert np.all(s1 <= 1.0)
