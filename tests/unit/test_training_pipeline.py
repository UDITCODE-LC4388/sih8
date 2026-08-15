"""
Unit tests for the Super-Resolution training loop, dataset collation, and checkpoint loading.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest
import torch

from src.sr_engine.train import RealOverlapDataset, run_training_stage
from src.sr_engine.inference import SREngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_real_dataset_loading():
    patches_dir = PROJECT_ROOT / "data" / "processed" / "patches"
    patch_dirs = sorted([p for p in patches_dir.iterdir() if p.is_dir()])
    assert len(patch_dirs) > 0, "Real patches must be available for testing"

    dataset = RealOverlapDataset(patch_dirs=patch_dirs, crop_size=32, augment=True)
    assert len(dataset) == len(patch_dirs) * 4

    sample = dataset[0]
    assert "lr_ortho" in sample
    assert "lr_dem" in sample
    assert sample["lr_ortho"].shape == (1, 32, 32)
    assert sample["lr_dem"].shape == (1, 32, 32)
    assert "sun_azimuth_deg" in sample
    assert "sun_elevation_deg" in sample


def test_training_smoke_stages():
    # Run 1 epoch of Stage A
    res_a = run_training_stage(stage="A", num_epochs=1, batch_size=2, allow_data_gap=True)
    assert res_a == 0

    # Run 1 epoch of Stage B
    res_b = run_training_stage(stage="B", num_epochs=1, batch_size=2, allow_data_gap=True)
    assert res_b == 0

    # Verify SREngine loads checkpoints
    engine = SREngine(load_checkpoints=True)
    dummy_ortho = np.ones((16, 16), dtype=np.float32) * 0.5
    dummy_dem = np.ones((16, 16), dtype=np.float32) * 100.0

    sr_ortho, sr_dem, uncert = engine.super_resolve(
        dummy_ortho, dummy_dem, sun_azimuth_deg=238.2, sun_elevation_deg=39.1, enable_shading_refinement=False
    )
    assert sr_ortho.shape == (80, 80)
    assert sr_dem.shape == (160, 160)
    assert uncert.shape == (160, 160)
