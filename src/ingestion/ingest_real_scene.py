"""
Real Chandrayaan-2 TMC Scene Ingestion & Patch Extractor (Module 1 Component)

Reads real 16-bit Chandrayaan-2 DTM and Ortho GeoTIFF rasters with zarr/tifffile windowing,
applies radiometric normalization, and exports co-registered 256x256 px patch bundles
with complete solar and orbital metadata into data/processed/patches/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import tifffile

from scripts.validate_provenance import validate_provenance_gate
from src.common.geo_utils import radiometric_mean_2sigma_stretch
from src.common.logging import logger
from src.ingestion.pds_reader import parse_pds4_xml_label

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_PATCHES_DIR = PROJECT_ROOT / "data" / "processed" / "patches"


def ingest_real_chandrayaan2_scene(
    dtm_tif_path: Path,
    dtm_xml_path: Path,
    oth_tif_path: Path,
    oth_xml_path: Path,
    output_dir: Path = PROCESSED_PATCHES_DIR,
    sample_windows: Optional[List[Tuple[int, int, int, int]]] = None,
    patch_size: int = 256,
) -> List[Path]:
    """
    Ingests and tiles real Chandrayaan-2 TMC scene products into standardized patch pairs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Parse PDS4 metadata
    dtm_meta = parse_pds4_xml_label(dtm_xml_path)
    oth_meta = parse_pds4_xml_label(oth_xml_path)

    logger.info(f"Ingesting real Chandrayaan-2 TMC Scene: {dtm_meta.start_time[:10]}")
    logger.info(f"Solar geometry: Elevation={dtm_meta.sun_elevation_deg}°, Azimuth={dtm_meta.sun_azimuth_deg}°")

    # If no specific window offsets provided, sample high-relief sections across the strip
    if sample_windows is None:
        # Sample across the strip where interesting crater/terrain features exist
        # Strip dimensions: ~306000 lines x 12450 samples
        sample_windows = [
            (25000, 4000, patch_size, patch_size),
            (25000 + patch_size, 4000, patch_size, patch_size),
            (60000, 5000, patch_size, patch_size),
            (60000 + patch_size, 5000, patch_size, patch_size),
            (120000, 6000, patch_size, patch_size),
            (120000 + patch_size, 6000, patch_size, patch_size),
            (180000, 4500, patch_size, patch_size),
            (180000 + patch_size, 4500, patch_size, patch_size),
        ]

    created_patch_dirs: List[Path] = []

def read_uncompressed_tif_window(
    tif_path: Path,
    row_offset: int,
    col_offset: int,
    num_rows: int,
    num_cols: int,
    dtype: np.dtype,
) -> np.ndarray:
    """Instantly reads a 2D window from an uncompressed GeoTIFF using offset table."""
    with tifffile.TiffFile(tif_path) as tif:
        page = tif.pages[0]
        seek_pos = page.dataoffsets[row_offset]
        total_samples = page.shape[1]
        bytes_per_sample = dtype.itemsize

    with open(tif_path, "rb") as f:
        f.seek(seek_pos)
        raw_bytes = f.read(num_rows * total_samples * bytes_per_sample)
        full_width_block = np.frombuffer(raw_bytes, dtype=dtype).reshape(num_rows, total_samples)
        window = full_width_block[:, col_offset : col_offset + num_cols].copy()

    return window.astype(np.float32)


