"""
Safety-Critical Feature Cross-Checking (Module 3 & Section 12 Requirement)

Cross-checks geometric DEM detections against appearance-based orthoimage detections.
Safety Rule: When the two independent detection paths disagree, mark the pixel as UNCERTAIN,
never default to safe.
"""

from __future__ import annotations

import numpy as np


def cross_check_hazard_detections(
    geom_crater_mask: np.ndarray,
    geom_boulder_mask: np.ndarray,
    app_crater_mask: np.ndarray,
    app_boulder_mask: np.ndarray,
    sr_uncertainty_map: np.ndarray,
    uncertainty_threshold: float = 0.65,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Cross-checks geometric and appearance detection masks.
    
    Returns:
        tuple of:
          - confirmed_hazard_mask (both paths agree it is hazardous)
          - uncertain_hazard_mask (paths disagree or SR uncertainty is high)
          - combined_conservative_hazard_mask (confirmed OR uncertain)
    """
    geom_any = np.logical_or(geom_crater_mask > 0, geom_boulder_mask > 0)
    app_any = np.logical_or(app_crater_mask > 0, app_boulder_mask > 0)

    # Agreement: both geometric and appearance paths flagged hazard
    agreed_hazard = np.logical_and(geom_any, app_any)

    # Disagreement: only one path flagged hazard
    disagreed_hazard = np.logical_xor(geom_any, app_any)

    # Low-confidence SR regions are also marked uncertain
    high_sr_uncertainty = sr_uncertainty_map > uncertainty_threshold
    uncertain_hazard = np.logical_or(disagreed_hazard, high_sr_uncertainty)

    # Asymmetric safety policy: conservative hazard flags include both agreed and uncertain
    conservative_hazard = np.logical_or(agreed_hazard, uncertain_hazard)

    return (
        agreed_hazard.astype(np.uint8),
        uncertain_hazard.astype(np.uint8),
        conservative_hazard.astype(np.uint8),
    )
