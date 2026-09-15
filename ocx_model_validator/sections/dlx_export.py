"""Nauticus Hull 2DLX (CROSS_SECTION) cross-section export.

Reuses the shared section-body builders from ``hmx_export``; see the
design spec ``docs/superpowers/specs/2026-09-15-2dlx-export-design.md``
for the OCX -> 2DLX profile type map and content deltas versus HMX.
"""
from __future__ import annotations

from datetime import datetime
from importlib import metadata
from pathlib import Path

from lxml import etree

from ocx_model_validator.reporting.generators.model_extent import extent_mm
from ocx_model_validator.sections.hmx_export import (
    _LSTIFF_TYPE,
    _MaterialIds,
    _append_section_body,
    _register_section_materials,
    _write_pretty_xml,
    _xml_comment_text,
)
from ocx_model_validator.sections.section_builder import CrossSection

# 2DLX only recognizes LSTIFF Type codes 10, 20-29, 30, 31, 33, 35, 36,
# 37, 42 and 43 (docs/superpowers/ProfileTypesEnum.cs, trailing comment
# block). Notably the HMX BuiltUpTbar code 40 is invalid here: T-bars
# map to 43 (Welded T-bar).
_LSTIFF_TYPE_2DLX = {**_LSTIFF_TYPE, "t_section": 43}

# Locale-independent month names for the schema-documented date format
# (e.g. 15-Feb-2013).
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def build_2dlx(
    vessel,
    cross_section: CrossSection,
    frame_table,
) -> etree._Element:
    """Build a standalone Nauticus Hull 2DLX CROSS_SECTION document.

    Mirrors the HMX Scantling body but omits the HMX-only SEGMENT
    compartment refs, and carries materials in a GlobalData/Materials
    table referenced by PLATE/LSTIFF MaterialId attributes (matching
    Nauticus Hull's own 2DLX exports).
    """
    warnings = [*getattr(frame_table, "warnings", []), *cross_section.warnings]
    if not cross_section.plates:
        raise ValueError("2DLX export requires at least one plate")
    extent = extent_mm(vessel)
    materials = _MaterialIds()
    _register_section_materials(cross_section, materials)

    root = etree.Element("CROSS_SECTION")
    root.append(_administrative())
    _append_section_body(
        root,
        vessel,
        cross_section,
        frame_table,
        extent,
        comp_boxes=None,
        materials=materials,
        warnings=warnings,
        lstiff_types=_LSTIFF_TYPE_2DLX,
        global_materials=True,
    )

    if warnings:
        root.insert(
            0,
            etree.Comment(_xml_comment_text("warnings: " + "; ".join(dict.fromkeys(warnings)))),
        )
    return root


def save_2dlx(root: etree._Element, path: str | Path) -> None:
    """Save a 2DLX XML document with declaration and stable pretty printing."""
    _write_pretty_xml(root, path)


def _administrative() -> etree._Element:
    try:
        version = metadata.version("ocx-model-validator")
    except metadata.PackageNotFoundError:
        version = "unknown"
    administrative = etree.Element("administrative")
    etree.SubElement(
        administrative,
        "program",
        name="ocx-model-validator",
        version=version,
    )
    now = datetime.now()
    # schema-documented formats: 15-Feb-2013 / 14:50:59
    etree.SubElement(
        administrative,
        "session_info",
        date=f"{now.day:02d}-{_MONTHS[now.month - 1]}-{now.year}",
        time=now.strftime("%H:%M:%S"),
    )
    return administrative
