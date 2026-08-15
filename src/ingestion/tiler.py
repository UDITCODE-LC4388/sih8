"""
Tiling and Patch Extraction Engine (Module 1 Component)

Extracts fixed-size patches (e.g. 256x256 px) from full real TMC/OHRC scenes
while strictly preserving geo-referencing, illumination, and provenance metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "patches"


def extract_tiles_from_array(
    array: np.ndarray,
    tile_size: int = 256,
    stride: Optional[int] = None,
) -> Generator[Tuple[int, int, np.ndarray], None, None]:
    """
    Yields (row_idx, col_idx, tile_array) windows of size (tile_size, tile_size).
    """
    if stride is None:
        stride = tile_size

    h, w = array.shape[:2]
    for r in range(0, h - tile_size + 1, stride):
        for c in range(0, w - tile_size + 1, stride):
            tile = array[r : r + tile_size, c : c + tile_size]
            yield r, c, tile


def save_patch_pair(
    tile_id: str,
    lr_ortho: np.ndarray,
    lr_dem: np.ndarray,
    metadata: Dict[str, Any],
    hr_ortho: Optional[np.ndarray] = None,
    hr_dem: Optional[np.ndarray] = None,
    output_base_dir: Path = PROCESSED_DIR,
) -> Path:
    """
    Saves a processed patch bundle to disk with complete metadata.
    """
    patch_dir = output_base_dir / tile_id
    patch_dir.mkdir(parents=True, exist_ok=True)

    np.save(patch_dir / "lr_ortho.npy", lr_ortho.astype(np.float32))
    np.save(patch_dir / "lr_dem.npy", lr_dem.astype(np.float32))

    if hr_ortho is not None:
        np.save(patch_dir / "hr_ortho.npy", hr_ortho.astype(np.float32))
    if hr_dem is not None:
        np.save(patch_dir / "hr_dem.npy", hr_dem.astype(np.float32))

    with open(patch_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return patch_dir
