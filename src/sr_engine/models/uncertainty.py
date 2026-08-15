"""
Epistemic Uncertainty Estimation Head (Module 2 Component)

Provides per-pixel predictive standard deviation / variance using Monte Carlo Dropout.
Downstream modules use this uncertainty map to conservatively flag low-confidence areas as hazardous.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Tuple


class MCDropoutEstimator:
    """
    Monte Carlo Dropout uncertainty estimator for PyTorch models.
    Enables dropout during inference to sample multiple stochastic forward passes.
    """

    def __init__(self, model: nn.Module, num_samples: int = 10):
        self.model = model
        self.num_samples = num_samples

    def _enable_dropout(self) -> None:
        """Sets dropout layers to train mode while keeping batchnorm in eval mode."""
        for m in self.model.modules():
            if isinstance(m, nn.Dropout) or isinstance(m, nn.Dropout2d):
                m.train()

    @torch.no_grad()
    def estimate_uncertainty(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs MC Dropout passes.
        
        Returns:
            mean_prediction: Tensor of shape (B, C, H, W)
            uncertainty_map (std dev): Tensor of shape (B, C, H, W)
        """
        self.model.eval()
        self._enable_dropout()

        samples = []
        for _ in range(self.num_samples):
            pred = self.model(x)
            samples.append(pred.unsqueeze(0))

        # Stack shape: (num_samples, B, C, H, W)
        stacked = torch.cat(samples, dim=0)
        mean_pred = torch.mean(stacked, dim=0)
        uncertainty = torch.std(stacked, dim=0)

        return mean_pred, uncertainty
