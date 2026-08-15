#!/usr/bin/env python3
"""
Preflight Data-Integrity Gate (Section 3.4 of SIH260008 Master Brief)
Enforces the PRIME DIRECTIVE: Real data only.

Walks data/raw/, verifies every file is listed in data/manifest/data_manifest.yaml,
checks SHA256 checksums, and ensures complete provenance before any pipeline stage runs.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Resolve root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest" / "data_manifest.yaml"


class ProvenanceError(Exception):
    """Raised when data integrity or provenance validation fails."""
    pass


class DataGapError(Exception):
    """Raised when required real datasets are missing for a requested pipeline stage."""
    pass


@dataclass
class ManifestRecord:
    id: str
    instrument: str
    mission: str
    path: str
    source_archive: str
    checksum_sha256: str
    acquisition_date: Optional[str] = None
    sun_elevation_deg: Optional[float] = None
    sun_azimuth_deg: Optional[float] = None
    license_or_terms: Optional[str] = None
    provided_by_user: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ManifestRecord:
        return cls(
            id=str(data.get("id", "")),
            instrument=str(data.get("instrument", "")),
            mission=str(data.get("mission", "")),
            path=str(data.get("path", "")),
            source_archive=str(data.get("source_archive", "")),
            checksum_sha256=str(data.get("checksum_sha256", "")).strip().lower(),
            acquisition_date=data.get("acquisition_date"),
            sun_elevation_deg=data.get("sun_elevation_deg"),
            sun_azimuth_deg=data.get("sun_azimuth_deg"),
            license_or_terms=data.get("license_or_terms"),
            provided_by_user=bool(data.get("provided_by_user", True)),
            notes=str(data.get("notes", "")),
        )


def compute_sha256(file_path: Path, block_size: int = 65536) -> str:
    """Compute the SHA256 hex digest of a file in chunks."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest().lower()


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> Tuple[List[ManifestRecord], Dict[str, Any]]:
    """Load and parse the data manifest YAML file."""
    if not manifest_path.exists():
        raise ProvenanceError(f"Manifest file not found at: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_records = data.get("records", [])
    records = [ManifestRecord.from_dict(r) for r in raw_records]
    return records, data


def collect_raw_files(raw_dir: Path = RAW_DATA_DIR) -> List[Path]:
    """Walk data/raw/ to find all primary science raster and data files."""
    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        return []

    valid_extensions = {".img", ".tif", ".tiff", ".cub", ".dtm", ".oth"}
    files = []
    for root, _, filenames in os.walk(raw_dir):
        for fname in filenames:
            if fname.startswith(".") or fname.endswith("~") or fname == ".gitkeep":
                continue
            p = Path(root) / fname
            if p.suffix.lower() in valid_extensions:
                files.append(p)
    return sorted(files)


def validate_provenance_gate(
    raw_dir: Path = RAW_DATA_DIR,
    manifest_path: Path = MANIFEST_PATH,
    stage_requirement: Optional[str] = None,
    raise_on_error: bool = True,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Core verification function enforcing the data provenance gate.
    
    Returns a dictionary summarizing verification status.
    Raises ProvenanceError or DataGapError if raise_on_error is True and issues are found.
    """
    records, manifest_meta = load_manifest(manifest_path)
    disk_files = collect_raw_files(raw_dir)
    root = project_root or PROJECT_ROOT
    if project_root is None and disk_files and not disk_files[0].is_relative_to(root):
        root = raw_dir.parent.parent.resolve()

    # Map manifest records by normalized relative path
    manifest_by_rel_path: Dict[str, ManifestRecord] = {}
    for r in records:
        # Normalize relative path to project root
        rel_p = str(Path(r.path).as_posix()).lstrip("./")
        manifest_by_rel_path[rel_p] = r

    unmanifested_files: List[Path] = []
    checksum_mismatches: List[Tuple[Path, str, str]] = []
    missing_manifested_files: List[str] = []
    verified_files: List[Tuple[Path, ManifestRecord]] = []

    seen_rel_paths: Set[str] = set()

    for file_path in disk_files:
        try:
            rel_path_str = str(file_path.relative_to(root).as_posix())
        except ValueError:
            rel_path_str = str(file_path.name)
        seen_rel_paths.add(rel_path_str)

        if rel_path_str not in manifest_by_rel_path:
            unmanifested_files.append(file_path)
        else:
            rec = manifest_by_rel_path[rel_path_str]
            actual_checksum = compute_sha256(file_path)
            expected_checksum = rec.checksum_sha256
            if actual_checksum != expected_checksum:
                checksum_mismatches.append((file_path, expected_checksum, actual_checksum))
            else:
                verified_files.append((file_path, rec))

    for rel_p, rec in manifest_by_rel_path.items():
        if rel_p not in seen_rel_paths:
            missing_manifested_files.append(rel_p)

    # Check stage prerequisites
    instruments_present = {rec.instrument.upper() for _, rec in verified_files}
    tmc_present = "TMC" in instruments_present
    ohrc_present = "OHRC" in instruments_present
    nac_present = "NAC_SLDEM" in instruments_present or "NAC" in instruments_present or "SLDEM" in instruments_present

    data_gap_messages: List[str] = []
    if stage_requirement == "ingestion" and not tmc_present:
        data_gap_messages.append("DATA_GAP [Module 1 Ingestion]: At least one real TMC scene (orthoimage + DEM) is required.")
    elif stage_requirement == "sr_training" and not (tmc_present and ohrc_present):
        data_gap_messages.append("DATA_GAP [Module 2 SR Training]: Real paired TMC + OHRC overlap scenes are required for supervised training.")
    elif stage_requirement == "validation" and not (tmc_present and ohrc_present):
        data_gap_messages.append("DATA_GAP [Module 7 Validation]: Real OHRC ground truth overlap scenes are required for independent validation.")

    has_hard_error = len(unmanifested_files) > 0 or len(checksum_mismatches) > 0

    def safe_rel(p: Path) -> str:
        try:
            return str(p.relative_to(root).as_posix())
        except ValueError:
            return str(p.as_posix())

    report = {
        "status": "FAILED" if has_hard_error else ("DATA_GAP" if data_gap_messages else "PASSED"),
        "total_disk_files": len(disk_files),
        "total_manifest_records": len(records),
        "verified_files_count": len(verified_files),
        "unmanifested_files": [safe_rel(f) for f in unmanifested_files],
        "checksum_mismatches": [
            {
                "file": safe_rel(f),
                "expected": exp,
                "actual": act,
            }
            for f, exp, act in checksum_mismatches
        ],
        "missing_manifested_files": missing_manifested_files,
        "instruments_present": sorted(list(instruments_present)),
        "data_gaps": data_gap_messages,
    }

    if raise_on_error:
        if unmanifested_files:
            raise ProvenanceError(
                f"Unmanifested files found in data/raw/: {[safe_rel(f) for f in unmanifested_files]}. "
                f"Every raw file must be registered in the manifest."
            )
        if checksum_mismatches:
            raise ProvenanceError(
                f"SHA256 checksum mismatch for files: {[safe_rel(f) for f, _, _ in checksum_mismatches]}."
            )
        if data_gap_messages:
            raise DataGapError("\n".join(data_gap_messages))

    return report


def print_report(report: Dict[str, Any]) -> None:
    """Print a clean CLI summary of the preflight validation gate."""
    print("=" * 72)
    print(" LUNAR HAZARD-MAP SUPER-RESOLUTION SYSTEM: DATA PROVENANCE GATE")
    print("=" * 72)
    print(f"Status:                      {report['status']}")
    print(f"Files found in data/raw/:    {report['total_disk_files']}")
    print(f"Records in manifest:         {report['total_manifest_records']}")
    print(f"Verified files with SHA256:  {report['verified_files_count']}")
    print(f"Instruments present:         {', '.join(report['instruments_present']) or 'None'}")
    print("-" * 72)

    if report["unmanifested_files"]:
        print("❌ UNMANIFESTED RAW FILES (Hard Failure):")
        for f in report["unmanifested_files"]:
            print(f"  - {f}")
        print("  Action: Register these files using scripts/build_manifest.py")
        print("-" * 72)

    if report["checksum_mismatches"]:
        print("❌ CHECKSUM MISMATCHES (Integrity Failure):")
        for item in report["checksum_mismatches"]:
            print(f"  - File:     {item['file']}")
            print(f"    Expected: {item['expected']}")
            print(f"    Actual:   {item['actual']}")
        print("-" * 72)

    if report["missing_manifested_files"]:
        print("⚠️  MISSING FILES (Registered in manifest but not found on disk):")
        for f in report["missing_manifested_files"]:
            print(f"  - {f}")
        print("-" * 72)

    if report["data_gaps"]:
        print("⚠️  DATA GAP REPORT:")
        for gap in report["data_gaps"]:
            print(f"  - {gap}")
        print("-" * 72)

    if report["status"] == "PASSED":
        if report["verified_files_count"] == 0:
            print("ℹ️  No raw data files dropped yet. System is ready to receive real data.")
        else:
            print("✅ PREFLIGHT DATA INTEGRITY CHECK PASSED. All data verifiable.")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight Data Provenance and Integrity Gate")
    parser.add_argument("--stage", choices=["ingestion", "sr_training", "validation"], default=None,
                        help="Optional stage requirement to check for data completeness")
    parser.add_argument("--allow-gap", action="store_true", help="Do not exit with error code if data gaps exist")
    args = parser.parse_args()

    try:
        report = validate_provenance_gate(
            stage_requirement=args.stage,
            raise_on_error=False
        )
        print_report(report)

        if report["unmanifested_files"] or report["checksum_mismatches"]:
            return 1
        if report["data_gaps"] and not args.allow_gap:
            return 2
        return 0
    except Exception as e:
        print(f"Fatal validation error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
