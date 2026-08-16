"""
Dataset Evaluation Script for Lunar SR Engine & Anti-Hallucination Guardrails

Runs full evaluation across all real Chandrayaan-2 TMC and LRO NAC patches in data/processed/patches:
- Measures downscale cycle invariance MAE (scale consistency)
- Measures elevation range preservation and inflation ratio
- Measures photoclinometric shading SSIM and radiometric correlation
- Verifies anti-hallucination certificate across all tiles
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.logging import logger
from src.sr_engine.inference import SREngine
from src.sr_engine.validation import generate_sr_fidelity_report

PATCHES_DIR = PROJECT_ROOT / "data" / "processed" / "patches"


def evaluate_dataset_patches() -> int:
    patch_dirs = sorted([p for p in PATCHES_DIR.iterdir() if p.is_dir() and (p / "lr_ortho.npy").exists()])
    if not patch_dirs:
        logger.error(f"No patches found in {PATCHES_DIR}")
        return 1

    logger.info(f"Initiating SR Model & Anti-Hallucination Evaluation on {len(patch_dirs)} real dataset patches...")
    sr_engine = SREngine()

    results: List[Dict[str, Any]] = []

    print("\n" + "=" * 110)
    print(f"{'PATCH / TILE ID':<42} | {'ORIG RANGE':<11} | {'SR RANGE':<10} | {'RANGE RATIO':<11} | {'SCALE MAE':<10} | {'SHADING SSIM':<12} | {'STATUS'}")
    print("=" * 110)

    for pdir in patch_dirs:
        lr_ortho = np.load(pdir / "lr_ortho.npy")
        lr_dem = np.load(pdir / "lr_dem.npy")
        with open(pdir / "metadata.json", "r", encoding="utf-8") as f:
            meta = json.load(f)

        sun_az = float(meta.get("sun_azimuth_deg", 238.21))
        sun_el = float(meta.get("sun_elevation_deg", 39.14))
        tile_id = meta.get("tile_id", pdir.name)

        sr_ortho, sr_dem, uncert = sr_engine.super_resolve(
            lr_ortho=lr_ortho,
            lr_dem=lr_dem,
            sun_azimuth_deg=sun_az,
            sun_elevation_deg=sun_el,
            enable_shading_refinement=True,
        )

        fidelity = generate_sr_fidelity_report(
            sr_dem_1m=sr_dem,
            original_dem_lr=lr_dem,
            optical_image_1m=sr_ortho,
            sun_azimuth_deg=sun_az,
            sun_elevation_deg=sun_el,
        )

        scale_inv = fidelity["scale_invariance"]
        shd_fid = fidelity["photoclinometric_fidelity"]
        orig_range = scale_inv["original_elevation_range_meters"]
        sr_range = scale_inv["sr_elevation_range_meters"]
        ratio = scale_inv["range_inflation_ratio"]
        scale_mae = scale_inv["downscale_mae_meters"]
        ssim = shd_fid["shading_ssim"]

        status = "✅ VERIFIED" if (scale_inv["passed"] and ssim >= 0.5) else "⚠️ REVIEW"

        print(
            f"{tile_id:<42} | {orig_range:>9.2f}m | {sr_range:>8.2f}m | {ratio:>10.2f}x | {scale_mae:>8.4f}m | {ssim:>12.4f} | {status}"
        )

        results.append({
            "tile_id": tile_id,
            "orig_range_m": orig_range,
            "sr_range_m": sr_range,
            "range_ratio": ratio,
            "scale_mae_m": scale_mae,
            "shading_ssim": ssim,
            "photometric_correlation": shd_fid["photometric_correlation"],
            "verified": fidelity["hallucination_safeguards_verified"],
        })

    print("=" * 110 + "\n")

    avg_mae = np.mean([r["scale_mae_m"] for r in results])
    avg_ratio = np.mean([r["range_ratio"] for r in results])
    avg_ssim = np.mean([r["shading_ssim"] for r in results])

    logger.info(f"Dataset Evaluation Complete: Mean Downscale MAE: {avg_mae:.4f} m | Mean Range Ratio: {avg_ratio:.3f}x | Mean Shading SSIM: {avg_ssim:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(evaluate_dataset_patches())
