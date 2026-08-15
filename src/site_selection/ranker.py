"""
Candidate Landing Site Multi-Criterion Ranking (Module 5 Component)

Ranks safe candidate patches based on a composite optimization score:
- Hazard clearance margin (distance to nearest hazard boundary)
- Topographic flatness (minimal slope)
- Minimal graded severity
- Minimal Delta-V / fuel retargeting penalty from nominal aim point
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np


def rank_landing_candidates(
    candidates: List[Dict[str, any]],
    top_k: int = 10,
    w_slope: float = 0.35,
    w_severity: float = 0.35,
    w_distance: float = 0.30,
) -> List[Dict[str, any]]:
    """
    Ranks safe candidates using multi-objective scoring.
    Lower score = safer / higher priority landing site.
    """
    if not candidates:
        return []

    # Extract bounds for normalization
    slopes = np.array([c["mean_slope_deg"] for c in candidates])
    severities = np.array([c["mean_severity"] for c in candidates])
    dists = np.array([c["distance_from_aim_m"] for c in candidates])

    max_dist = max(np.max(dists), 1.0)
    norm_slopes = slopes / 10.0  # Max acceptable is 10 deg
    norm_severities = severities  # [0, 1]
    norm_dists = dists / max_dist  # [0, 1]

    for idx, c in enumerate(candidates):
        composite_score = (
            w_slope * norm_slopes[idx] +
            w_severity * norm_severities[idx] +
            w_distance * norm_dists[idx]
        )
        c["composite_rank_score"] = float(composite_score)

    # Sort ascending by composite score (lowest penalty = best)
    sorted_candidates = sorted(candidates, key=lambda x: x["composite_rank_score"])
    return sorted_candidates[:top_k]
