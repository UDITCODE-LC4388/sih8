"""
Module 7: Validation Framework.
"""

from src.validation.metrics import (
    compute_elevation_metrics,
    compute_slope_error_metrics,
    compute_hazard_iou,
    compute_detection_precision_recall,
)
from src.validation.report_generator import generate_validation_report
from src.validation.evaluate import run_evaluation

__all__ = [
    "compute_elevation_metrics",
    "compute_slope_error_metrics",
    "compute_hazard_iou",
    "compute_detection_precision_recall",
    "generate_validation_report",
    "run_evaluation",
]
