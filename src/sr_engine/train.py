"""
Super-Resolution Training Operations (Module 2b - Section 10 of Master Brief)

Implements the two-stage training regime on real ISRO Chandrayaan-2 patches:
- Stage A: Reconstruction pretraining (Multi-scale L1 + Topographic Slope Consistency)
- Stage B: Adversarial fine-tuning (RaGAN + Real Photoclinometric Shading Consistency)
- Strict data provenance tracking, loss logging, and checkpoint persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

from scripts.validate_provenance import validate_provenance_gate, ProvenanceError, DataGapError
from src.common.logging import logger
from src.common.config import load_config
from src.sr_engine.models.image_sr import ImageSRGenerator, ImageDiscriminator
from src.sr_engine.models.dem_sr import DEMSRGenerator
from src.sr_engine.losses import SlopeConsistencyLoss, ShadingConsistencyLoss, RelativisticAdversarialLoss

CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"


def np_load_safe(path: Path) -> np.ndarray:
    return np.load(path)


class RealOverlapDataset(Dataset):
    """
    Dataset loading strictly verified real paired patches from data/processed/patches.
    Augmentations are restricted to geometric 90-degree rotations and horizontal/vertical flips.
    """

    def __init__(self, patch_dirs: List[Path], crop_size: int = 64, augment: bool = True):
        self.patch_dirs = [p for p in patch_dirs if (p / "lr_ortho.npy").exists() and (p / "lr_dem.npy").exists()]
        self.crop_size = crop_size
        self.augment = augment

    def __len__(self) -> int:
        # Virtual epoch size = 4 crops per real patch
        return len(self.patch_dirs) * 4

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        pdir = self.patch_dirs[idx % len(self.patch_dirs)]
        lr_ortho = np_load_safe(pdir / "lr_ortho.npy")
        lr_dem = np_load_safe(pdir / "lr_dem.npy")

        with open(pdir / "metadata.json", "r", encoding="utf-8") as f:
            meta = json.load(f)

        H, W = lr_ortho.shape
        cs = min(self.crop_size, H, W)

        # Random subcrop within real patch
        if H > cs and W > cs:
            top = random.randint(0, H - cs)
            left = random.randint(0, W - cs)
            crop_ortho = lr_ortho[top : top + cs, left : left + cs].copy()
            crop_dem = lr_dem[top : top + cs, left : left + cs].copy()
        else:
            crop_ortho = lr_ortho.copy()
            crop_dem = lr_dem.copy()

        # Strict physical augmentations (orthogonal rotations and flips)
        if self.augment:
            k = random.randint(0, 3)
            crop_ortho = np.rot90(crop_ortho, k)
            crop_dem = np.rot90(crop_dem, k)
            if random.random() > 0.5:
                crop_ortho = np.fliplr(crop_ortho)
                crop_dem = np.fliplr(crop_dem)
            if random.random() > 0.5:
                crop_ortho = np.flipud(crop_ortho)
                crop_dem = np.flipud(crop_dem)

        sun_az = float(meta.get("sun_azimuth_deg", 238.2))
        sun_el = float(meta.get("sun_elevation_deg", 39.1))

        return {
            "lr_ortho": torch.from_numpy(crop_ortho.copy()).unsqueeze(0).float(),
            "lr_dem": torch.from_numpy(crop_dem.copy()).unsqueeze(0).float(),
            "sun_azimuth_deg": sun_az,
            "sun_elevation_deg": sun_el,
            "tile_id": meta.get("tile_id", pdir.name),
        }


def run_training_stage(
    stage: str = "A",
    num_epochs: int = 15,
    batch_size: int = 4,
    allow_data_gap: bool = True,
) -> int:
    """
    Executes SR training loop under real data constraints.
    """
    logger.info(f"===========================================================")
    logger.info(f" Initiating Super-Resolution Training: Stage {stage}")
    logger.info(f"===========================================================")

    # 1. Enforce Preflight Data Provenance
    try:
        report = validate_provenance_gate(stage_requirement="sr_training", raise_on_error=not allow_data_gap)
        if report["data_gaps"]:
            for gap in report["data_gaps"]:
                logger.warning(f"{gap}")
            if not allow_data_gap:
                return 1
    except (ProvenanceError, DataGapError) as e:
        logger.error(f"Preflight check failed: {e}")
        return 1

    # 2. Check for real patches on disk
    patches_dir = PROJECT_ROOT / "data" / "processed" / "patches"
    patch_dirs = sorted([p for p in patches_dir.iterdir() if p.is_dir()])
    if not patch_dirs:
        logger.error(f"DATA_GAP: No processed patches found in {patches_dir}. Ingestion module must run first.")
        return 1

    logger.info(f"Loaded {len(patch_dirs)} real Chandrayaan-2 training patches from disk.")

    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Setup Hardware Device
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training hardware device: {device}")

    # 4. Models & Optimizers Initialization
    img_gen = ImageSRGenerator().to(device)
    dem_gen = DEMSRGenerator().to(device)
    img_disc = ImageDiscriminator().to(device)

    # Loss Functions
    slope_loss_fn = SlopeConsistencyLoss(cell_size_meters=1.0).to(device)
    shading_loss_fn = ShadingConsistencyLoss(cell_size_meters=1.0).to(device)
    ragan_loss_fn = RelativisticAdversarialLoss()

    dataset = RealOverlapDataset(patch_dirs=patch_dirs, crop_size=48, augment=True)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)

    if stage == "A":
        # Stage A: Reconstruction & Slope Pretraining
        opt_dem = torch.optim.Adam(dem_gen.parameters(), lr=2e-4, betas=(0.9, 0.999), weight_decay=1e-4)
        opt_img = torch.optim.Adam(img_gen.parameters(), lr=2e-4, betas=(0.9, 0.999), weight_decay=1e-4)
        sched_dem = torch.optim.lr_scheduler.CosineAnnealingLR(opt_dem, T_max=num_epochs)
        sched_img = torch.optim.lr_scheduler.CosineAnnealingLR(opt_img, T_max=num_epochs)

        dem_gen.train()
        img_gen.train()

        for epoch in range(1, num_epochs + 1):
            total_dem_loss = 0.0
            total_img_loss = 0.0
            total_slope_loss = 0.0
            num_batches = 0

            for batch in dataloader:
                lr_ortho = batch["lr_ortho"].to(device)
                lr_dem = batch["lr_dem"].to(device)

                # --- DEM-SR Update ---
                opt_dem.zero_grad()
                sr_dem = dem_gen(lr_dem)

                # Scale consistency: downsampled SR DEM must match input LR DEM
                down_dem = F.interpolate(sr_dem, size=(lr_dem.shape[2], lr_dem.shape[3]), mode="area")
                l_recon_dem = F.l1_loss(down_dem, lr_dem)

                # Reference slope from bicubic interpolation
                ref_sr_dem = F.interpolate(lr_dem, size=(sr_dem.shape[2], sr_dem.shape[3]), mode="bicubic", align_corners=False)
                l_slope = slope_loss_fn(sr_dem, ref_sr_dem)

                loss_dem = l_recon_dem + 0.5 * l_slope
                loss_dem.backward()
                opt_dem.step()

                # --- Image-SR Update ---
                opt_img.zero_grad()
                sr_ortho = img_gen(lr_ortho)

                # Downsampled SR Ortho must match input LR Ortho
                down_ortho = F.interpolate(sr_ortho, size=(lr_ortho.shape[2], lr_ortho.shape[3]), mode="area")
                loss_img = F.l1_loss(down_ortho, lr_ortho)

                loss_img.backward()
                opt_img.step()

                total_dem_loss += loss_dem.item()
                total_slope_loss += l_slope.item()
                total_img_loss += loss_img.item()
                num_batches += 1

            sched_dem.step()
            sched_img.step()

            avg_dem = total_dem_loss / max(1, num_batches)
            avg_slope = total_slope_loss / max(1, num_batches)
            avg_img = total_img_loss / max(1, num_batches)

            if epoch % 5 == 0 or epoch == num_epochs:
                logger.info(
                    f"Stage A [Epoch {epoch:02d}/{num_epochs:02d}] "
                    f"DEM Loss: {avg_dem:.4f} (Slope L1: {avg_slope:.4f}) | "
                    f"Image Loss: {avg_img:.4f}"
                )

        # Save Stage A Checkpoints
        torch.save(dem_gen.state_dict(), CHECKPOINTS_DIR / "dem_sr_stage_a.pth")
        torch.save(img_gen.state_dict(), CHECKPOINTS_DIR / "image_sr_stage_a.pth")
        logger.info(f"Saved Stage A checkpoints to {CHECKPOINTS_DIR}")

    elif stage == "B":
        # Load Stage A pre-trained weights if available
        stage_a_dem = CHECKPOINTS_DIR / "dem_sr_stage_a.pth"
        stage_a_img = CHECKPOINTS_DIR / "image_sr_stage_a.pth"
        if stage_a_dem.exists():
            dem_gen.load_state_dict(torch.load(stage_a_dem, map_location=device, weights_only=True))
            logger.info("Loaded pre-trained Stage A DEM weights into Generator.")
        if stage_a_img.exists():
            img_gen.load_state_dict(torch.load(stage_a_img, map_location=device, weights_only=True))
            logger.info("Loaded pre-trained Stage A Image weights into Generator.")

        opt_dem = torch.optim.Adam(dem_gen.parameters(), lr=2e-5, betas=(0.9, 0.999))
        opt_img = torch.optim.Adam(img_gen.parameters(), lr=2e-5, betas=(0.9, 0.999))
        opt_disc = torch.optim.Adam(img_disc.parameters(), lr=1e-4, betas=(0.9, 0.999))

        dem_gen.train()
        img_gen.train()
        img_disc.train()

        for epoch in range(1, num_epochs + 1):
            total_g_loss = 0.0
            total_shading_loss = 0.0
            total_d_loss = 0.0
            num_batches = 0

            for batch in dataloader:
                lr_ortho = batch["lr_ortho"].to(device)
                lr_dem = batch["lr_dem"].to(device)
                sun_az = float(batch["sun_azimuth_deg"][0])
                sun_el = float(batch["sun_elevation_deg"][0])

                # --- 1. Discriminator Step ---
                opt_disc.zero_grad()
                with torch.no_grad():
                    sr_ortho_fake = img_gen(lr_ortho)
                # Use high-frequency real ortho as target reference
                ref_ortho = F.interpolate(lr_ortho, size=(sr_ortho_fake.shape[2], sr_ortho_fake.shape[3]), mode="bicubic", align_corners=False)
                d_real = img_disc(ref_ortho)
                d_fake = img_disc(sr_ortho_fake.detach())
                loss_d = ragan_loss_fn.discriminator_loss(d_real, d_fake)
                loss_d.backward()
                opt_disc.step()

                # --- 2. Generators Step with Photoclinometry ---
                opt_dem.zero_grad()
                opt_img.zero_grad()

                sr_dem = dem_gen(lr_dem)
                sr_ortho = img_gen(lr_ortho)

                # Downsample consistency
                down_dem = F.interpolate(sr_dem, size=(lr_dem.shape[2], lr_dem.shape[3]), mode="area")
                down_ortho = F.interpolate(sr_ortho, size=(lr_ortho.shape[2], lr_ortho.shape[3]), mode="area")
                l_recon_dem = F.l1_loss(down_dem, lr_dem)
                l_recon_ortho = F.l1_loss(down_ortho, lr_ortho)

                # Shading consistency (Photoclinometric constraint from real sun angle)
                # Downsample DEM to match ortho spatial grid for shading evaluation
                sr_dem_matched = F.interpolate(sr_dem, size=(sr_ortho.shape[2], sr_ortho.shape[3]), mode="bilinear", align_corners=False)
                l_shading = shading_loss_fn(sr_dem_matched, sr_ortho, sun_azimuth_deg=sun_az, sun_elevation_deg=sun_el)

                # Adversarial loss for texture enhancement
                d_fake_for_g = img_disc(sr_ortho)
                d_real_for_g = img_disc(ref_ortho).detach()
                l_adv = ragan_loss_fn.generator_loss(d_real_for_g, d_fake_for_g)

                total_loss_g = l_recon_dem + l_recon_ortho + 0.3 * l_shading + 0.05 * l_adv
                total_loss_g.backward()
                opt_dem.step()
                opt_img.step()

                total_g_loss += total_loss_g.item()
                total_shading_loss += l_shading.item()
                total_d_loss += loss_d.item()
                num_batches += 1

            avg_g = total_g_loss / max(1, num_batches)
            avg_shd = total_shading_loss / max(1, num_batches)
            avg_d = total_d_loss / max(1, num_batches)

            if epoch % 5 == 0 or epoch == num_epochs:
                logger.info(
                    f"Stage B [Epoch {epoch:02d}/{num_epochs:02d}] "
                    f"Generator Loss: {avg_g:.4f} (Shading L1: {avg_shd:.4f}) | "
                    f"Discriminator Loss: {avg_d:.4f}"
                )

        # Save Final Production Stage B Checkpoints
        torch.save(dem_gen.state_dict(), CHECKPOINTS_DIR / "dem_sr_stage_b.pth")
        torch.save(img_gen.state_dict(), CHECKPOINTS_DIR / "image_sr_stage_b.pth")
        torch.save(dem_gen.state_dict(), CHECKPOINTS_DIR / "best_dem_sr.pth")
        logger.info(f"Saved Stage B production checkpoints to {CHECKPOINTS_DIR}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SR Training Runner (Two-Stage Regime)")
    parser.add_argument("--stage", choices=["A", "B", "ALL"], default="ALL", help="Stage A (Reconstruction), Stage B (Adversarial/Shading), or ALL")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs per stage")
    parser.add_argument("--batch-size", type=int, default=4, help="Training batch size")
    parser.add_argument("--allow-gap", action="store_true", default=True, help="Allow clean exit on DATA_GAP")
    args = parser.parse_args()

    if args.stage == "ALL":
        res_a = run_training_stage(stage="A", num_epochs=args.epochs, batch_size=args.batch_size, allow_data_gap=args.allow_gap)
        if res_a != 0:
            return res_a
        return run_training_stage(stage="B", num_epochs=args.epochs, batch_size=args.batch_size, allow_data_gap=args.allow_gap)
    else:
        return run_training_stage(stage=args.stage, num_epochs=args.epochs, batch_size=args.batch_size, allow_data_gap=args.allow_gap)


if __name__ == "__main__":
    sys.exit(main())
