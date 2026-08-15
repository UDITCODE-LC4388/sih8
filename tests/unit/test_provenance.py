"""
Unit tests for data provenance preflight gate and manifest builder.
"""

import tempfile
from pathlib import Path
import pytest
import yaml

from scripts.validate_provenance import (
    compute_sha256,
    load_manifest,
    validate_provenance_gate,
    ProvenanceError,
    DataGapError,
)
from scripts.build_manifest import register_file


def test_sha256_computation(tmp_path: Path):
    test_file = tmp_path / "test_sample.bin"
    test_file.write_bytes(b"ISRO_CHANDRAYAAN_TMC_DATA")
    checksum = compute_sha256(test_file)
    assert len(checksum) == 64
    assert checksum.isalnum()


def test_manifest_validation_pass(tmp_path: Path):
    raw_dir = tmp_path / "data" / "raw" / "tmc"
    raw_dir.mkdir(parents=True)
    sample_file = raw_dir / "ortho.tif"
    sample_file.write_bytes(b"LUNAR_ORTHO_REAL_BYTES")

    manifest_file = tmp_path / "data" / "manifest" / "data_manifest.yaml"
    register_file(
        file_path=sample_file,
        instrument="TMC",
        mission="Chandrayaan-2",
        source_archive="ISRO PRADAN",
        manifest_path=manifest_file,
        project_root=tmp_path,
    )

    report = validate_provenance_gate(
        raw_dir=raw_dir,
        manifest_path=manifest_file,
        project_root=tmp_path,
        raise_on_error=True,
    )
    assert report["status"] == "PASSED"
    assert report["verified_files_count"] == 1


def test_unmanifested_file_hard_failure(tmp_path: Path):
    raw_dir = tmp_path / "data" / "raw" / "tmc"
    raw_dir.mkdir(parents=True)
    sample_file = raw_dir / "unregistered.tif"
    sample_file.write_bytes(b"UNREGISTERED_DATA")

    manifest_file = tmp_path / "data" / "manifest" / "data_manifest.yaml"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text("version: '1.0'\nrecords: []\n")

    with pytest.raises(ProvenanceError):
        validate_provenance_gate(
            raw_dir=raw_dir,
            manifest_path=manifest_file,
            project_root=tmp_path,
            raise_on_error=True,
        )
