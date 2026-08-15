"""
Constants and operational thresholds for the Lunar Hazard-Map Super-Resolution System.
Cross-referenced against ISRO Chandrayaan-3 Vikram Lander HDA specifications.
"""

from typing import Final

# ==============================================================================
# Planetary & Sensor Constants
# ==============================================================================
MOON_MEAN_RADIUS_METERS: Final[float] = 1737400.0  # IAU/IAG standard

# Native Sensor Spatial Granularities (Meters/pixel)
TMC_ORTHO_GSD_METERS: Final[float] = 5.0
TMC_DEM_GSD_METERS: Final[float] = 10.0
OHRC_ORTHO_GSD_METERS: Final[float] = 0.25
TARGET_HAZARD_GRID_GSD_METERS: Final[float] = 1.0

# Super-Resolution Upsampling Factors
IMAGE_SR_SCALE_FACTOR: Final[int] = 5   # 5m -> 1m
DEM_SR_SCALE_FACTOR: Final[int] = 10   # 10m -> 1m

# ==============================================================================
# Chandrayaan-3 Operational Hazard Thresholds (SIH260008 & Suresh/Amitabh 2024)
# ==============================================================================
SLOPE_HAZARD_THRESHOLD_DEG: Final[float] = 10.0       # > 10 deg is hazardous
CRATER_DEPTH_HAZARD_THRESHOLD_M: Final[float] = 1.0   # Operational ref ~1.2m
BOULDER_HEIGHT_DEM_THRESHOLD_M: Final[float] = 1.0    # 1m DEM resolvable limit
BOULDER_HEIGHT_SHADOW_THRESHOLD_M: Final[float] = 0.32 # 32 cm sub-meter shadow photogrammetry

# Minimum Safe Landing Patch Dimensions
LANDER_PATCH_SIZE_METERS: Final[float] = 24.0          # 24m x 24m patch
LANDER_PATCH_GRID_CELLS: Final[int] = int(LANDER_PATCH_SIZE_METERS / TARGET_HAZARD_GRID_GSD_METERS) # 24 cells at 1m

# Epistemic Uncertainty Hazard Cutoff
UNCERTAINTY_HAZARD_THRESHOLD: Final[float] = 0.65     # Conservative flagging of low confidence SR
