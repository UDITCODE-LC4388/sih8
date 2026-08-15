"""
Unit tests for super-resolution model architectures and tensor forward passes.
"""

import pytest
import torch
from src.sr_engine.models.image_sr import ImageSRGenerator
from src.sr_engine.models.dem_sr import DEMSRGenerator
from src.sr_engine.losses import SlopeConsistencyLoss


def test_image_sr_upsampling_factor():
    # Input: 5m TMC crop (e.g. 32x32)
    # Output: 1m SR orthoimage (5x upsampled -> 160x160)
    model = ImageSRGenerator(in_channels=1, out_channels=1, num_features=16, num_blocks=1)
    model.eval()

    dummy_input = torch.randn(1, 1, 32, 32)
    with torch.no_grad():
        out = model(dummy_input)

    assert out.shape == (1, 1, 160, 160)


def test_dem_sr_upsampling_factor():
    # Input: 10m TMC DEM crop (e.g. 16x16)
    # Output: 1m SR DEM (10x upsampled -> 160x160)
    model = DEMSRGenerator(in_channels=1, out_channels=1, num_features=16, num_groups=1)
    model.eval()

    dummy_input = torch.randn(1, 1, 16, 16)
    with torch.no_grad():
        out = model(dummy_input)

    assert out.shape == (1, 1, 160, 160)


def test_slope_consistency_loss_differentiable():
    loss_fn = SlopeConsistencyLoss(cell_size_meters=1.0)
    pred_dem = torch.randn(2, 1, 32, 32, requires_grad=True)
    target_dem = torch.randn(2, 1, 32, 32)

    loss = loss_fn(pred_dem, target_dem)
    assert torch.isfinite(loss)
    loss.backward()
    assert pred_dem.grad is not None
