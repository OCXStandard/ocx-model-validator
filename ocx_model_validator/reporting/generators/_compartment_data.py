"""Compartment data extraction shared by the compartments and model-extent reports.

Builds JSON-ready compartment rows (tank type, COG, volume, extent) and the
conservative curve-point sampling used for bounding boxes.
"""
from __future__ import annotations

from typing import Any

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Ref
from ocx_model_validator.model.ir.structural import IrPanel, IrVessel
from ocx_model_validator.model.units import point_mm, qty_kpa, qty_m3, qty_mm

_NULL_EXTENT = {
    "min_x": None,
    "max_x": None,
    "min_y": None,
    "max_y": None,
    "min_z": None,
    "max_z": None,
}


def build_compartments_block(vessel: IrVessel) -> tuple[list[dict[str, Any]], list[str]]:
    """Build compartment JSON rows and non-fatal extraction warnings."""
    warnings: list[str] = []
    compartments = [
        _compartment_row(compartment, vessel, warnings)
        for compartment in vessel.compartments.values()
    ]
    return _round_floats(compartments), warnings


def _compartment_row(
    compartment: IrCompartment,
    vessel: IrVessel,
    warnings: list[str],
) -> dict[str, Any]:
    name = compartment.name or compartment.id
    return {
        "id": compartment.id,
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
            cog = (plate.mass_properties.moulded_cog
                   if plate is not None and plate.mass_properties is not None
                   else None)
            if cog is None:
                continue
            try:
                points.append(point_mm(cog, vessel.unit_registry))  # type: ignore[arg-type]
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
