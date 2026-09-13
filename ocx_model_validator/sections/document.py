"""Build, save, and load lean Nauticus Hull cross-section JSON documents."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Ref
from ocx_model_validator.model.ir.structural import IrPanel, IrVessel
from ocx_model_validator.sections.frame_table import build_frame_table
from ocx_model_validator.sections.section_builder import build_cross_section
from ocx_model_validator.sections.units import point_mm, qty_m3

SCHEMA = "nh-cross-section/1"
_REQUIRED_TOP_LEVEL_KEYS = {"schema", "frame_table", "cross_section", "compartments"}
_NULL_EXTENT = {
    "min_x": None,
    "max_x": None,
    "min_y": None,
    "max_y": None,
    "min_z": None,
    "max_z": None,
}


def build_document(
    vessel: IrVessel,
    source_file: str,
    x_mm: float | None = None,
    frame: str | None = None,
) -> dict[str, Any]:
    """Build a cross-section JSON document for exactly one x-location or frame."""
    if (x_mm is None) == (frame is None):
        raise SectionError("Exactly one of x_mm or frame must be provided")

    frame_table = build_frame_table(vessel)
    section_frame: str | None
    if frame is not None:
        section_x_mm = frame_table.frame_to_x(frame)
        section_frame = frame
    else:
        assert x_mm is not None
        section_x_mm = x_mm
        nearest_label, nearest_x = frame_table.nearest_frame(x_mm)
        section_frame = nearest_label if abs(nearest_x - x_mm) <= 1.0 else None

    cross_section = build_cross_section(vessel, section_x_mm, frame=section_frame)
    compartments, compartment_warnings = build_compartments_block(vessel)
    warnings = [*frame_table.warnings, *cross_section.warnings, *compartment_warnings]

    doc = {
        "schema": SCHEMA,
        "source": {
            "file": str(source_file),
            "vessel_id": vessel.id,
            "generated": datetime.now(timezone.utc).isoformat(),
        },
        "frame_table": {
            "frame0_offset_mm": frame_table.frame0_offset_mm,
            "entries": [
                {"frame_no": label, "spacing_mm": spacing_mm}
                for label, spacing_mm in frame_table.entries
            ],
            "positions": [
                {"frame_no": label, "x_mm": position_x_mm}
                for label, position_x_mm in frame_table.positions
            ],
        },
        "cross_section": {
            "x_mm": cross_section.x_mm,
            "frame": cross_section.frame,
            "stiffeners": [_dataclass_dict(stiffener) for stiffener in cross_section.stiffeners],
            "plates": [_dataclass_dict(plate) for plate in cross_section.plates],
        },
        "compartments": compartments,
        "warnings": warnings,
    }
    return _round_floats(doc)


def build_compartments_block(vessel: IrVessel) -> tuple[list[dict[str, Any]], list[str]]:
    """Build compartment JSON rows and non-fatal extraction warnings."""
    warnings: list[str] = []
    compartments = [
        _compartment_row(compartment, vessel, warnings)
        for compartment in vessel.compartments.values()
    ]
    return _round_floats(compartments), warnings


def save_document(doc: dict[str, Any], path: str | Path) -> None:
    """Save a JSON document using deterministic human-readable formatting."""
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def load_document(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a cross-section JSON document."""
    with Path(path).open(encoding="utf-8") as f:
        doc = json.load(f)

    if not isinstance(doc, dict):
        raise SectionError("Document root must be a JSON object")
    missing = _REQUIRED_TOP_LEVEL_KEYS - set(doc)
    if missing:
        raise SectionError(f"Document is missing required top-level keys: {', '.join(sorted(missing))}")
    if doc["schema"] != SCHEMA:
        raise SectionError(f"Document schema must be {SCHEMA!r}")
    return doc


def _compartment_row(
    compartment: IrCompartment,
    vessel: IrVessel,
    warnings: list[str],
) -> dict[str, Any]:
    name = compartment.name or compartment.id
    return {
        "name": name,
        "tank_type": _tank_type(compartment, name, warnings),
        "cog_mm": _cog_mm(compartment.cog, vessel, name, warnings),
        "volume_m3": _volume_m3(compartment, vessel, name, warnings),
        "extent_mm": _extent_mm(compartment, vessel, name, warnings),
    }


def _tank_type(compartment: IrCompartment, name: str, warnings: list[str]) -> str:
    purpose = compartment.compartment_purpose
    if not purpose:
        warnings.append(f"compartment {name}: purpose is missing; using VOIDSPACE")
        return "VOIDSPACE"

    lowered = purpose.lower()
    if "void" in lowered:
        return "VOIDSPACE"
    if "ballast" in lowered:
        return "BALLASTWATERTANK"
    if "fuel" in lowered or "hfo" in lowered or "mdo" in lowered:
        return "FUELTANK"
    if "fresh" in lowered:
        return "FRESHWATERTANK"
    if "cargo" in lowered:
        return "CARGOHOLD"
    return purpose.upper()


def _cog_mm(
    cog: IrCog | None,
    vessel: IrVessel,
    name: str,
    warnings: list[str],
) -> list[float] | None:
    if cog is None:
        warnings.append(f"compartment {name}: cog is missing")
        return None
    try:
        return list(point_mm(cog, vessel.unit_registry))  # type: ignore[arg-type]
    except GeometryError as exc:
        warnings.append(f"compartment {name}: {exc}")
        return None


def _volume_m3(
    compartment: IrCompartment,
    vessel: IrVessel,
    name: str,
    warnings: list[str],
) -> float | None:
    try:
        return qty_m3(compartment.volume, vessel.unit_registry)
    except GeometryError as exc:
        warnings.append(f"compartment {name}: {exc}")
        return None


def _extent_mm(
    compartment: IrCompartment,
    vessel: IrVessel,
    name: str,
    warnings: list[str],
) -> dict[str, float | None]:
    panels = _referenced_panels(compartment.face_refs, vessel)
    if not panels:
        warnings.append(f"compartment {name}: extent unavailable; no face references matched panels")
        return dict(_NULL_EXTENT)

    points: list[tuple[float, float, float]] = []
    for panel in panels:
        for plate_id in panel.plate_ids:
            plate = vessel.plates.get(plate_id)
            if plate is None or plate.cog is None:
                continue
            try:
                points.append(point_mm(plate.cog, vessel.unit_registry))  # type: ignore[arg-type]
            except GeometryError as exc:
                warnings.append(f"compartment {name}: plate {plate.name or plate.id}: {exc}")

    if not points:
        warnings.append(f"compartment {name}: extent unavailable; no plate cogs found")
        return dict(_NULL_EXTENT)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "min_z": min(zs),
        "max_z": max(zs),
    }


def _referenced_panels(face_refs: list[Ref], vessel: IrVessel) -> list[IrPanel]:
    panels: list[IrPanel] = []
    seen: set[str] = set()
    for face_ref in face_refs:
        for panel in vessel.panels.values():
            if panel.id in seen:
                continue
            if face_ref.local_ref == panel.id or (
                face_ref.guidref is not None and face_ref.guidref == panel.guidref
            ):
                panels.append(panel)
                seen.add(panel.id)
    return panels


def _dataclass_dict(value: object) -> dict[str, Any]:
    if not is_dataclass(value):
        raise TypeError(f"Expected dataclass, got {type(value).__name__}")
    return asdict(value)


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_round_floats(item) for item in value)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    return value
