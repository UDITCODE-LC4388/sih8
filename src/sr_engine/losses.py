"""
Loss Functions for Super-Resolution and Fusion (Module 2 Component)

Includes:
- L1 Reconstruction Loss
- Relativistic Average GAN Loss (RaGAN)
- Topographic Slope-Consistency Loss
- Photoclinometric Shading-Consistency Loss
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class SlopeConsistencyLoss(nn.Module):
    """
    Penalizes differences in spatial terrain gradients (slope) between predicted DEM and target.
    Uses Sobel/Horn kernels for differentiable gradient computation.
    """

    def __init__(self, cell_size_meters: float = 1.0):
        super().__init__()
        self.cell_size_meters = cell_size_meters
        # 3x3 Sobel/Horn gradient filters
        kx = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]]) / (8.0 * cell_size_meters)
        ky = torch.tensor([[1.0, 2.0, 1.0], [0.0, 0.0, 0.0], [-1.0, -2.0, -1.0]]) / (8.0 * cell_size_meters)
        self.register_buffer("kx", kx.view(1, 1, 3, 3))
        self.register_buffer("ky", ky.view(1, 1, 3, 3))

    def forward(self, pred_dem: torch.Tensor, target_dem: torch.Tensor) -> torch.Tensor:
        p_pred = F.conv2d(pred_dem, self.kx, padding=1)
        q_pred = F.conv2d(pred_dem, self.ky, padding=1)
        slope_pred = torch.sqrt(p_pred**2 + q_pred**2 + 1e-8)

        p_targ = F.conv2d(target_dem, self.kx, padding=1)
        q_targ = F.conv2d(target_dem, self.ky, padding=1)
        slope_targ = torch.sqrt(p_targ**2 + q_targ**2 + 1e-8)

        return F.l1_loss(slope_pred, slope_targ)


class ShadingConsistencyLoss(nn.Module):
    """
    Computes photoclinometry loss: compares synthetic Lambertian shading from the DEM
    against the SR orthoimage intensity given real Sun elevation and azimuth angles.
    """

    def __init__(self, cell_size_meters: float = 1.0):
        super().__init__()
        self.cell_size_meters = cell_size_meters
        kx = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]]) / (8.0 * cell_size_meters)
        ky = torch.tensor([[1.0, 2.0, 1.0], [0.0, 0.0, 0.0], [-1.0, -2.0, -1.0]]) / (8.0 * cell_size_meters)
        self.register_buffer("kx", kx.view(1, 1, 3, 3))
        self.register_buffer("ky", ky.view(1, 1, 3, 3))

    def forward(
        self,
        pred_dem: torch.Tensor,
        sr_ortho: torch.Tensor,
        sun_azimuth_deg: float,
        sun_elevation_deg: float,
    ) -> torch.Tensor:
        p = F.conv2d(pred_dem, self.kx, padding=1)
        q = F.conv2d(pred_dem, self.ky, padding=1)

        norm = torch.sqrt(p**2 + q**2 + 1.0)
        nx = -p / norm
        ny = -q / norm
        nz = 1.0 / norm

        az_rad = torch.tensor(sun_azimuth_deg * 3.14159265 / 180.0, device=pred_dem.device)
        el_rad = torch.tensor(sun_elevation_deg * 3.14159265 / 180.0, device=pred_dem.device)
        sx = torch.sin(az_rad) * torch.cos(el_rad)
        sy = torch.cos(az_rad) * torch.cos(el_rad)
        sz = torch.sin(el_rad)

        cos_i = nx * sx + ny * sy + nz * sz
        shaded = torch.clamp(cos_i, 0.0, 1.0)

        # Normalize ortho to [0, 1] range for comparison
        ortho_norm = (sr_ortho - sr_ortho.min()) / (sr_ortho.max() - sr_ortho.min() + 1e-8)
        return F.l1_loss(shaded, ortho_norm)


class RelativisticAdversarialLoss(nn.Module):
    """Relativistic Average GAN (RaGAN) loss for generator and discriminator."""

    def __init__(self):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()

    def generator_loss(self, d_real: torch.Tensor, d_fake: torch.Tensor) -> torch.Tensor:
        loss_fake = self.bce(d_fake - torch.mean(d_real), torch.ones_like(d_fake))
        loss_real = self.bce(d_real - torch.mean(d_fake), torch.zeros_like(d_real))
        return (loss_fake + loss_real) / 2.0

    def discriminator_loss(self, d_real: torch.Tensor, d_fake: torch.Tensor) -> torch.Tensor:
        loss_real = self.bce(d_real - torch.mean(d_fake), torch.ones_like(d_real))
        loss_fake = self.bce(d_fake - torch.mean(d_real), torch.zeros_like(d_fake))
        return (loss_real + loss_fake) / 2.0
