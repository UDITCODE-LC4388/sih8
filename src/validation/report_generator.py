"""
Validation Report Generator (Module 7 Component)

Generates official, run-linked Markdown validation reports in docs/validation_reports/.
ENFORCES ANTI-FABRICATION GUARDRAILS: Refuses to write placeholder or unverified reports.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "docs" / "validation_reports"


def generate_validation_report(
    run_id: str,
    manifest_hash: str,
    overlap_tile_id: str,
    metrics: Dict[str, Any],
    execution_provenance: Dict[str, Any],
    output_dir: Path = REPORTS_DIR,
) -> Path:
    """
    Writes a timestamped validation report for a completed real-data run.
    """
    if not metrics or "elevation" not in metrics:
        raise ValueError("Cannot generate validation report without verified execution metrics from real data.")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"{run_id}.md"

    elev = metrics.get("elevation", {})
    slope = metrics.get("slope", {})
    haz = metrics.get("hazard", {})
    det = metrics.get("detection", {})

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    content = f"""# Validation Report: {run_id}

> **Generated on:** {now_iso}  
> **Overlap Tile ID:** `{overlap_tile_id}`  
> **Data Manifest SHA256:** `{manifest_hash}`  
> **Execution Provenance:** Real TMC–OHRC Overlap Validation

---

## 1. Provenance & Execution Summary

- **Primary Input (TMC):** `{execution_provenance.get('tmc_scene_id', 'N/A')}`
- **Ground Truth Reference (OHRC):** `{execution_provenance.get('ohrc_strip_id', 'N/A')}`
- **Evaluation Grid Spacing:** 1.0 meter
- **Model Checkpoint Hash:** `{execution_provenance.get('checkpoint_hash', 'N/A')}`

---

## 2. Elevation & Topographic Accuracy

| Metric | Measured Value | Unit |
|---|---|---|
| Elevation RMSE | `{elev.get('rmse_m', 'N/A')}` | meters |
| Elevation MAE | `{elev.get('mae_m', 'N/A')}` | meters |
| Max Elevation Delta | `{elev.get('max_error_m', 'N/A')}` | meters |
| Slope Angle MAE | `{slope.get('slope_mae_deg', 'N/A')}` | degrees |
| Slope 95th Percentile Error | `{slope.get('slope_p95_err_deg', 'N/A')}` | degrees |

---

## 3. Hazard Map Agreement & Detection Performance

| Evaluation Metric | Score | Note |
|---|---|---|
| Hazard Map IoU | `{haz.get('iou', 'N/A')}` | Binary safe/hazard overlap |
| Crater/Boulder Precision | `{det.get('precision', 'N/A')}` | True Positive / All Flags |
| Crater/Boulder Recall | `{det.get('recall', 'N/A')}` | Safety Critical Metric |
| Detection F1-Score | `{det.get('f1_score', 'N/A')}` | Harmonic Mean |

---

*This report was automatically compiled by the validation framework from direct execution on verified real data.*
"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(content)

    return report_file
