"""
Module 2: Super-Resolution Engine.
"""

from src.sr_engine.models.image_sr import ImageSRGenerator, ImageDiscriminator
from src.sr_engine.models.dem_sr import DEMSRGenerator
from src.sr_engine.models.uncertainty import MCDropoutEstimator
from src.sr_engine.shading_fusion import refine_dem_with_shading
from src.sr_engine.losses import (
    ElevationRangeAnchorLoss,
    SlopeConsistencyLoss,
    ShadingConsistencyLoss,
    RelativisticAdversarialLoss,
)
from src.sr_engine.validation import (
    validate_downscale_cycle_invariance,
    validate_photoclinometric_rerendering,
    validate_against_lola_profile,
    generate_sr_fidelity_report,
)
from src.sr_engine.inference import SREngine

__all__ = [
    "ImageSRGenerator",
    "ImageDiscriminator",
    "DEMSRGenerator",
    "MCDropoutEstimator",
    "refine_dem_with_shading",
    "ElevationRangeAnchorLoss",
    "SlopeConsistencyLoss",
    "ShadingConsistencyLoss",
    "RelativisticAdversarialLoss",
    "validate_downscale_cycle_invariance",
    "validate_photoclinometric_rerendering",
    "validate_against_lola_profile",
    "generate_sr_fidelity_report",
    "SREngine",
]
