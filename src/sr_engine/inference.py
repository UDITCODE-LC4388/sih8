"""
Super-Resolution Inference Pipeline (Module 2 Component)

Lifts TMC 5 m orthoimage and 10 m DEM to 1 m hazard-map grid with uncertainty estimation
and shading-guided photoclinometric refinement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import torch

from src.common.logging import logger
from src.sr_engine.models.image_sr import ImageSRGenerator
from src.sr_engine.models.dem_sr import DEMSRGenerator
from src.sr_engine.models.uncertainty import MCDropoutEstimator
from src.sr_engine.shading_fusion import refine_dem_with_shading

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"


class SREngine:
    """End-to-end Super-Resolution Inference Engine."""

    def __init__(
        self,
        image_generator: Optional[ImageSRGenerator] = None,
        dem_generator: Optional[DEMSRGenerator] = None,
        device: Optional[torch.device] = None,
        load_checkpoints: bool = True,
    ):
        self.device = device or torch.device(
            "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.image_gen = image_generator or ImageSRGenerator()
        self.dem_gen = dem_generator or DEMSRGenerator()

        # Check for pre-trained weights in checkpoints/
        if load_checkpoints:
            self._load_best_weights()

        self.image_gen.to(self.device).eval()
        self.dem_gen.to(self.device).eval()

        self.uncertainty_estimator = MCDropoutEstimator(self.dem_gen, num_samples=8)

    def _load_best_weights(self) -> None:
        """Loads Stage B or Stage A checkpoint weights if present on disk."""
        # DEM Generator weights
        for ckpt_name in ["best_dem_sr.pth", "dem_sr_stage_b.pth", "dem_sr_stage_a.pth"]:
            ckpt_path = CHECKPOINTS_DIR / ckpt_name
            if ckpt_path.exists():
                try:
                    self.dem_gen.load_state_dict(torch.load(ckpt_path, map_location=self.device, weights_only=True))
                    logger.info(f"SREngine: Loaded DEM weights from {ckpt_name}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {ckpt_name}: {e}")

        # Image Generator weights
        for ckpt_name in ["image_sr_stage_b.pth", "image_sr_stage_a.pth"]:
            ckpt_path = CHECKPOINTS_DIR / ckpt_name
            if ckpt_path.exists():
                try:
                    self.image_gen.load_state_dict(torch.load(ckpt_path, map_location=self.device, weights_only=True))
                    logger.info(f"SREngine: Loaded Image weights from {ckpt_name}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {ckpt_name}: {e}")

    @torch.no_grad()
    def super_resolve(
        self,
        lr_ortho: np.ndarray,
        lr_dem: np.ndarray,
        sun_azimuth_deg: float,
        sun_elevation_deg: float,
        enable_shading_refinement: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Executes super-resolution on real TMC patch arrays.
        
        Args:
            lr_ortho: 2D float array of 5m TMC orthoimage.
            lr_dem: 2D float array of 10m TMC DEM.
            sun_azimuth_deg: Sun azimuth angle in degrees.
            sun_elevation_deg: Sun elevation angle in degrees.
            enable_shading_refinement: Apply photoclinometric DEM refinement.
            
        Returns:
            Tuple of (sr_ortho_1m, sr_dem_1m, uncertainty_map_1m).
        """
        # Prepare tensors
        t_ortho = torch.from_numpy(lr_ortho).unsqueeze(0).unsqueeze(0).float().to(self.device)
        t_dem = torch.from_numpy(lr_dem).unsqueeze(0).unsqueeze(0).float().to(self.device)

        # 1. Image SR (5x upsampling: 5m -> 1m)
        sr_ortho_tensor = self.image_gen(t_ortho)
        sr_ortho = sr_ortho_tensor.squeeze().cpu().numpy()

        # 2. DEM SR with Uncertainty (10x upsampling: 10m -> 1m)
        sr_dem_tensor, uncert_tensor = self.uncertainty_estimator.estimate_uncertainty(t_dem)
        sr_dem = sr_dem_tensor.squeeze().cpu().numpy()
        uncert_map = uncert_tensor.squeeze().cpu().numpy()

        # 3. Photoclinometric Shading Refinement
        if enable_shading_refinement:
            sr_dem = refine_dem_with_shading(
                sr_dem=sr_dem,
                sr_ortho=sr_ortho,
                sun_azimuth_deg=sun_azimuth_deg,
                sun_elevation_deg=sun_elevation_deg,
                cell_size_meters=1.0,
            )

        return sr_ortho, sr_dem, uncert_map
