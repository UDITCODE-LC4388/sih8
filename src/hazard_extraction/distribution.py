"""
Crater & Boulder Spatial Distribution Risk Layer (Module 3 Component)

Calculates local spatial density and size-frequency distribution of hazards
to generate a regional risk layer across the 1m grid.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def compute_hazard_density_map(
    hazard_features_mask: np.ndarray,
    kernel_radius_cells: int = 15,
) -> np.ndarray:
    """
    Computes local hazard density using uniform circular smoothing kernel.
    
    Args:
        hazard_features_mask: 2D binary array of detected hazard points/pixels.
        kernel_radius_cells: Radius of neighborhood in cells (e.g. 15m).
        
    Returns:
        2D float array with values normalized to [0, 1] representing spatial hazard density.
    """
    y, x = np.ogrid[-kernel_radius_cells : kernel_radius_cells + 1, -kernel_radius_cells : kernel_radius_cells + 1]
    kernel = (x**2 + y**2 <= kernel_radius_cells**2).astype(np.float32)
    kernel_area = np.sum(kernel)
    kernel /= kernel_area

    density = ndimage.convolve(hazard_features_mask.astype(np.float32), kernel, mode="reflect")
    max_d = np.max(density)
    if max_d > 0:
        norm_density = density / max_d
    else:
        norm_density = density

    return norm_density.astype(np.float32)
