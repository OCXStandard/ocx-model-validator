"""FastMCP server exposing OCX model cross-section tools."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ocx_model_validator import writeback
from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.mcp import state
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.parsers.parser import OcxParser
from ocx_model_validator.sections import (
    build_compartments_block,
    build_document,
    build_frame_table,
    frame_table_block,
    save_document,
)

mcp = FastMCP("ocx-mcp")


def _counts(vessel: IrVessel) -> dict[str, int]:
    return {
        "panels": len(vessel.panels),
        "plates": len(vessel.plates),
        "stiffeners": len(vessel.stiffeners),
        "compartments": len(vessel.compartments),
        "ref_planes": len(vessel.ref_planes),
        "materials": len(vessel.materials),
        "sections": len(vessel.sections),
    }


def _load_vessel(path: str) -> IrVessel:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    root = OcxParser().parse(source)
    schema_version = getattr(root, "schema_version", "unknown")
    return get_builder(schema_version).build(root)


def _require_model() -> IrVessel:
    if state.vessel is None:
        raise RuntimeError("No model loaded; call load_model first")
    return state.vessel


def _frame_table_dict(vessel: IrVessel) -> tuple[dict[str, Any], list[str]]:
    frame_table = build_frame_table(vessel)
    return (
        frame_table_block(frame_table),
        list(frame_table.warnings),
    )


@mcp.tool()
def load_model(path: str) -> dict[str, Any]:
    """Load and parse an OCX 3D ship model file. Must be called before any other tool."""
    try:
        vessel = _load_vessel(path)
        state.set_model(vessel, path)
        return {"ok": True, "vessel_id": vessel.id, "counts": _counts(vessel)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_model_info() -> dict[str, Any]:
    """Retrieve model ID, name, and entity counts (panels, plates, stiffeners, compartments, ref planes, materials, sections)."""
    try:
        vessel = _require_model()
        return {
            "ok": True,
            "vessel_id": vessel.id,
            "vessel_name": vessel.name,
            "counts": _counts(vessel),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_frame_table() -> dict[str, Any]:
    """Retrieve Nauticus frame table with labels, positions and spacings in mm derived from X reference planes. Requires load_model."""
    try:
        vessel = _require_model()
        frame_table, warnings = _frame_table_dict(vessel)
        return {"ok": True, "frame_table": frame_table, "warnings": warnings}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_compartments() -> dict[str, Any]:
    """Retrieve compartment list with tank type, center-of-gravity (mm), volume (m³), and extent (mm). Requires load_model."""
    try:
        vessel = _require_model()
        compartments, warnings = build_compartments_block(vessel)
        return {"ok": True, "compartments": compartments, "warnings": warnings}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def build_cross_section(
    x_mm: float | None = None,
    frame: str | None = None,
) -> dict[str, Any]:
    """Build cross-section JSON document at a transverse plane; provide exactly one of x_mm (mm) or frame (frame label string). Requires load_model."""
    try:
        vessel = _require_model()
        if state.source_file is None:
            raise RuntimeError("No source file recorded; call load_model first")
        doc = build_document(vessel, state.source_file, x_mm=x_mm, frame=frame)
        return {"ok": True, "document": doc}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def save_cross_section(
    path: str,
    x_mm: float | None = None,
    frame: str | None = None,
) -> dict[str, Any]:
    """Build and save the cross-section document to a JSON file path; provide exactly one of x_mm (mm) or frame (frame label string). Requires load_model."""
    try:
        vessel = _require_model()
        if state.source_file is None:
            raise RuntimeError("No source file recorded; call load_model first")
        doc = build_document(vessel, state.source_file, x_mm=x_mm, frame=frame)
        save_document(doc, path)
        return {"ok": True, "path": path}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def apply_scantlings(model_path: str, report_path: str,
                     output_path: str) -> dict[str, Any]:
    """Apply an nh-optimisation/1 report (from the nauticushull-mcp
    optimise_cross_section tool) to an OCX .3docx model. Patches plate
    thicknesses (max over each plate's EPP strips) and repoints stiffener
    SectionRefs to new BarSections with the optimised dimensions. Writes
    the patched model to output_path (must differ from model_path); never
    modifies the input. Returns counts of updated items and any unmatched
    report rows."""
    try:
        report = json.loads(
            Path(report_path).read_text(encoding="utf-8"))
        result = writeback.apply_report(model_path, report, output_path)
        return {"ok": True, **result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    mcp.run()
