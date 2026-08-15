"""
Image Super-Resolution Branch (Module 2 Component)

ESRGAN-style Generator with Residual-in-Residual Dense Blocks (RRDB) and
Relativistic Average Discriminator (RaGAN) for 5x upsampling of TMC 5 m orthoimagery to 1 m.
Preserves small-scale photometric textures (crater rims, boulder shadow boundaries).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DenseResidualBlock5C(nn.Module):
    """5-layer dense block used within RRDB."""

    def __init__(self, channels: int = 64, growth_channels: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, growth_channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(channels + growth_channels, growth_channels, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(channels + 2 * growth_channels, growth_channels, kernel_size=3, padding=1)
        self.conv4 = nn.Conv2d(channels + 3 * growth_channels, growth_channels, kernel_size=3, padding=1)
        self.conv5 = nn.Conv2d(channels + 4 * growth_channels, channels, kernel_size=3, padding=1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), dim=1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), dim=1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), dim=1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), dim=1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    """Residual-in-Residual Dense Block."""

    def __init__(self, channels: int = 64):
        super().__init__()
        self.rdb1 = DenseResidualBlock5C(channels)
        self.rdb2 = DenseResidualBlock5C(channels)
        self.rdb3 = DenseResidualBlock5C(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class ImageSRGenerator(nn.Module):
    """
    ESRGAN-style 5x Generator for TMC Orthoimagery (5m -> 1m).
    Single channel grayscale lunar remote sensing imagery.
    """

    def __init__(self, in_channels: int = 1, out_channels: int = 1, num_features: int = 64, num_blocks: int = 6):
        super().__init__()
        self.conv_first = nn.Conv2d(in_channels, num_features, kernel_size=3, padding=1)
        self.body = nn.Sequential(*[RRDB(num_features) for _ in range(num_blocks)])
        self.conv_trunk = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)

        # 5x upsampling via bilinear upsample + convolution
        self.upconv1 = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)
        self.upconv2 = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)
        self.conv_last = nn.Conv2d(num_features, out_channels, kernel_size=3, padding=1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.conv_first(x)
        trunk = self.conv_trunk(self.body(feat))
        feat = feat + trunk

        # 5x upsampling
        feat = F.interpolate(feat, scale_factor=5.0, mode="bicubic", align_corners=False)
        feat = self.lrelu(self.upconv1(feat))
        out = self.conv_last(feat)
        return torch.sigmoid(out)


class ImageDiscriminator(nn.Module):
    """VGG-style Relativistic Discriminator for lunar orthoimagery."""

    def __init__(self, in_channels: int = 1, num_features: int = 64):
        super().__init__()
        layers = []
        # Conv 1
        layers.append(nn.Conv2d(in_channels, num_features, 3, padding=1))
        layers.append(nn.LeakyReLU(0.2, inplace=True))

        channels = [num_features, num_features * 2, num_features * 4, num_features * 8]
        for c_in, c_out in zip(channels[:-1], channels[1:]):
            layers.append(nn.Conv2d(c_in, c_out, 3, stride=2, padding=1, bias=False))
            layers.append(nn.BatchNorm2d(c_out))
            layers.append(nn.LeakyReLU(0.2, inplace=True))

        self.features = nn.Sequential(*layers)
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(channels[-1], 100),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(100, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        return self.classifier(feat)
