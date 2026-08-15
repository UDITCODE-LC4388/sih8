"""
Module 3: Hazard Feature Extraction.
"""

from src.hazard_extraction.slope import extract_slope_hazard
from src.hazard_extraction.geometric_detector import detect_geometric_hazards
from src.hazard_extraction.appearance_detector import detect_appearance_hazards
from src.hazard_extraction.cross_check import cross_check_hazard_detections
from src.hazard_extraction.shadow_model import compute_raycast_shadows
from src.hazard_extraction.distribution import compute_hazard_density_map

__all__ = [
    "extract_slope_hazard",
    "detect_geometric_hazards",
    "detect_appearance_hazards",
    "cross_check_hazard_detections",
    "compute_raycast_shadows",
    "compute_hazard_density_map",
]
