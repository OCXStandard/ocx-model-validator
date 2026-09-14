"""Model extent report generator — bounding box over all parsed IR geometry.

Points are gathered from part COGs, stiffener/pillar traces, seam trace
lines and compartment face boundary curves. Unknown units degrade to notes.
"""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable
from ocx_model_validator.sections.document import _curve_points_mm
from ocx_model_validator.sections.units import point_mm

_TITLE = "Model extent report"

_PART_COLLECTIONS = ("plates", "stiffeners", "brackets", "pillars",
                     "edge_reinforcements", "seams")


def _gather_points(vessel: IrVessel, notes: list[str]) -> list[tuple[float, float, float]]:
    registry = vessel.unit_registry
    points: list[tuple[float, float, float]] = []

    def _add_curve(curve, label: str) -> None:
        if curve is None:
            return
        try:
            points.extend(_curve_points_mm(curve, registry))
        except GeometryError as exc:
            notes.append(f"{label}: {exc}")

    for attr in _PART_COLLECTIONS:
        for part in getattr(vessel, attr, {}).values():
            cog = getattr(part, "cog", None)
            if cog is not None:
                try:
                    points.append(point_mm(cog, registry))  # type: ignore[arg-type]
                except GeometryError as exc:
                    notes.append(f"{part.id} cog: {exc}")
            _add_curve(getattr(part, "trace", None), f"{part.id} trace")
            _add_curve(getattr(part, "trace_line", None), f"{part.id} trace line")

    for compartment in vessel.compartments.values():
        for curve in compartment.face_boundary_curves:
            _add_curve(curve, f"compartment {compartment.name or compartment.id}")

    return points


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    points = _gather_points(vessel, notes)

    rows: list[list[Cell]] = []
    if points:
        for axis, values in zip("xyz", zip(*points)):
            lo, hi = min(values), max(values)
            rows.append([axis, round(lo, 1), round(hi, 1), round(hi - lo, 1)])
    else:
        notes.append("Model extent unavailable; no geometry points found")

    notes[:] = list(dict.fromkeys(notes))
    section = ReportSection(
        title="Model extent",
        tables=[ReportTable("Bounding box",
                            ["Axis", "min (mm)", "max (mm)", "size (mm)"],
                            rows)],
        notes=notes,
    )
    return Report(title=_TITLE, metadata=report_metadata(vessel, source_file),
                  sections=[section])
