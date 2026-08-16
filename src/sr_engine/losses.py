"""
Loss Functions for Super-Resolution and Topographic Fusion (Module 2 Component)

Includes:
- ElevationRangeAnchorLoss (Anti-inflation and mean-elevation conservation)
- Topographic Slope-Consistency Loss (Differentiable Horn gradient with angle of repose penalty)
- Photoclinometric Shading-Consistency Loss (Lambertian / Shape-from-Shading with grazing angle safeguards)
- Relativistic Average GAN Loss (RaGAN - restricted strictly to optical orthoimage domain)
"""

from __future__ import annotations

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class ElevationRangeAnchorLoss(nn.Module):
    """
    Prevents DEM elevation range inflation and macroscopic drift.
    
    Penalizes deviations in:
    1. Local mean elevation (mean anchor)
    2. Dynamic range (|max(z) - min(z)|)
    3. Extreme bounds (min and max preservation)
    """

    def __init__(self, range_weight: float = 1.0, mean_weight: float = 1.0, bounds_weight: float = 0.5):
        super().__init__()
        self.range_weight = range_weight
        self.mean_weight = mean_weight
        self.bounds_weight = bounds_weight

    def forward(self, pred_dem: torch.Tensor, target_dem: torch.Tensor) -> torch.Tensor:
        # Match dimensions if needed (pred_dem is 1m, target_dem may be 5m/10m)
        if pred_dem.shape[-2:] != target_dem.shape[-2:]:
            down_pred = F.interpolate(pred_dem, size=target_dem.shape[-2:], mode="area")
        else:
            down_pred = pred_dem

        # 1. Mean Elevation Conservation
        mean_pred = torch.mean(down_pred, dim=(-2, -1))
        mean_targ = torch.mean(target_dem, dim=(-2, -1))
        l_mean = F.l1_loss(mean_pred, mean_targ)

        # 2. Dynamic Elevation Range Conservation (Max - Min)
        max_pred = torch.amax(down_pred, dim=(-2, -1))
        min_pred = torch.amin(down_pred, dim=(-2, -1))
        range_pred = max_pred - min_pred

        max_targ = torch.amax(target_dem, dim=(-2, -1))
        min_targ = torch.amin(target_dem, dim=(-2, -1))
        range_targ = max_targ - min_targ

        l_range = F.l1_loss(range_pred, range_targ)

        # 3. Min / Max Boundary Anchoring
        l_bounds = (F.l1_loss(min_pred, min_targ) + F.l1_loss(max_pred, max_targ)) / 2.0

        return self.mean_weight * l_mean + self.range_weight * l_range + self.bounds_weight * l_bounds


class SlopeConsistencyLoss(nn.Module):
    """
    Penalizes differences in spatial terrain gradients (slope) between predicted DEM and target.
    Uses Sobel/Horn kernels for differentiable gradient computation and penalizes non-physical
    slopes exceeding the lunar angle of repose (~35 degrees).
    """

    def __init__(self, cell_size_meters: float = 1.0, max_slope_deg: float = 35.0):
        super().__init__()
        self.cell_size_meters = cell_size_meters
        self.max_slope_rad = math.radians(max_slope_deg)
        self.max_slope_gradient = math.tan(self.max_slope_rad)

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

        # Primary slope gradient L1 match
        l_slope = F.l1_loss(slope_pred, slope_targ)

        # Repose Penalty: penalize slope gradients exceeding physical lunar threshold
        excess_slope = F.relu(slope_pred - self.max_slope_gradient)
        repose_penalty = torch.mean(excess_slope**2)

        return l_slope + 0.5 * repose_penalty


class ShadingConsistencyLoss(nn.Module):
    """
    Computes photoclinometry loss: compares synthetic Lambertian shading from the DEM
    against the SR orthoimage intensity given real Sun elevation and azimuth angles.
    Includes safeguards against division by zero and grazing illumination angle divergence.
    """

    def __init__(self, cell_size_meters: float = 1.0, min_elevation_deg: float = 5.0):
        super().__init__()
        self.cell_size_meters = cell_size_meters
        self.min_elevation_deg = min_elevation_deg
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
        # Clamp sun elevation to avoid numerical singularity at 0 deg horizon
        effective_sun_el = max(float(sun_elevation_deg), self.min_elevation_deg)

        p = F.conv2d(pred_dem, self.kx, padding=1)
        q = F.conv2d(pred_dem, self.ky, padding=1)

        norm = torch.sqrt(p**2 + q**2 + 1.0 + 1e-7)
        nx = -p / norm
        ny = -q / norm
        nz = 1.0 / norm

        az_rad = torch.tensor(sun_azimuth_deg * math.pi / 180.0, device=pred_dem.device)
        el_rad = torch.tensor(effective_sun_el * math.pi / 180.0, device=pred_dem.device)
        sx = torch.sin(az_rad) * torch.cos(el_rad)
        sy = torch.cos(az_rad) * torch.cos(el_rad)
        sz = torch.sin(el_rad)

        cos_i = nx * sx + ny * sy + nz * sz
        shaded = torch.clamp(cos_i, 0.0, 1.0)

        # Normalize ortho to [0, 1] range safely
        ortho_min = sr_ortho.amin(dim=(-2, -1), keepdim=True)
        ortho_max = sr_ortho.amax(dim=(-2, -1), keepdim=True)
        ortho_norm = (sr_ortho - ortho_min) / (ortho_max - ortho_min + 1e-7)

        return F.l1_loss(shaded, ortho_norm)


class RelativisticAdversarialLoss(nn.Module):
    """
    Relativistic Average GAN (RaGAN) loss for generator and discriminator.
    Strictly isolated to optical orthoimagery (texture enhancement) - never applied to DEM elevation.
    """

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

