"""
End-to-End Real Data Processing Pipeline (SIH260008)

Executes Modules 1 through 6 on real Chandrayaan-2 TMC patches:
- Preflight Provenance Check
- 1m Super-Resolution (Image + DEM + Shading Photoclinometry + MC Uncertainty)
- 1m Hazard Feature Extraction (Horn Slope > 10°, Geometric + Photometric Craters/Boulders, Ray-cast Shadows, Density)
- Weighted-Fuzzy Hazard Map Fusion (Graded Severity + Binary Hazard Map)
- 24m x 24m Safe Landing Site Search & Multi-Criterion Ranking
- TRN Reference Packaging
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from scripts.validate_provenance import validate_provenance_gate
from src.common.logging import logger
from src.hazard_fusion.pipeline import execute_hazard_pipeline
from src.navigation_interface.trn_packager import package_trn_payload
from src.site_selection.ranker import rank_landing_candidates
from src.site_selection.sliding_window import find_candidate_landing_patches
from src.sr_engine.inference import SREngine
PATCHES_DIR = PROJECT_ROOT / "data" / "processed" / "patches"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"


def run_pipeline_on_real_patch(patch_dir: Path, sr_engine: SREngine) -> Dict[str, Any]:
    """Runs full pipeline on a single real Chandrayaan-2 patch."""
    lr_ortho_path = patch_dir / "lr_ortho.npy"
    lr_dem_path = patch_dir / "lr_dem.npy"
    meta_path = patch_dir / "metadata.json"

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    lr_ortho = np.load(lr_ortho_path)
    lr_dem = np.load(lr_dem_path)

    sun_az = float(metadata.get("sun_azimuth_deg", 238.21))
    sun_el = float(metadata.get("sun_elevation_deg", 39.14))

    tile_id = metadata["tile_id"]
    logger.info(f"===> Processing Real Patch [{tile_id}] (Elev: {metadata['dem_min_elev_m']:.1f}m to {metadata['dem_max_elev_m']:.1f}m)")

    # 1. Module 2: Super-Resolution to 1m Grid
    logger.info("  [1/5] Super-Resolving Ortho (5x) & DEM (10x) to 1 m grid spacing with uncertainty...")
    sr_ortho, sr_dem, uncert_map = sr_engine.super_resolve(
        lr_ortho=lr_ortho,
        lr_dem=lr_dem,
        sun_azimuth_deg=sun_az,
        sun_elevation_deg=sun_el,
        enable_shading_refinement=True,
    )

    # 2. Modules 3 & 4: Hazard Extraction & Weighted-Fuzzy Fusion
    logger.info("  [2/5] Extracting hazards (Slope > 10°, Craters, Boulders, Shadows, Density) and fusing...")
    hazard_results = execute_hazard_pipeline(
        sr_dem=sr_dem,
        sr_ortho=sr_ortho,
        uncertainty_map=uncert_map,
        sun_azimuth_deg=sun_az,
        sun_elevation_deg=sun_el,
        cell_size_meters=1.0,
    )

    binary_hazard = hazard_results["binary_hazard"]
    graded_severity = hazard_results["graded_severity"]
    slope_deg = hazard_results["slope_deg"]

    # 3. Module 5: Safe Landing Site Selection (24m x 24m Patch Search)
    logger.info("  [3/5] Searching for safe 24m x 24m landing patches & ranking candidates...")
    aim_point = (sr_dem.shape[0] // 2, sr_dem.shape[1] // 2)
    accepted, rejected = find_candidate_landing_patches(
        binary_hazard_map=binary_hazard,
        slope_deg_map=slope_deg,
        graded_severity_map=graded_severity,
        patch_size_cells=24,
        stride_cells=4,
        nominal_aim_point=aim_point,
    )

    ranked_sites = rank_landing_candidates(accepted, top_k=5)
    logger.info(f"  Found {len(accepted)} safe candidate zones, {len(rejected)} rejected due to hazards/slope.")
    if ranked_sites:
        top = ranked_sites[0]
        logger.info(f"  🎯 Optimal Landing Site: Center=({top['center_r']}, {top['center_c']}), Slope={top['mean_slope_deg']:.1f}°, Distance from aim={top['distance_from_aim_m']:.1f}m")

    # 4. Module 6: TRN Reference Map Packaging
    logger.info("  [4/5] Packaging onboard TRN reference payload and metadata...")
    patch_out_dir = OUTPUT_DIR / tile_id
    package_trn_payload(
        sr_ortho=sr_ortho,
        sr_dem=sr_dem,
        binary_hazard=binary_hazard,
        graded_severity=graded_severity,
        ranked_sites=ranked_sites,
        metadata=metadata,
        output_dir=patch_out_dir,
    )

    # Save visualization / debug summary
    summary = {
        "tile_id": tile_id,
        "grid_resolution_m": 1.0,
        "elevation_min_m": float(np.min(sr_dem)),
        "elevation_max_m": float(np.max(sr_dem)),
        "mean_slope_deg": float(np.mean(slope_deg)),
        "max_slope_deg": float(np.max(slope_deg)),
        "hazard_coverage_pct": float(np.mean(binary_hazard) * 100.0),
        "safe_patch_count_24m": len(accepted),
        "rejected_patch_count_24m": len(rejected),
        "top_ranked_sites": ranked_sites,
        "trn_package_path": str((patch_out_dir / "trn_reference_package.npz").relative_to(PROJECT_ROOT)),
    }

    with open(patch_out_dir / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main() -> int:
    logger.info("========================================================================")
    logger.info(" LUNAR HAZARD-MAP SUPER-RESOLUTION SYSTEM: FULL REAL-DATA PIPELINE")
    logger.info("========================================================================")

    # Preflight Check
    report = validate_provenance_gate(raise_on_error=True)
    logger.info(f"Preflight Provenance Check: {report['status']} ({report['verified_files_count']} verified files)")

    patch_dirs = sorted([p for p in PATCHES_DIR.iterdir() if p.is_dir() and (p / "lr_ortho.npy").exists()])
    if not patch_dirs:
        logger.error("No processed patches found. Run ingestion first.")
        return 1

    logger.info(f"Found {len(patch_dirs)} real lunar terrain patches to process across all sensors.\n")
    sr_engine = SREngine()

    all_summaries = []
    for pdir in patch_dirs:
        summary = run_pipeline_on_real_patch(pdir, sr_engine)
        all_summaries.append(summary)

    overall_file = OUTPUT_DIR / "overall_mission_run_summary.json"
    with open(overall_file, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2)

    logger.info("\n========================================================================")
    logger.info(f"✅ Full real-data pipeline successfully executed across {len(patch_dirs)} patches.")
    logger.info(f"Results and TRN reference packages written to: {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")
    logger.info("========================================================================")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
