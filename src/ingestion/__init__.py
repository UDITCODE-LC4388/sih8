"""
Module 1: Ingestion, Co-registration, Tiling, and Overlap Discovery.
"""

from src.ingestion.overlap_detector import detect_real_overlaps, compute_bbox_overlap
from src.ingestion.tiler import extract_tiles_from_array, save_patch_pair
from src.ingestion.pipeline import run_ingestion_pipeline

__all__ = [
    "detect_real_overlaps",
    "compute_bbox_overlap",
    "extract_tiles_from_array",
    "save_patch_pair",
    "run_ingestion_pipeline",
]
