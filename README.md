# Lunar Hazard-Map Super-Resolution System

> **SIH260008 — ISRO, Space Technology / Planetary Remote Sensing**  
> *"Generation of Hazard Maps at 1 m Grid Spacing Using Super-Resolution Techniques for Safe Lunar Lander Navigation"*

---

## 0. Prime Directive — Real Data Only

This system is strictly trained, tested, and validated on **real ISRO/NASA lunar remote sensing data only**. There is no synthetic, simulated, or artificially degraded fake data in this pipeline.

- Every raster, DEM tile, or label must trace back to a verifiable ISRO (TMC, OHRC) or NASA (LRO NAC/SLDEM) product.
- Unmanifested data or missing provenance halts pipeline execution via preflight gates.
- Missing real data results in explicit `DATA_GAP` reports rather than synthetic placeholder fallbacks.

---

## 1. Directory Structure

```text
lunar-hazard-map/
  data/
    raw/
      tmc/<scene_id>/          # TMC orthoimagery and DEM products
      ohrc/<strip_id>/         # OHRC high-resolution strips
      nac_sldem/<tile_id>/     # LRO NAC / SLDEM2015 geodetic control
    manifest/
      data_manifest.yaml       # Cryptographic provenance manifest
    processed/                 # Generated patches and coregistered products
    overlaps/                  # Identified TMC-OHRC overlap footprints
  scripts/
    validate_provenance.py     # Preflight data gate
    build_manifest.py          # Manifest registration helper
  src/
    common/                    # Shared geospatial tools, logger, configs
    ingestion/                 # Module 1: ISIS3/ASP ingest, co-registration, tiling
    sr_engine/                 # Module 2: Image-SR, DEM-SR, shading fusion
    hazard_extraction/         # Module 3: Slope, crater/boulder, shadow, distribution
    hazard_fusion/             # Module 4: Weighted-fuzzy hazard fusion
    site_selection/            # Module 5: Sliding-window safe site search
    navigation_interface/      # Module 6: TRN packaging and GCS dashboard API
    validation/                # Module 7: Real overlap validation framework
  configs/                     # Hydra / YAML experiment and module configurations
  docs/
    validation_reports/        # Auto-generated, run-linked validation reports
  tests/                       # Unit and integration test suites
```

---

## 2. Getting Started & Installation

### Environment Setup

Using `conda` / `mamba`:
```bash
conda env create -f environment.yml
conda activate lunar-sr
```

Or using `pip`:
```bash
pip install -e ".[dev]"
```

---

## 3. Adding Real Data & Preflight Validation

1. Place real data files inside the appropriate directory in `data/raw/`:
   - `data/raw/tmc/<scene_id>/`
   - `data/raw/ohrc/<strip_id>/`
   - `data/raw/nac_sldem/<tile_id>/`

2. Register newly added files in `data/manifest/data_manifest.yaml`:
   ```bash
   python scripts/build_manifest.py --path data/raw/tmc/<scene_id>/orthoimage.tif --instrument TMC --mission Chandrayaan-2 --source "ISRO PRADAN"
   ```

3. Run the preflight data integrity gate:
   ```bash
   python scripts/validate_provenance.py
   ```

---

## 4. Running the Pipeline

Once real data passes the preflight gate:
```bash
# Preprocess and detect overlaps
python -m src.ingestion.pipeline

# Train / Evaluate Super-Resolution
python -m src.sr_engine.train

# Extract hazards and fuse maps
python -m src.hazard_fusion.pipeline

# Search safe landing sites
python -m src.site_selection.search

# Validate against real OHRC ground truth
python -m src.validation.evaluate
```
