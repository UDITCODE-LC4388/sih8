"""
Unit tests for SR anti-hallucination losses, elevation range anchoring, and validation suite.
"""

import numpy as np
import pytest
import torch
import torch.nn.functional as F

from src.sr_engine.losses import (
    ElevationRangeAnchorLoss,
    SlopeConsistencyLoss,
    ShadingConsistencyLoss,
)
from src.sr_engine.validation import (
    validate_downscale_cycle_invariance,
    validate_photoclinometric_rerendering,
    validate_against_lola_profile,
    generate_sr_fidelity_report,
)


def test_elevation_range_anchor_loss():
    anchor_loss = ElevationRangeAnchorLoss()

    # Exact match should yield 0 loss
    dem = torch.ones(2, 1, 32, 32) * 50.0
    loss_exact = anchor_loss(dem, dem)
    assert torch.isclose(loss_exact, torch.tensor(0.0), atol=1e-5)

    # Shifted mean should increase loss
    dem_shifted = dem + 10.0
    loss_shifted = anchor_loss(dem_shifted, dem)
    assert loss_shifted.item() > 5.0

    # Inflated range should increase loss
    dem_inflated = dem.clone()
    dem_inflated[0, 0, 0, 0] += 100.0
    loss_inflated = anchor_loss(dem_inflated, dem)
    assert loss_inflated.item() > 0.0


def test_slope_consistency_loss_repose_penalty():
    slope_loss = SlopeConsistencyLoss(cell_size_meters=1.0, max_slope_deg=35.0)

    # Gentle slope
    dem_flat = torch.zeros(1, 1, 16, 16)
    dem_gentle = torch.zeros(1, 1, 16, 16)
    dem_gentle[0, 0, :, :] = torch.linspace(0, 2, 16).repeat(16, 1)

    loss_gentle = slope_loss(dem_gentle, dem_flat)
    assert torch.isfinite(loss_gentle)

    # Extreme non-physical cliff (violates 35 deg angle of repose)
    dem_extreme = torch.zeros(1, 1, 16, 16)
    dem_extreme[0, 0, :, 8:] = 500.0  # 500m vertical jump over 1m cell size

    loss_extreme = slope_loss(dem_extreme, dem_flat)
    # The repose penalty will add a large quadratic penalty
    assert loss_extreme.item() > loss_gentle.item() * 10.0


def test_shading_consistency_grazing_angles():
    shading_loss = ShadingConsistencyLoss(cell_size_meters=1.0, min_elevation_deg=5.0)
    pred_dem = torch.randn(1, 1, 32, 32)
    sr_ortho = torch.rand(1, 1, 32, 32)

    # Test very low sun elevation (e.g. 1 deg near horizon)
    loss_grazing = shading_loss(pred_dem, sr_ortho, sun_azimuth_deg=180.0, sun_elevation_deg=1.0)
    assert torch.isfinite(loss_grazing)
    assert loss_grazing.item() >= 0.0


def test_downscale_cycle_validation():
    # 1. Test flat terrain
    lr_flat = np.ones((16, 16), dtype=np.float32) * 1200.0
    sr_flat = np.ones((160, 160), dtype=np.float32) * 1200.0
    report_flat = validate_downscale_cycle_invariance(sr_flat, lr_flat, scale_factor=10)
    assert report_flat["passed"] is True
    assert report_flat["downscale_mae_meters"] < 0.001

    # 2. Test sloped terrain with realistic gradient
    x_sr = np.linspace(100.0, 200.0, 160, dtype=np.float32)
    sr_dem = np.tile(x_sr, (160, 1))
    t_sr = torch.from_numpy(sr_dem).unsqueeze(0).unsqueeze(0)
    lr_dem = F.interpolate(t_sr, size=(16, 16), mode="area").squeeze().numpy()

    report = validate_downscale_cycle_invariance(sr_dem, lr_dem, scale_factor=10)
    assert report["passed"] is True
    assert report["downscale_mae_meters"] < 0.01
    assert 0.85 <= report["range_inflation_ratio"] <= 1.15

    # 3. Test artificially inflated DEM
    sr_dem_inflated = sr_dem.copy()
    sr_dem_inflated[0:10, 0:10] += 500.0
    report_inflated = validate_downscale_cycle_invariance(sr_dem_inflated, lr_dem, scale_factor=10)
    assert report_inflated["downscale_mae_meters"] > 0.05


def test_lola_profile_validation():
    sr_dem = np.zeros((100, 100), dtype=np.float32)
    sr_dem[:] = 50.0

    coords = np.array([[10, 10], [20, 20], [30, 30], [40, 40]], dtype=np.float32)
    altitudes = np.array([50.1, 49.9, 50.2, 49.8], dtype=np.float32)

    res = validate_against_lola_profile(sr_dem, coords, altitudes, max_tolerated_rmse_m=1.0)
    assert res["passed"] is True
    assert res["vertical_rmse_m"] < 0.5
    assert res["shot_count"] == 4


def test_comprehensive_sr_fidelity_report():
    sr_dem = np.ones((64, 64), dtype=np.float32) * 100.0
    lr_dem = np.ones((16, 16), dtype=np.float32) * 100.0
    sr_ortho = np.ones((64, 64), dtype=np.float32) * 0.5

    report = generate_sr_fidelity_report(
        sr_dem_1m=sr_dem,
        original_dem_lr=lr_dem,
        optical_image_1m=sr_ortho,
        sun_azimuth_deg=238.2,
        sun_elevation_deg=39.1,
    )
    assert "hallucination_safeguards_verified" in report
    assert "scale_invariance" in report
    assert "photoclinometric_fidelity" in report
