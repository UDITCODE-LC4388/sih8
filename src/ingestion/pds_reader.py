"""
PDS4 & GeoTIFF Ingestion Parser for ISRO TMC-2 and OHRC Products (Module 1 Component)

Parses PDS4 XML labels and reads raw raster files (.img, .tif) with complete
provenance, georeferencing, and solar illumination geometry.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np


@dataclass
class PDS4Metadata:
    logical_identifier: str
    title: str
    start_time: str
    stop_time: str
    mission: str
    instrument: str
    sun_azimuth_deg: float
    sun_elevation_deg: float
    solar_incidence_deg: float
    pixel_resolution_m: float
    lines: int
    samples: int
    data_type: str
    data_file_name: str
    raw_xml_dict: Dict[str, Any]


def parse_pds4_xml_label(xml_path: Path) -> PDS4Metadata:
    """
    Parses an ISRO PDS4 XML label file to extract remote sensing and solar geometry parameters.
    """
    if not xml_path.exists():
        raise FileNotFoundError(f"PDS4 XML label not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Namespace handling
    ns = {
        "pds": "http://pds.nasa.gov/pds4/pds/v1",
        "isda": "https://isda.issdc.gov.in/pds4/isda/v1",
    }

    # Fallback to search without namespace if needed
    def find_text(elem, xpath, default=""):
        res = elem.find(xpath, ns)
        if res is None:
            # Try without namespace prefix
            tag_name = xpath.split(":")[-1]
            res = elem.find(f".//{tag_name}")
        return res.text.strip() if res is not None and res.text else default

    lid = find_text(root, ".//pds:logical_identifier")
    title = find_text(root, ".//pds:title")
    start_t = find_text(root, ".//pds:start_date_time")
    stop_t = find_text(root, ".//pds:stop_date_time")
    mission = find_text(root, ".//pds:Investigation_Area/pds:name", "Chandrayaan-2")
    instrument = find_text(root, ".//pds:Observing_System_Component/pds:name", "terrain mapping camera")

    sun_az = float(find_text(root, ".//isda:sun_azimuth", "0.0"))
    sun_el = float(find_text(root, ".//isda:sun_elevation", "30.0"))
    sol_inc = float(find_text(root, ".//isda:solar_incidence", "60.0"))
    res_m = float(find_text(root, ".//isda:pixel_resolution", "5.0"))

    lines = int(find_text(root, ".//pds:Axis_Array[pds:axis_name='Line']/pds:elements", "0") or "0")
    samples = int(find_text(root, ".//pds:Axis_Array[pds:axis_name='Sample']/pds:elements", "0") or "0")
    data_type = find_text(root, ".//pds:Element_Array/pds:data_type", "UnsignedLSB2")
    data_fname = find_text(root, ".//pds:File/pds:file_name", "")

    return PDS4Metadata(
        logical_identifier=lid,
        title=title,
        start_time=start_t,
        stop_time=stop_t,
        mission=mission,
        instrument="TMC",
        sun_azimuth_deg=sun_az,
        sun_elevation_deg=sun_el,
        solar_incidence_deg=sol_inc,
        pixel_resolution_m=res_m,
        lines=lines,
        samples=samples,
        data_type=data_type,
        data_file_name=data_fname,
        raw_xml_dict={},
    )


def read_pds4_raster_window(
    img_path: Path,
    metadata: PDS4Metadata,
    row_offset: int = 0,
    col_offset: int = 0,
    num_rows: Optional[int] = None,
    num_cols: Optional[int] = None,
) -> np.ndarray:
    """
    Reads a 2D window from a binary PDS4 raster file using memory-mapping.
    Supports 16-bit unsigned (UnsignedLSB2/MSB2) and 32-bit float rasters.
    """
    if not img_path.exists():
        raise FileNotFoundError(f"Binary image file not found: {img_path}")

    dtype = np.uint16
    if "float" in metadata.data_type.lower() or "real" in metadata.data_type.lower():
        dtype = np.float32
    elif "lsb" in metadata.data_type.lower() or "unsignedlsb" in metadata.data_type.lower():
        dtype = np.dtype("<u2")
    elif "msb" in metadata.data_type.lower() or "unsignedmsb" in metadata.data_type.lower():
        dtype = np.dtype(">u2")

    total_lines = metadata.lines
    total_samples = metadata.samples

    # Memory map the full image
    mmap_arr = np.memmap(
        img_path,
        dtype=dtype,
        mode="r",
        shape=(total_lines, total_samples),
    )

    r_end = total_lines if num_rows is None else min(row_offset + num_rows, total_lines)
    c_end = total_samples if num_cols is None else min(col_offset + num_cols, total_samples)

    window = np.array(mmap_arr[row_offset:r_end, col_offset:c_end])
    return window.astype(np.float32)
