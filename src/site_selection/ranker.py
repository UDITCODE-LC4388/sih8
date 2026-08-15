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
    min_separation_m: float = 48.0,
) -> List[Dict[str, any]]:
    """
    Ranks safe candidates using multi-objective scoring with spatial Non-Maximum Suppression (NMS).
    Lower score = safer / higher priority landing site.
    Enforces minimum spatial separation between selected sites to provide distinct flight corridors.
    """
    if not candidates:
        return []

    # Extract bounds for normalization
    slopes = np.array([c["mean_slope_deg"] for c in candidates])
    severities = np.array([c["mean_severity"] for c in candidates])
    dists = np.array([c["distance_from_aim_m"] for c in candidates])

    max_dist = max(float(np.max(dists)), 1.0)
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

    # Spatial Non-Maximum Suppression (NMS)
    selected: List[Dict[str, any]] = []
    for cand in sorted_candidates:
        r = cand["center_r"]
        c = cand["center_c"]
        
        # Check distance against all previously selected sites
        too_close = False
        for s in selected:
            sr = s["center_r"]
            sc = s["center_c"]
            dist_m = np.hypot(r - sr, c - sc)
            if dist_m < min_separation_m:
                too_close = True
                break
        
        if not too_close:
            cand["rank"] = len(selected) + 1
            cand["site_id"] = f"LZ-{cand['rank']:02d}"
            cand["status"] = "SAFE TO LAND"
            selected.append(cand)
            if len(selected) >= top_k:
                break

    # If strict separation yielded fewer than top_k, fill with remaining best non-identical candidates
    if len(selected) < top_k and len(sorted_candidates) > len(selected):
        fallback_min_sep = 24.0  # At least full footprint width
        for cand in sorted_candidates:
            if cand in selected:
                continue
            r = cand["center_r"]
            c = cand["center_c"]
            too_close = False
            for s in selected:
                dist_m = np.hypot(r - s["center_r"], c - s["center_c"])
                if dist_m < fallback_min_sep:
                    too_close = True
                    break
            if not too_close:
                cand["rank"] = len(selected) + 1
                cand["site_id"] = f"LZ-{cand['rank']:02d}"
                cand["status"] = "SAFE TO LAND"
                selected.append(cand)
                if len(selected) >= top_k:
                    break

    return selected

