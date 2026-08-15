"""
Centralized Configuration Loader and Schemas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default_config.yaml"


class IngestionConfig(BaseModel):
    patch_size: int = 256
    overlap_min_area_km2: float = 0.05
    target_crs: str = "IAU_2015:30100"  # Lunar Body-Fixed


class SREngineConfig(BaseModel):
    image_scale_factor: int = 5
    dem_scale_factor: int = 10
    batch_size: int = 8
    gradient_accumulation_steps: int = 2
    stage_a_lr: float = 2e-4
    stage_b_lr: float = 2e-5
    mc_dropout_samples: int = 10
    n_critic: int = 1
    weight_decay: float = 1e-4


class HazardConfig(BaseModel):
    slope_threshold_deg: float = 10.0
    crater_depth_threshold_m: float = 1.0
    boulder_height_dem_threshold_m: float = 1.0
    boulder_height_shadow_threshold_m: float = 0.32
    uncertainty_threshold: float = 0.65


class SiteSelectionConfig(BaseModel):
    patch_size_m: float = 24.0
    hazard_margin_cells: int = 2
    max_slope_deg: float = 10.0
    top_k_candidates: int = 10


class AppConfig(BaseModel):
    version: str = "1.0"
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    sr_engine: SREngineConfig = Field(default_factory=SREngineConfig)
    hazard: HazardConfig = Field(default_factory=HazardConfig)
    site_selection: SiteSelectionConfig = Field(default_factory=SiteSelectionConfig)


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return AppConfig()
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig.model_validate(raw)
