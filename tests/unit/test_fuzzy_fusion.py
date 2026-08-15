"""
Unit tests for weighted-fuzzy hazard map fusion mathematics.
"""

import numpy as np
import pytest
from src.hazard_fusion.fuzzy_fusion import (
    compute_fuzzy_slope_severity,
    fuse_hazard_layers,
)


def test_fuzzy_slope_severity():
    # 0 deg slope should have low severity
    s_flat = compute_fuzzy_slope_severity(np.array([0.0]))
    assert s_flat[0] < 0.01

    # 10 deg slope (threshold) should be at midpoint (~0.5)
    s_thresh = compute_fuzzy_slope_severity(np.array([10.0]))
    assert np.isclose(s_thresh[0], 0.5, atol=0.01)

    # 25 deg slope should be near 1.0 (lethal)
    s_steep = compute_fuzzy_slope_severity(np.array([25.0]))
    assert s_steep[0] > 0.99


def test_fuse_hazard_layers_output_shapes_and_ranges():
    shape = (64, 64)
    slope = np.zeros(shape, dtype=np.float32)
    features = np.zeros(shape, dtype=np.uint8)
    density = np.zeros(shape, dtype=np.float32)
    shadow = np.zeros(shape, dtype=np.uint8)
    uncertainty = np.zeros(shape, dtype=np.float32)

    # Add a known steep slope in the center
    slope[20:30, 20:30] = 20.0  # lethal slope

    graded, binary = fuse_hazard_layers(
        slope_deg=slope,
        conservative_feature_mask=features,
        density_map=density,
        shadow_mask=shadow,
        uncertainty_map=uncertainty,
    )

    assert graded.shape == shape
    assert binary.shape == shape
    assert np.all(graded >= 0.0) and np.all(graded <= 1.0)
    # Steep region must be flagged as hazard in binary map
    assert np.all(binary[22:28, 22:28] == 1)
    # Flat region must remain safe (0)
    assert np.all(binary[0:10, 0:10] == 0)