def ingest_real_chandrayaan2_scene(
    dtm_tif_path: Path,
    dtm_xml_path: Path,
    oth_tif_path: Path,
    oth_xml_path: Path,
    output_dir: Path = PROCESSED_PATCHES_DIR,
    sample_windows: Optional[List[Tuple[int, int, int, int]]] = None,
    patch_size: int = 256,
) -> List[Path]:
    """
    Ingests and tiles real Chandrayaan-2 TMC scene products into standardized patch pairs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Parse PDS4 metadata
    dtm_meta = parse_pds4_xml_label(dtm_xml_path)
    oth_meta = parse_pds4_xml_label(oth_xml_path)

    logger.info(f"Ingesting real Chandrayaan-2 TMC Scene: {dtm_meta.start_time[:10]}")
    logger.info(f"Solar geometry: Elevation={dtm_meta.sun_elevation_deg}°, Azimuth={dtm_meta.sun_azimuth_deg}°")

    if sample_windows is None:
        sample_windows = [
            (25000, 4000, patch_size, patch_size),
            (25000 + patch_size, 4000, patch_size, patch_size),
            (60000, 5000, patch_size, patch_size),
            (60000 + patch_size, 5000, patch_size, patch_size),
            (120000, 6000, patch_size, patch_size),
            (120000 + patch_size, 6000, patch_size, patch_size),
            (180000, 4500, patch_size, patch_size),
            (180000 + patch_size, 4500, patch_size, patch_size),
        ]

    created_patch_dirs: List[Path] = []

    for idx, (r_off, c_off, h, w) in enumerate(sample_windows, start=1):
        tile_id = f"ch2_tmc_patch_{idx:03d}_r{r_off}_c{c_off}"
        patch_dir = output_dir / tile_id

        raw_dtm_crop = read_uncompressed_tif_window(
            dtm_tif_path, r_off, c_off, h, w, dtype=np.dtype("<i2")
        )
        raw_oth_crop = read_uncompressed_tif_window(
            oth_tif_path, r_off, c_off, h, w, dtype=np.dtype("<u2")
        )

        valid_dtm = np.isfinite(raw_dtm_crop) & (raw_dtm_crop > -30000)
        if not np.any(valid_dtm):
            continue

        patch_dir.mkdir(parents=True, exist_ok=True)

        norm_ortho = radiometric_mean_2sigma_stretch(raw_oth_crop)
        clean_dem = raw_dtm_crop.copy()
        clean_dem[~valid_dtm] = np.mean(clean_dem[valid_dtm])

        metadata = {
            "tile_id": tile_id,
            "mission": "Chandrayaan-2",
            "instrument": "TMC",
            "source_archive": "ISRO ISSDC / PRADAN",
            "dtm_source_file": dtm_tif_path.name,
            "oth_source_file": oth_tif_path.name,
            "acquisition_date": dtm_meta.start_time[:10],
            "sun_elevation_deg": dtm_meta.sun_elevation_deg,
            "sun_azimuth_deg": dtm_meta.sun_azimuth_deg,
            "row_offset": r_off,
            "col_offset": c_off,
            "height_px": h,
            "width_px": w,
            "native_dem_resolution_m": 5.0,
            "native_ortho_resolution_m": 5.0,
            "dem_min_elev_m": float(np.min(clean_dem)),
            "dem_max_elev_m": float(np.max(clean_dem)),
            "dem_mean_elev_m": float(np.mean(clean_dem)),
            "provided_by_user": True,
        }

        np.save(patch_dir / "lr_ortho.npy", norm_ortho.astype(np.float32))
        np.save(patch_dir / "lr_dem.npy", clean_dem.astype(np.float32))

        with open(patch_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        created_patch_dirs.append(patch_dir)
        logger.info(
            f"Generated real patch [{tile_id}]: Elev={metadata['dem_min_elev_m']:.1f}m to "
            f"{metadata['dem_max_elev_m']:.1f}m | SunEl={metadata['sun_elevation_deg']}°"
        )

    return created_patch_dirs


def main() -> int:
    dtm_tif = PROJECT_ROOT / "data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18.tif"
    dtm_xml = PROJECT_ROOT / "data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18.xml"
    oth_tif = PROJECT_ROOT / "data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_oth_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_oth_d18.tif"
    oth_xml = PROJECT_ROOT / "data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_oth_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_oth_d18.xml"

    if not dtm_tif.exists() or not oth_tif.exists():
        logger.error("Required Chandrayaan-2 raw data files missing.")
        return 1

    patches = ingest_real_chandrayaan2_scene(
        dtm_tif_path=dtm_tif,
        dtm_xml_path=dtm_xml,
        oth_tif_path=oth_tif,
        oth_xml_path=oth_xml,
    )
    logger.info(f"Ingestion complete: {len(patches)} real patches ready.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
