"""
Module 2: Super-Resolution Engine.
"""

from src.sr_engine.models.image_sr import ImageSRGenerator, ImageDiscriminator
from src.sr_engine.models.dem_sr import DEMSRGenerator
from src.sr_engine.models.uncertainty import MCDropoutEstimator
from src.sr_engine.shading_fusion import refine_dem_with_shading
from src.sr_engine.inference import SREngine

__all__ = [
    "ImageSRGenerator",
    "ImageDiscriminator",
    "DEMSRGenerator",
    "MCDropoutEstimator",
    "refine_dem_with_shading",
    "SREngine",
]
