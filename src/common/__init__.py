"""
Shared common utilities, constants, logging, and configuration for Lunar Hazard Mapping.
"""

from src.common.constants import (
    MOON_MEAN_RADIUS_METERS,
    TMC_ORTHO_GSD_METERS,
    TMC_DEM_GSD_METERS,
    OHRC_ORTHO_GSD_METERS,
    TARGET_HAZARD_GRID_GSD_METERS,
    IMAGE_SR_SCALE_FACTOR,
    DEM_SR_SCALE_FACTOR,
    SLOPE_HAZARD_THRESHOLD_DEG,
    CRATER_DEPTH_HAZARD_THRESHOLD_M,
    BOULDER_HEIGHT_DEM_THRESHOLD_M,
    BOULDER_HEIGHT_SHADOW_THRESHOLD_M,
    LANDER_PATCH_SIZE_METERS,
    LANDER_PATCH_GRID_CELLS,
    UNCERTAINTY_HAZARD_THRESHOLD,
)
from src.common.logging import setup_logger, logger
from src.common.config import load_config, AppConfig
from src.common.geo_utils import (
    compute_horn_slope,
    compute_lambertian_shading,
    radiometric_mean_2sigma_stretch,
)

__all__ = [
    "MOON_MEAN_RADIUS_METERS",
    "TMC_ORTHO_GSD_METERS",
    "TMC_DEM_GSD_METERS",
    "OHRC_ORTHO_GSD_METERS",
    "TARGET_HAZARD_GRID_GSD_METERS",
    "IMAGE_SR_SCALE_FACTOR",
    "DEM_SR_SCALE_FACTOR",
    "SLOPE_HAZARD_THRESHOLD_DEG",
    "CRATER_DEPTH_HAZARD_THRESHOLD_M",
    "BOULDER_HEIGHT_DEM_THRESHOLD_M",
    "BOULDER_HEIGHT_SHADOW_THRESHOLD_M",
    "LANDER_PATCH_SIZE_METERS",
    "LANDER_PATCH_GRID_CELLS",
    "UNCERTAINTY_HAZARD_THRESHOLD",
    "setup_logger",
    "logger",
    "load_config",
    "AppConfig",
    "compute_horn_slope",
    "compute_lambertian_shading",
    "radiometric_mean_2sigma_stretch",
]
