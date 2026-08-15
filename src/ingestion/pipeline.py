"""
Module 1: Ingestion & Preprocessing Pipeline Entrypoint
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from scripts.validate_provenance import validate_provenance_gate, ProvenanceError, DataGapError
from src.common.logging import logger
from src.ingestion.overlap_detector import detect_real_overlaps


def run_ingestion_pipeline(allow_data_gap: bool = True) -> int:
    logger.info("Starting Module 1: Ingestion & Preprocessing Pipeline")

    # Step 1: Preflight Data Provenance Gate
    try:
        report = validate_provenance_gate(stage_requirement="ingestion", raise_on_error=not allow_data_gap)
        if report["data_gaps"]:
            for gap in report["data_gaps"]:
                logger.warning(f"DATA_GAP: {gap}")
            if not allow_data_gap:
                return 1
    except (ProvenanceError, DataGapError) as e:
        logger.error(f"Preflight validation halted ingestion: {e}")
        return 1

    # Step 2: Ingest Chandrayaan-2 TMC Scenes
    from src.ingestion.ingest_real_scene import ingest_real_chandrayaan2_scene
    dtm_tif = Path("data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18.tif")
    dtm_xml = Path("data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_dtm_d18.xml")
    oth_tif = Path("data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_oth_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_oth_d18.tif")
    oth_xml = Path("data/raw/tmc/ch2_tmc_ndn_20220511T0809312081_d_oth_d18_5m/data/derived/20220511/ch2_tmc_ndn_20220511T0809312081_d_oth_d18.xml")

    if dtm_tif.exists() and oth_tif.exists():
        tmc_patches = ingest_real_chandrayaan2_scene(
            dtm_tif_path=dtm_tif,
            dtm_xml_path=dtm_xml,
            oth_tif_path=oth_tif,
            oth_xml_path=oth_xml,
        )
        logger.info(f"Ingested {len(tmc_patches)} Chandrayaan-2 TMC patches.")

    # Step 3: Ingest NASA LRO NAC & SLDEM Products
    from src.ingestion.ingest_nac_sldem import ingest_real_nac_and_sldem
    nac_patches = ingest_real_nac_and_sldem()
    logger.info(f"Ingested {len(nac_patches)} NASA LRO NAC / SLDEM patches.")

    # Step 4: Overlap Footprint Discovery
    overlaps = detect_real_overlaps()
    logger.info(f"Overlap detection step finished. Total overlap regions: {len(overlaps)}")

    return 0


if __name__ == "__main__":
    sys.exit(run_ingestion_pipeline(allow_data_gap=True))
