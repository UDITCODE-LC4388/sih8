"""
DEM Super-Resolution Branch (Module 2 Component)

Residual Channel Attention Network (RCAN / D-SRCAGAN family) for ~10x upsampling
of TMC DEM (10m -> 1m). Channel attention ensures sharp crater rim edges and boulder
relief are preserved without over-smoothing.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ChannelAttention(nn.Module):
    """Channel Attention layer for adaptive feature re-weighting."""

    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(channels, channels // reduction, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels // reduction, channels, 1, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = self.fc(self.avg_pool(x))
        return x * w


class ResidualChannelAttentionBlock(nn.Module):
    """RCAB: Residual block with Channel Attention."""

    def __init__(self, channels: int = 64, reduction: int = 16):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.ca = ChannelAttention(channels, reduction)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.relu(self.conv1(x))
        res = self.ca(self.conv2(res))
        return res + x


class ResidualGroup(nn.Module):
    """Group of RCAB blocks with residual connection."""

    def __init__(self, channels: int = 64, num_blocks: int = 4):
        super().__init__()
        self.blocks = nn.Sequential(*[ResidualChannelAttentionBlock(channels) for _ in range(num_blocks)])
        self.conv = nn.Conv2d(channels, channels, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blocks(x)) + x


class DEMSRGenerator(nn.Module):
    """
    10x DEM Super-Resolution Generator with Channel Attention.
    Inputs 10m DEM elevation grid, outputs 1m SR DEM.
    """

    def __init__(self, in_channels: int = 1, out_channels: int = 1, num_features: int = 64, num_groups: int = 4):
        super().__init__()
        self.head = nn.Conv2d(in_channels, num_features, 3, padding=1)
        self.groups = nn.Sequential(*[ResidualGroup(num_features) for _ in range(num_groups)])
        self.conv_mid = nn.Conv2d(num_features, num_features, 3, padding=1)

        # 10x Upsampling block
        self.upconv = nn.Conv2d(num_features, num_features, 3, padding=1)
        self.tail = nn.Conv2d(num_features, out_channels, 3, padding=1)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Base bicubic residual connection to learn residual elevation detail
        base_upsampled = F.interpolate(x, scale_factor=10.0, mode="bicubic", align_corners=False)

        feat = self.head(x)
        res = self.conv_mid(self.groups(feat))
        feat = feat + res

        feat = F.interpolate(feat, scale_factor=10.0, mode="bicubic", align_corners=False)
        feat = self.relu(self.upconv(feat))
        elev_residual = self.tail(feat)

        # SR DEM is base interpolation plus learned high-frequency topographic residual
        sr_dem = base_upsampled + elev_residual
        return sr_dem
