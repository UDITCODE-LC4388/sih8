"""
Unit tests for safe landing site search and ranking.
"""

import numpy as np
import pytest
from src.site_selection.sliding_window import find_candidate_landing_patches
from src.site_selection.ranker import rank_landing_candidates


def test_sliding_window_finds_clear_region():
    # 128x128 grid, completely flat and safe except for a hazard in the bottom right
    h, w = 128, 128
    binary_hazard = np.zeros((h, w), dtype=np.uint8)
    slope_deg = np.zeros((h, w), dtype=np.float32)
    graded_severity = np.zeros((h, w), dtype=np.float32)

    # Hazard cluster in bottom right
    binary_hazard[80:120, 80:120] = 1

    accepted, rejected = find_candidate_landing_patches(
        binary_hazard_map=binary_hazard,
        slope_deg_map=slope_deg,
        graded_severity_map=graded_severity,
        patch_size_cells=24,
        stride_cells=8,
        nominal_aim_point=(32, 32),
    )

    assert len(accepted) > 0
    assert len(rejected) > 0

    # Ensure all rejected candidates have a discard reason
    for rej in rejected:
        assert "discard_reason" in rej
        assert len(rej["discard_reason"]) > 0

    # Rank accepted candidates
    ranked = rank_landing_candidates(accepted, top_k=5)
    assert len(ranked) <= 5
    # The closest candidate to aim point (32, 32) should rank highest
    top_candidate = ranked[0]
    assert top_candidate["distance_from_aim_m"] <= ranked[-1]["distance_from_aim_m"]


def test_rank_landing_candidates_spatial_nms():
    # Create synthetic candidates clustered close together and some far apart
    candidates = [
        {"center_r": 100, "center_c": 100, "mean_slope_deg": 0.5, "mean_severity": 0.01, "distance_from_aim_m": 10.0},
        {"center_r": 104, "center_c": 100, "mean_slope_deg": 0.5, "mean_severity": 0.01, "distance_from_aim_m": 12.0},
        {"center_r": 100, "center_c": 104, "mean_slope_deg": 0.6, "mean_severity": 0.01, "distance_from_aim_m": 13.0},
        {"center_r": 200, "center_c": 200, "mean_slope_deg": 0.8, "mean_severity": 0.02, "distance_from_aim_m": 50.0},
        {"center_r": 300, "center_c": 150, "mean_slope_deg": 0.9, "mean_severity": 0.02, "distance_from_aim_m": 80.0},
    ]

    ranked = rank_landing_candidates(candidates, top_k=3, min_separation_m=48.0)
    assert len(ranked) == 3

    # Check pairwise distances
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            dist = np.hypot(ranked[i]["center_r"] - ranked[j]["center_r"], ranked[i]["center_c"] - ranked[j]["center_c"])
            assert dist >= 48.0

