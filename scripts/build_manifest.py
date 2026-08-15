#!/usr/bin/env python3
"""
Manifest Builder Helper Script (Section 3.3 of SIH260008 Master Brief)

Registers newly dropped real ISRO/NASA files into data/manifest/data_manifest.yaml,
calculating SHA256 cryptographic checksums automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest" / "data_manifest.yaml"


def compute_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest().lower()


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> Dict[str, Any]:
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        return {"version": "1.0", "records": []}
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "records" not in data or data["records"] is None:
        data["records"] = []
    if "version" not in data:
        data["version"] = "1.0"
    return data


def save_manifest(data: Dict[str, Any], manifest_path: Path = MANIFEST_PATH) -> None:
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False, indent=2)


def register_file(
    file_path: Path,
    instrument: str,
    mission: str,
    source_archive: str,
    record_id: Optional[str] = None,
    acquisition_date: Optional[str] = None,
    sun_elevation_deg: Optional[float] = None,
    sun_azimuth_deg: Optional[float] = None,
    license_or_terms: Optional[str] = "ISRO Open Data Policy",
    notes: str = "",
    manifest_path: Path = MANIFEST_PATH,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Register a single real file into the manifest."""
    abs_path = file_path.resolve()
    if not abs_path.exists() or not abs_path.is_file():
        raise FileNotFoundError(f"Target file does not exist: {file_path}")

    root = project_root or PROJECT_ROOT
    if project_root is None and not abs_path.is_relative_to(root):
        root = manifest_path.parent.parent.resolve()

    # Compute relative path from project root
    try:
        rel_path = str(abs_path.relative_to(root).as_posix())
    except ValueError:
        raise ValueError(f"File {file_path} must be inside project workspace ({root})")

    sha256_hash = compute_sha256(abs_path)
    rec_id = record_id or f"{instrument.lower()}_{abs_path.stem}"

    manifest_data = load_manifest(manifest_path)
    records: List[Dict[str, Any]] = manifest_data.get("records", [])

    # Check if path or id already exists
    existing_idx = None
    for idx, r in enumerate(records):
        if r.get("path") == rel_path or r.get("id") == rec_id:
            existing_idx = idx
            break

    new_record: Dict[str, Any] = {
        "id": rec_id,
        "instrument": instrument,
        "mission": mission,
        "path": rel_path,
        "source_archive": source_archive,
        "checksum_sha256": sha256_hash,
        "acquisition_date": acquisition_date,
        "sun_elevation_deg": sun_elevation_deg,
        "sun_azimuth_deg": sun_azimuth_deg,
        "license_or_terms": license_or_terms,
        "provided_by_user": True,
        "notes": notes,
    }

    if existing_idx is not None:
        records[existing_idx] = new_record
        print(f"Updated existing manifest record: {rec_id} ({rel_path})")
    else:
        records.append(new_record)
        print(f"Added new manifest record: {rec_id} ({rel_path})")

    manifest_data["records"] = records
    save_manifest(manifest_data, manifest_path)
    return new_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a real data file in data_manifest.yaml")
    parser.add_argument("--path", required=True, type=str, help="Path to the real file inside data/raw/")
    parser.add_argument("--instrument", required=True, choices=["TMC", "OHRC", "NAC_SLDEM", "NAC", "SLDEM"], help="Sensor instrument")
    parser.add_argument("--mission", required=True, choices=["Chandrayaan-1", "Chandrayaan-2", "LRO"], help="Spacecraft mission")
    parser.add_argument("--source", required=True, help="Source archive (e.g. 'ISRO PRADAN/ISSDC', 'NASA PDS')")
    parser.add_argument("--id", type=str, default=None, help="Optional unique record identifier")
    parser.add_argument("--date", type=str, default=None, help="Acquisition date (YYYY-MM-DD)")
    parser.add_argument("--sun-elevation", type=float, default=None, help="Sun elevation in degrees")
    parser.add_argument("--sun-azimuth", type=float, default=None, help="Sun azimuth in degrees")
    parser.add_argument("--license", type=str, default="ISRO Open Data Policy", help="Terms or license")
    parser.add_argument("--notes", type=str, default="", help="Additional provenance notes")

    args = parser.parse_args()

    try:
        register_file(
            file_path=Path(args.path),
            instrument=args.instrument,
            mission=args.mission,
            source_archive=args.source,
            record_id=args.id,
            acquisition_date=args.date,
            sun_elevation_deg=args.sun_elevation,
            sun_azimuth_deg=args.sun_azimuth,
            license_or_terms=args.license,
            notes=args.notes,
        )
        return 0
    except Exception as e:
        print(f"Error registering manifest record: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
