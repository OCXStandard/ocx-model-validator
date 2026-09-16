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
from ocx_model_validator.sections.epp import split_plates_to_epps
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table
from ocx_model_validator.sections.section_builder import CrossSection, build_cross_section
from ocx_model_validator.sections.units import point_mm, qty_kpa, qty_m3, qty_mm

SCHEMA = "nh-cross-section/2"
_REQUIRED_TOP_LEVEL_KEYS = {"schema", "frame_table", "cross_section", "compartments"}
_NULL_EXTENT = {
    "min_x": None,
    "max_x": None,
    "min_y": None,
    "max_y": None,
    "min_z": None,
    "max_z": None,
}


def resolve_section(
    vessel: IrVessel,
    x_mm: float | None = None,
    frame: str | None = None,
) -> tuple[FrameTable, CrossSection]:
    """Resolve a frame/x-position to a FrameTable and CrossSection for one vessel location."""
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
    return frame_table, cross_section


def build_document(
    vessel: IrVessel,
    source_file: str,
    x_mm: float | None = None,
    frame: str | None = None,
) -> dict[str, Any]:
    """Build a cross-section JSON document for exactly one x-location or frame."""
    frame_table, cross_section = resolve_section(vessel, x_mm=x_mm, frame=frame)
    compartments, compartment_warnings = build_compartments_block(vessel)
    warnings = [*frame_table.warnings, *cross_section.warnings, *compartment_warnings]

    doc = {
        "schema": SCHEMA,
        "source": {
            "file": str(source_file),
            "vessel_id": vessel.id,
            "generated": datetime.now(timezone.utc).isoformat(),
        },
        "frame_table": frame_table_block(frame_table),
        "cross_section": {
            "x_mm": cross_section.x_mm,
            "frame": cross_section.frame,
            "stiffeners": [_dataclass_dict(stiffener) for stiffener in cross_section.stiffeners],
            "plates": [
                _dataclass_dict(epp)
                for epp in split_plates_to_epps(
                    cross_section.plates, cross_section.stiffeners
                )
            ],
            "seams": [_dataclass_dict(seam) for seam in cross_section.seams],
        },
        "compartments": compartments,
        "warnings": warnings,
    }
    return _round_floats(doc)


def frame_table_block(ft: FrameTable) -> dict[str, Any]:
    """Serialize a FrameTable into JSON-ready dict format."""
    return {
        "frame0_offset_mm": ft.frame0_offset_mm,
        "entries": [
            {"frame_no": frame_no, "spacing_mm": spacing_mm}
            for frame_no, spacing_mm in ft.entries
        ],
        "positions": [
            {"frame_no": frame_no, "x_mm": x_mm}
            for frame_no, x_mm in ft.positions
        ],
    }


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
        "filling_height_mm": _safe_qty(qty_mm, compartment.filling_height, vessel, name, warnings),
        "air_pipe_height_mm": _safe_qty(qty_mm, compartment.air_pipe_height, vessel, name, warnings),
        "relief_valve_pressure_kpa": _safe_qty(qty_kpa, compartment.relief_valve_pressure, vessel, name, warnings),
    }


def _safe_qty(convert, qty, vessel: IrVessel, name: str, warnings: list[str]) -> float | None:
    if qty is None:
        return None
    try:
        return convert(qty, vessel.unit_registry)
    except GeometryError as exc:
        warnings.append(f"compartment {name}: {exc}")
        return None


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
    if compartment.volume is None:
        warnings.append(f"compartment {name}: volume is missing")
        return None
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
    # Preferred: bounding box over the face boundary curves of all faces
    points = _boundary_points_mm(compartment, vessel, name, warnings)

    if not points:
        # Fallback: plate COGs of panels matched via face references
        points = _panel_cog_points_mm(compartment, vessel, name, warnings)

    if not points:
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


def _boundary_points_mm(
    compartment: IrCompartment,
    vessel: IrVessel,
    name: str,
    warnings: list[str],
) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for curve in compartment.face_boundary_curves:
        try:
            points.extend(_curve_points_mm(curve, vessel.unit_registry))
        except GeometryError as exc:
            warnings.append(f"compartment {name}: face boundary curve: {exc}")
    return points


def _curve_points_mm(curve, registry) -> list[tuple[float, float, float]]:
    """Return points in mm bounding a boundary curve (conservative superset)."""
    points: list[tuple[float, float, float]] = []

    for attr in ("start", "intermediate", "end"):
        p = getattr(curve, attr, None)
        if p is not None:
            points.append(point_mm(p, registry))
    for p in getattr(curve, "vertices", None) or []:
        if p is not None:
            points.append(point_mm(p, registry))
    for p in getattr(curve, "control_points", None) or []:
        if p is not None:
            points.append(point_mm(p, registry))
    for segment in getattr(curve, "segments", None) or []:
        points.extend(_curve_points_mm(segment, registry))

    # Circles/ellipses: center +/- radius in every axis (axis-aligned superset)
    center = getattr(curve, "center", None)
    if center is not None:
        cx, cy, cz = point_mm(center, registry)
        diameter = (getattr(curve, "diameter", None)
                    or getattr(curve, "major_diameter", None))
        r = (qty_mm(diameter, registry) or 0.0) / 2.0
        points.append((cx - r, cy - r, cz - r))
        points.append((cx + r, cy + r, cz + r))

    return points


def _panel_cog_points_mm(
    compartment: IrCompartment,
    vessel: IrVessel,
    name: str,
    warnings: list[str],
) -> list[tuple[float, float, float]]:
    panels = _referenced_panels(compartment.face_refs, vessel)
    if not panels:
        warnings.append(f"compartment {name}: extent unavailable; no face references matched panels")
        return []

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
    return points


def _referenced_panels(face_refs: list[Ref], vessel: IrVessel) -> list[IrPanel]:
    by_guid = {
        panel.guidref: panel for panel in vessel.panels.values() if panel.guidref is not None
    }
    panels: list[IrPanel] = []
    seen: set[str] = set()
    for face_ref in face_refs:
        panel = vessel.panels.get(face_ref.local_ref)
        if panel is None and face_ref.guidref is not None:
            panel = by_guid.get(face_ref.guidref)
        if panel is not None and panel.id not in seen:
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
