"""Split cross-section plates into elementary plate panels (EPPs).

An EPP spans between two adjacent longitudinal stiffeners on the same panel
(or between a stiffener and the plate edge). See
docs/superpowers/specs/2026-09-16-epp-json-export-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.sections.section_builder import SectionPlate, SectionStiffener
from ocx_model_validator.sections.segment_math import (
    arc_length,
    point_at_station,
    project_point,
)


@dataclass(frozen=True)
class EppPlate:
    """One elementary plate panel segment in the section plane."""

    name: str
    y1_mm: float
    z1_mm: float
    y2_mm: float
    z2_mm: float
    thickness_mm: float | None
    material_reh_mpa: float | None
    panel: str | None
    radius_mm: float | None
    arc_center_y_mm: float | None
    arc_center_z_mm: float | None
    guidref: str | None
    bound_lower: str | None
    bound_upper: str | None
    breadth_mm: float
    function_type: str | None = None


def split_plates_to_epps(
    plates: list[SectionPlate],
    stiffeners: list[SectionStiffener],
    snap_tol: float = 5.0,
    end_tol: float = 1.0,
) -> list[EppPlate]:
    """Split every plate at same-panel stiffener stations into EPPs."""
    return [
        epp
        for plate in plates
        for epp in _split_plate(plate, stiffeners, snap_tol, end_tol)
    ]


def _split_plate(
    plate: SectionPlate,
    stiffeners: list[SectionStiffener],
    snap_tol: float,
    end_tol: float,
) -> list[EppPlate]:
    p1 = (plate.y1_mm, plate.z1_mm)
    p2 = (plate.y2_mm, plate.z2_mm)
    length = arc_length(plate, p1, p2)

    # (station, stiffener name) hits on this plate, sorted along it.
    hits: list[tuple[float, str]] = []
    for stiffener in stiffeners:
        if stiffener.panel != plate.panel:
            continue
        station, dist = project_point(plate, p1, p2, (stiffener.y_mm, stiffener.z_mm))
        if dist <= snap_tol:
            hits.append((station, stiffener.name))
    hits.sort(key=lambda hit: hit[0])

    # Stiffeners sitting on a plate end bound the outermost EPP but never split.
    bound_start = next((name for st, name in hits if st <= end_tol), None)
    bound_end = next(
        (name for st, name in reversed(hits) if st >= length - end_tol), None
    )

    interior: list[tuple[float, str]] = []
    for station, name in hits:
        if station <= end_tol or station >= length - end_tol:
            continue
        if interior and station - interior[-1][0] <= end_tol:
            continue  # coincident stations collapse; first stiffener name wins
        interior.append((station, name))

    stations = [0.0, *(st for st, _ in interior), length]
    bounds = [bound_start, *(name for _, name in interior), bound_end]
    points = [point_at_station(plate, p1, p2, st) for st in stations]
    points[0] = p1
    points[-1] = p2

    return [
        EppPlate(
            name=f"{plate.name}_EPP{index + 1}",
            y1_mm=points[index][0],
            z1_mm=points[index][1],
            y2_mm=points[index + 1][0],
            z2_mm=points[index + 1][1],
            thickness_mm=plate.thickness_mm,
            material_reh_mpa=plate.material_reh_mpa,
            panel=plate.panel,
            radius_mm=plate.radius_mm,
            arc_center_y_mm=plate.arc_center_y_mm,
            arc_center_z_mm=plate.arc_center_z_mm,
            guidref=plate.guidref,
            bound_lower=bounds[index],
            bound_upper=bounds[index + 1],
            breadth_mm=stations[index + 1] - stations[index],
            function_type=plate.function_type,
        )
        for index in range(len(stations) - 1)
    ]
