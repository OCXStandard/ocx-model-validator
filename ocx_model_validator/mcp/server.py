"""FastMCP server exposing OCX model cross-section tools."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

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
    try:
        vessel = _load_vessel(path)
        state.set_model(vessel, path)
        return {"ok": True, "vessel_id": vessel.id, "counts": _counts(vessel)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_model_info() -> dict[str, Any]:
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
    try:
        vessel = _require_model()
        frame_table, warnings = _frame_table_dict(vessel)
        return {"ok": True, "frame_table": frame_table, "warnings": warnings}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_compartments() -> dict[str, Any]:
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
    try:
        vessel = _require_model()
        if state.source_file is None:
            raise RuntimeError("No source file recorded; call load_model first")
        doc = build_document(vessel, state.source_file, x_mm=x_mm, frame=frame)
        save_document(doc, path)
        return {"ok": True, "path": path}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    mcp.run()
