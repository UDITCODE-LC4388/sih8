"""
TRN Reference Map Packager (Module 6 Component)

Packages the 1 m SR reference orthoimage, DEM, and binary/graded hazard maps
into an onboard Terrain Relative Navigation (TRN) compatible payload, mirroring
the Vikram lander HDA onboard reference storage format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np


def package_trn_payload(
    sr_ortho: np.ndarray,
    sr_dem: np.ndarray,
    binary_hazard: np.ndarray,
    graded_severity: np.ndarray,
    ranked_sites: list[dict[str, Any]],
    metadata: dict[str, Any],
    output_dir: Path,
) -> Path:
    """
    Serializes and packages TRN reference datasets for lander navigation computer.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to standard compact formats
    np.savez_compressed(
        output_dir / "trn_reference_package.npz",
        ref_ortho=(sr_ortho * 255.0).astype(np.uint8),
        ref_dem=sr_dem.astype(np.float32),
        binary_hazard=binary_hazard.astype(np.uint8),
        graded_severity=(graded_severity * 255.0).astype(np.uint8),
    )

    nav_meta = {
        "format_version": "1.0-ISRO-TRN",
        "grid_spacing_meters": 1.0,
        "scene_metadata": metadata,
        "candidate_landing_sites": ranked_sites,
    }

    with open(output_dir / "nav_metadata.json", "w", encoding="utf-8") as f:
        json.dump(nav_meta, f, indent=2)

    return output_dir
