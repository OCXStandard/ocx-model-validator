"""Assemble transverse cross-section inputs from the schema-neutral IR."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import hypot
from typing import Iterable

import numpy as np

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.model.ir.base import IrUnit, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCurve3D,
)
from ocx_model_validator.model.ir.sections import (
    IrBulbFlatSection,
    IrFlatBarSection,
    IrLSection,
    IrLSectionOvershootFlange,
    IrLSectionOvershootWeb,
    IrSection,
    IrTSection,
)
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener, IrVessel
from ocx_model_validator.sections.geometry import (
    _circle_from_three_points,
    intersect_curve_plane,
    trace_profile,
)
from ocx_model_validator.sections.units import point_mm, qty_mm, qty_mpa


@dataclass(frozen=True)
class SectionStiffener:
    name: str
    y_mm: float
    z_mm: float
    panel: str | None
    profile_type: str | None
    profile_dimensions: str | None
    material_reh_mpa: float | None
    spacing_mm: float | None
    section_kind: str | None = None
    h_mm: float | None = None
    bf_mm: float | None = None
    tw_mm: float | None = None
    tf_mm: float | None = None
    orientation: str = "Longitudinal"
    web_angle_deg: float = 90.0
    web_dir_y: float | None = None
    web_dir_z: float | None = None


@dataclass(frozen=True)
class SectionPlate:
    name: str
    y1_mm: float
    z1_mm: float
    y2_mm: float
    z2_mm: float
    thickness_mm: float | None
    material_reh_mpa: float | None
    panel: str | None
    radius_mm: float | None = None
    arc_center_y_mm: float | None = None
    arc_center_z_mm: float | None = None


@dataclass(frozen=True)
class SectionSeam:
    """A panel seam's intersection with the section plane."""
    name: str | None
    panel: str | None
    y_mm: float
    z_mm: float


@dataclass(frozen=True)
class CrossSection:
    x_mm: float
    frame: str | None
    stiffeners: list[SectionStiffener]
    plates: list[SectionPlate]
    warnings: list[str]
    seams: list[SectionSeam] = field(default_factory=list)


@dataclass(frozen=True)
class _PanelItem:
    panel: IrPanel | None
    item: IrPlate | IrStiffener


@dataclass(frozen=True)
class _StiffenerItem:
    panel_id: str | None
    stiffener: SectionStiffener


def build_cross_section(
    vessel: IrVessel,
    x_mm: float,
    frame: str | None = None,
    tol: float = 0.1,
) -> CrossSection:
    """Build a transverse cross-section at ``x_mm`` from vessel IR geometry."""
    warnings: list[str] = []
    to_mm = lambda p: point_mm(p, vessel.unit_registry)

    stiffener_items = _build_stiffeners(vessel, x_mm, to_mm, tol, warnings)
    stiffeners = _with_spacing(stiffener_items, warnings)
    plates = _build_plates(vessel, x_mm, to_mm, tol, warnings)
    seams = _build_seams(vessel, x_mm, to_mm, tol, warnings)

    if not stiffeners and not plates:
        raise SectionError(f"No plates or stiffeners intersect x={x_mm} mm")

    return CrossSection(
        x_mm=x_mm,
        frame=frame,
        stiffeners=stiffeners,
        plates=plates,
        warnings=warnings,
        seams=seams,
    )


def _build_stiffeners(
    vessel: IrVessel,
    x_mm: float,
    to_mm,
    tol: float,
    warnings: list[str],
) -> list[_StiffenerItem]:
    result: list[_StiffenerItem] = []
    for panel_item in _panel_stiffeners(vessel):
        stiffener = panel_item.item
        assert isinstance(stiffener, IrStiffener)
        if stiffener.trace is None:
            continue
        name = _name(stiffener)
        
        try:
            hits = intersect_curve_plane(stiffener.trace, x_mm, to_mm, tol)
            if not hits:
                continue

            profile_type, profile_dimensions, section_kind, h_mm, bf_mm, tw_mm, tf_mm = _profile(
                stiffener, vessel, warnings, name
            )
            material_reh_mpa = _safe_material_reh_mpa(stiffener.material_ref, vessel, "stiffener", name, warnings)
            panel_name = _panel_name(panel_item.panel)
            panel_id = panel_item.panel.id if panel_item.panel is not None else None
            web_dir_y, web_dir_z = _web_dir(stiffener, x_mm, to_mm, warnings)
            for y_mm, z_mm in hits:
                result.append(
                    _StiffenerItem(
                        panel_id=panel_id,
                        stiffener=SectionStiffener(
                            name=name,
                            y_mm=y_mm,
                            z_mm=z_mm,
                            panel=panel_name,
                            profile_type=profile_type,
                            profile_dimensions=profile_dimensions,
                            material_reh_mpa=material_reh_mpa,
                            spacing_mm=None,
                            section_kind=section_kind,
                            h_mm=h_mm,
                            bf_mm=bf_mm,
                            tw_mm=tw_mm,
                            tf_mm=tf_mm,
                            web_dir_y=web_dir_y,
                            web_dir_z=web_dir_z,
                        ),
                    )
                )
        except GeometryError as exc:
            warnings.append(f"stiffener {name}: {exc}")
            continue

    return result


def _build_plates(
    vessel: IrVessel,
    x_mm: float,
    to_mm,
    tol: float,
    warnings: list[str],
) -> list[SectionPlate]:
    result: list[SectionPlate] = []
    for panel_item in _panel_plates(vessel):
        plate = panel_item.item
        assert isinstance(plate, IrPlate)
        if plate.outer_contour is None:
            continue
        name = _name(plate)
        
        try:
            hits = intersect_curve_plane(plate.outer_contour, x_mm, to_mm, tol)
            if not hits:
                continue

            hits = _sort_hits_along_principal_axis(hits)
            if len(hits) % 2 == 1:
                warnings.append(f"plate {name}: odd number of intersection points ({len(hits)}); dropping leftover")
            
            thickness_mm = _safe_qty_mm(plate.thickness, vessel.unit_registry, "plate", name, "thickness", warnings)
            material_reh_mpa = _safe_material_reh_mpa(plate.material_ref, vessel, "plate", name, warnings)
            panel_name = _panel_name(panel_item.panel)

            if len(hits) == 2:
                trace = trace_profile(plate.outer_contour, x_mm, to_mm, tol)
                if trace is not None and len(trace) > 2 and _trace_matches_hits(trace, hits, tol):
                    for p1, p2, radius_mm, center in _decompose_trace(trace):
                        result.append(
                            SectionPlate(
                                name=name,
                                y1_mm=p1[0],
                                z1_mm=p1[1],
                                y2_mm=p2[0],
                                z2_mm=p2[1],
                                thickness_mm=thickness_mm,
                                material_reh_mpa=material_reh_mpa,
                                panel=panel_name,
                                radius_mm=radius_mm,
                                arc_center_y_mm=center[0] if center else None,
                                arc_center_z_mm=center[1] if center else None,
                            )
                        )
                    continue

            arc_info = _plate_arc_info(plate, x_mm, to_mm, vessel.unit_registry)
            radius_mm, arc_center_y_mm, arc_center_z_mm = arc_info or (None, None, None)
            
            for left, right in zip(hits[0::2], hits[1::2]):
                result.append(
                    SectionPlate(
                        name=name,
                        y1_mm=left[0],
                        z1_mm=left[1],
                        y2_mm=right[0],
                        z2_mm=right[1],
                        thickness_mm=thickness_mm,
                        material_reh_mpa=material_reh_mpa,
                        panel=panel_name,
                        radius_mm=radius_mm,
                        arc_center_y_mm=arc_center_y_mm,
                        arc_center_z_mm=arc_center_z_mm,
                    )
                )
        except GeometryError as exc:
            warnings.append(f"plate {name}: {exc}")
            continue

    return result


def _build_seams(
    vessel: IrVessel,
    x_mm: float,
    to_mm,
    tol: float,
    warnings: list[str],
) -> list[SectionSeam]:
    """Intersect each panel's seam tracelines with the section plane.

    Transverse seams parallel to the plane simply produce no hits; a seam
    traceline may cross the plane more than once (one SectionSeam per hit).
    """
    result: list[SectionSeam] = []
    for panel in vessel.panels.values():
        panel_name = _panel_name(panel)
        for seam_id in panel.seam_ids:
            seam = vessel.seams.get(seam_id)
            if seam is None or seam.trace_line is None:
                continue
            name = seam.name or seam.id
            try:
                hits = intersect_curve_plane(seam.trace_line, x_mm, to_mm, tol)
            except GeometryError as exc:
                warnings.append(f"seam {name}: {exc}")
                continue
            for y_mm, z_mm in hits:
                result.append(SectionSeam(name=name, panel=panel_name, y_mm=y_mm, z_mm=z_mm))
    return result


def _trace_matches_hits(
    trace: list[tuple[float, float]],
    hits: list[tuple[float, float]],
    tol: float,
) -> bool:
    match_tol = max(1.0, 10.0 * tol)
    starts = (hypot(trace[0][0] - hits[0][0], trace[0][1] - hits[0][1]) <= match_tol
              and hypot(trace[-1][0] - hits[1][0], trace[-1][1] - hits[1][1]) <= match_tol)
    reversed_match = (hypot(trace[0][0] - hits[1][0], trace[0][1] - hits[1][1]) <= match_tol
                      and hypot(trace[-1][0] - hits[0][0], trace[-1][1] - hits[0][1]) <= match_tol)
    return starts or reversed_match


def _decompose_trace(
    trace: list[tuple[float, float]],
    fit_tol: float = 0.5,
) -> list[tuple[tuple[float, float], tuple[float, float], float | None, tuple[float, float] | None]]:
    """Split a section trace polyline into straight and circular-arc segments.

    Returns ``(start, end, radius_mm, center)`` tuples; ``radius_mm``/``center``
    are ``None`` for straight segments. Arc runs need at least four trace
    points on a common circle so tessellated bilge arcs recover their
    canonical radius while knuckles and seams stay straight segments.
    """
    segments: list[tuple[tuple[float, float], tuple[float, float], float | None, tuple[float, float] | None]] = []
    runs: list[tuple[int, int, float | None, tuple[float, float] | None]] = []
    index = 0
    count = len(trace)
    while index < count - 1:
        arc = _longest_arc_run(trace, index, fit_tol)
        if arc is not None:
            stop, radius, center = arc
            # Vertex noise near fit_tol can break one physical arc into
            # adjacent runs; refit the combined range with a relaxed tolerance
            # and merge when the points still share a single circle.
            if runs and runs[-1][2] is not None:
                prev_start = runs[-1][0]
                refit = _fit_circle_2d(trace[prev_start : stop + 1], 2.0 * fit_tol)
                if refit is not None:
                    runs[-1] = (prev_start, stop, refit[0], refit[1])
                    index = stop
                    continue
            runs.append((index, stop, radius, center))
            index = stop
            continue
        stop = index + 1
        while stop + 1 < count and _run_is_straight(trace, index, stop + 1, fit_tol):
            stop += 1
        runs.append((index, stop, None, None))
        index = stop
    for start, stop, radius, center in runs:
        segments.append((trace[start], trace[stop], radius, center))
    return segments


def _longest_arc_run(
    trace: list[tuple[float, float]],
    start: int,
    fit_tol: float,
) -> tuple[int, float, tuple[float, float]] | None:
    best: tuple[int, float, tuple[float, float]] | None = None
    stop = start + 3
    while stop < len(trace):
        fit = _fit_circle_2d(trace[start : stop + 1], fit_tol)
        if fit is None:
            break
        best = (stop, fit[0], fit[1])
        stop += 1
    if best is None:
        return None
    stop, radius, center = best
    chord = hypot(trace[stop][0] - trace[start][0], trace[stop][1] - trace[start][1])
    if radius <= 0.0 or chord <= 0.0:
        return None
    half_chord = min(chord / 2.0, radius)
    sagitta = radius - (radius * radius - half_chord * half_chord) ** 0.5
    if sagitta < 4.0 * fit_tol:
        return None
    return best


def _run_is_straight(
    trace: list[tuple[float, float]],
    start: int,
    stop: int,
    fit_tol: float,
) -> bool:
    (x1, y1), (x2, y2) = trace[start], trace[stop]
    length = hypot(x2 - x1, y2 - y1)
    if length <= 0.0:
        return False
    for x, y in trace[start + 1 : stop]:
        if abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / length > fit_tol:
            return False
    return True


def _fit_circle_2d(
    points: list[tuple[float, float]],
    fit_tol: float,
) -> tuple[float, tuple[float, float]] | None:
    """Least-squares circle fit; ``None`` for collinear points or poor fits."""
    arr = np.asarray(points, dtype=float)
    chord = float(np.linalg.norm(arr[-1] - arr[0]))
    if chord <= 0.0:
        return None
    deviation = max(
        float(abs((arr[-1][0] - arr[0][0]) * (arr[0][1] - y) - (arr[0][0] - x) * (arr[-1][1] - arr[0][1]))) / chord
        for x, y in arr[1:-1]
    )
    if deviation <= fit_tol:
        return None
    design = np.column_stack([2.0 * arr, np.ones(len(arr))])
    target = (arr**2).sum(axis=1)
    try:
        solution, *_ = np.linalg.lstsq(design, target, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cy, cz, constant = (float(v) for v in solution)
    radius_sq = constant + cy * cy + cz * cz
    if radius_sq <= 0.0:
        return None
    radius = radius_sq**0.5
    residual = float(np.abs(np.hypot(arr[:, 0] - cy, arr[:, 1] - cz) - radius).max())
    if residual > fit_tol:
        return None
    return radius, (cy, cz)


def _plate_arc_info(
    ir_plate: IrPlate,
    x_mm: float,
    to_mm,
    registry: dict[str, IrUnit],
) -> tuple[float, float, float] | None:
    contour = getattr(ir_plate, "outer_contour", None)
    if contour is None:
        return None

    accepted: list[tuple[float, float, float, float]] = []
    for segment in _curve_segments(contour):
        info = _arc_segment_info(segment, to_mm, registry)
        if info is None:
            continue
        center, radius, normal = info
        if abs(float(normal[0])) < 0.99:
            continue
        accepted.append(
            (abs(float(center[0] - x_mm)), float(radius), float(center[1]), float(center[2]))
        )

    if not accepted:
        return None
    _, radius_mm, center_y_mm, center_z_mm = min(accepted, key=lambda item: item[0])
    return radius_mm, center_y_mm, center_z_mm


def _curve_segments(curve: IrCurve3D) -> Iterable[IrCurve3D]:
    if isinstance(curve, IrCompositeCurve3D):
        return getattr(curve, "segments", None) or []
    return (curve,)


def _arc_segment_info(
    segment: IrCurve3D,
    to_mm,
    registry: dict[str, IrUnit],
) -> tuple[np.ndarray, float, np.ndarray] | None:
    try:
        if isinstance(segment, IrCircumArc3D):
            start = getattr(segment, "start", None)
            intermediate = getattr(segment, "intermediate", None)
            end = getattr(segment, "end", None)
            if start is None or intermediate is None or end is None:
                return None
            center, radius, normal = _circle_from_three_points(
                np.asarray(to_mm(start), dtype=float),
                np.asarray(to_mm(intermediate), dtype=float),
                np.asarray(to_mm(end), dtype=float),
            )
            return center, radius, normal
        if isinstance(segment, IrCircle3D):
            center_point = getattr(segment, "center", None)
            diameter = getattr(segment, "diameter", None)
            normal_vector = getattr(segment, "normal", None)
            if center_point is None or diameter is None or normal_vector is None:
                return None
            diameter_mm = qty_mm(diameter, registry)
            if diameter_mm is None or diameter_mm <= 0.0:
                return None
            normal = np.asarray(
                [normal_vector.x, normal_vector.y, normal_vector.z],
                dtype=float,
            )
            normal_length = float(np.linalg.norm(normal))
            if normal_length < 1e-9:
                return None
            return (
                np.asarray(to_mm(center_point), dtype=float),
                diameter_mm / 2.0,
                normal / normal_length,
            )
    except GeometryError:
        return None
    return None


def _panel_stiffeners(vessel: IrVessel) -> Iterable[_PanelItem]:
    seen: set[str] = set()
    for panel in vessel.panels.values():
        for stiffener_id in panel.stiffener_ids:
            stiffener = vessel.stiffeners.get(stiffener_id)
            if stiffener is None:
                continue
            seen.add(stiffener.id)
            yield _PanelItem(panel, stiffener)
    for stiffener in vessel.stiffeners.values():
        if stiffener.id in seen:
            continue
        yield _PanelItem(_parent_panel(vessel, stiffener), stiffener)


def _panel_plates(vessel: IrVessel) -> Iterable[_PanelItem]:
    seen: set[str] = set()
    for panel in vessel.panels.values():
        for plate_id in panel.plate_ids:
            plate = vessel.plates.get(plate_id)
            if plate is None:
                continue
            seen.add(plate.id)
            yield _PanelItem(panel, plate)
    for plate in vessel.plates.values():
        if plate.id in seen:
            continue
        yield _PanelItem(_parent_panel(vessel, plate), plate)


def _parent_panel(vessel: IrVessel, item: IrPlate | IrStiffener) -> IrPanel | None:
    parent_ref = getattr(item, "parent_ref", None)
    if parent_ref is None:
        return None
    return vessel.panels.get(parent_ref.id)


def _sort_hits_along_principal_axis(hits: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(hits) <= 2:
        return sorted(hits, key=lambda yz: (yz[1], yz[0]))

    best_i = 0
    best_j = 1
    best_dist_sq = -1.0
    for i, first in enumerate(hits):
        for j in range(i + 1, len(hits)):
            second = hits[j]
            dist_sq = (second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2
            if dist_sq > best_dist_sq:
                best_i = i
                best_j = j
                best_dist_sq = dist_sq

    axis_start = hits[best_i]
    axis_end = hits[best_j]
    if (axis_end[0], axis_end[1]) < (axis_start[0], axis_start[1]):
        axis_start, axis_end = axis_end, axis_start
    axis_y = axis_end[0] - axis_start[0]
    axis_z = axis_end[1] - axis_start[1]
    return sorted(
        hits,
        key=lambda yz: (
            (yz[0] - axis_start[0]) * axis_y + (yz[1] - axis_start[1]) * axis_z,
            yz[1],
            yz[0],
        ),
    )


def _with_spacing(stiffener_items: list[_StiffenerItem], warnings: list[str]) -> list[SectionStiffener]:
    by_panel: dict[str, list[int]] = {}
    updated = [item.stiffener for item in stiffener_items]
    for index, item in enumerate(stiffener_items):
        if item.panel_id is None:
            warnings.append(
                f"stiffener {item.stiffener.name}: panel is missing or unresolved; spacing unavailable"
            )
            continue
        by_panel.setdefault(item.panel_id, []).append(index)

    for panel_id, indexes in by_panel.items():
        if len(indexes) == 1:
            panel_name = stiffener_items[indexes[0]].stiffener.panel or panel_id
            warnings.append(f"panel {panel_name}: one stiffener intersects section; spacing unavailable")
            updated[indexes[0]] = replace(updated[indexes[0]], spacing_mm=None)
            continue
        for index in indexes:
            current = stiffener_items[index].stiffener
            nearest = min(
                hypot(
                    current.y_mm - stiffener_items[other].stiffener.y_mm,
                    current.z_mm - stiffener_items[other].stiffener.z_mm,
                )
                for other in indexes
                if other != index
            )
            updated[index] = replace(current, spacing_mm=nearest)
    return updated


def _profile(
    stiffener: IrStiffener,
    vessel: IrVessel,
    warnings: list[str],
    stiffener_name: str,
) -> tuple[
    str | None,
    str | None,
    str | None,
    float | None,
    float | None,
    float | None,
    float | None,
]:
    section = _resolve(vessel.sections, stiffener.section_ref)
    if section is None:
        warnings.append(f"stiffener {stiffener_name}: section reference is missing or unresolved")
        return None, None, None, None, None, None, None

    registry = vessel.unit_registry
    if isinstance(section, IrBulbFlatSection):
        h_mm = _safe_qty_mm(section.height, registry, "stiffener", stiffener_name, "height", warnings)
        tw_mm = _safe_qty_mm(
            section.web_thickness,
            registry,
            "stiffener",
            stiffener_name,
            "web_thickness",
            warnings,
        )
        bf_mm = None
        tf_mm = None
        dimensions = _safe_dimensions([h_mm, tw_mm])
        profile_type = "HpBulb"
        section_kind = "bulb_flat"
    elif isinstance(section, IrFlatBarSection):
        h_mm = _safe_qty_mm(section.height, registry, "stiffener", stiffener_name, "height", warnings)
        tw_mm = _safe_qty_mm(section.width, registry, "stiffener", stiffener_name, "width", warnings)
        bf_mm = None
        tf_mm = None
        dimensions = _safe_dimensions([h_mm, tw_mm])
        profile_type = "FlatBar"
        section_kind = "flat_bar"
    elif isinstance(section, IrTSection):
        h_mm = _safe_qty_mm(section.height, registry, "stiffener", stiffener_name, "height", warnings)
        bf_mm = _safe_qty_mm(section.width, registry, "stiffener", stiffener_name, "width", warnings)
        tw_mm = _safe_qty_mm(
            section.web_thickness,
            registry,
            "stiffener",
            stiffener_name,
            "web_thickness",
            warnings,
        )
        tf_mm = _safe_qty_mm(
            section.flange_thickness,
            registry,
            "stiffener",
            stiffener_name,
            "flange_thickness",
            warnings,
        )
        dimensions = _safe_dimensions([h_mm, bf_mm, tw_mm, tf_mm])
        profile_type = "TBar"
        section_kind = "t_section"
    elif isinstance(section, (IrLSection, IrLSectionOvershootFlange, IrLSectionOvershootWeb)):
        h_mm = _safe_qty_mm(section.height, registry, "stiffener", stiffener_name, "height", warnings)
        bf_mm = _safe_qty_mm(section.width, registry, "stiffener", stiffener_name, "width", warnings)
        tw_mm = _safe_qty_mm(
            section.web_thickness,
            registry,
            "stiffener",
            stiffener_name,
            "web_thickness",
            warnings,
        )
        tf_mm = _safe_qty_mm(
            section.flange_thickness,
            registry,
            "stiffener",
            stiffener_name,
            "flange_thickness",
            warnings,
        )
        dimensions = _safe_dimensions([h_mm, bf_mm, tw_mm, tf_mm])
        profile_type = "AngleBar"
        section_kind = _l_section_kind(section)
    else:
        warnings.append(f"stiffener {stiffener_name}: unsupported section type {type(section).__name__}")
        return None, None, None, None, None, None, None

    if dimensions is None:
        warnings.append(f"stiffener {stiffener_name}: section dimensions are incomplete")
        return profile_type, None, section_kind, h_mm, bf_mm, tw_mm, tf_mm
    return profile_type, dimensions, section_kind, h_mm, bf_mm, tw_mm, tf_mm


def _l_section_kind(section: IrLSection | IrLSectionOvershootFlange | IrLSectionOvershootWeb) -> str:
    if isinstance(section, IrLSectionOvershootFlange):
        return "l_overshoot_flange"
    if isinstance(section, IrLSectionOvershootWeb):
        return "l_overshoot_web"
    return "l_section"


def _web_dir(
    stiffener,
    x_mm: float,
    to_mm,
    warnings: list[str],
) -> tuple[float | None, float | None]:
    """Project the stiffener web direction onto the section (y, z) plane."""
    inclinations = getattr(stiffener, "inclinations", None) or []
    candidates = [inc for inc in inclinations if inc.web_direction is not None]
    if not candidates:
        warnings.append(f"stiffener {_name(stiffener)}: no inclination; web direction unknown")
        return None, None

    def _distance(inc) -> float:
        if inc.position is None:
            return float("inf")
        try:
            px, _, _ = to_mm(inc.position)
        except GeometryError:
            return float("inf")
        return abs(px - x_mm)

    with_pos = [inc for inc in candidates if inc.position is not None]
    chosen = min(with_pos, key=_distance) if with_pos else candidates[0]
    wd = chosen.web_direction
    length = hypot(wd.y, wd.z)
    if length < 1e-9:
        warnings.append(
            f"stiffener {_name(stiffener)}: web direction has no in-plane component"
        )
        return None, None
    return wd.y / length, wd.z / length


def _safe_qty_mm(
    qty: Quantity | None,
    registry: dict[str, object],
    item_kind: str,
    item_name: str,
    attr_name: str,
    warnings: list[str],
) -> float | None:
    """Convert quantity to mm, returning None on unit conversion errors with warning."""
    if qty is None:
        return None
    try:
        return qty_mm(qty, registry)
    except GeometryError as exc:
        warnings.append(f"{item_kind} {item_name}: {exc}")
        return None


def _safe_material_reh_mpa(
    ref: Ref | None,
    vessel: IrVessel,
    item_kind: str,
    item_name: str,
    warnings: list[str],
) -> float | None:
    """Get material yield stress in MPa, returning None on unit conversion errors with warning."""
    material = _resolve(vessel.materials, ref)
    if not isinstance(material, IrMaterial):
        return None
    try:
        return qty_mpa(material.yield_stress, vessel.unit_registry)
    except GeometryError as exc:
        warnings.append(f"{item_kind} {item_name}: {exc}")
        return None


def _safe_dimensions(values: list[float | None]) -> str | None:
    """Format dimensions, handling None values from failed conversions."""
    if any(value is None for value in values):
        return None
    return " x ".join(_format_mm(value) for value in values if value is not None)


def _resolve(catalogue: dict[str, object], ref: Ref | None) -> object | None:
    if ref is None:
        return None
    if ref.local_ref in catalogue:
        return catalogue[ref.local_ref]
    if ref.guidref is not None:
        for item in catalogue.values():
            if getattr(item, "guidref", None) == ref.guidref:
                return item
    return None


def _format_mm(value: float) -> str:
    rounded = round(value, 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def _name(item: IrPlate | IrStiffener | IrSection) -> str:
    return item.name or item.id


def _panel_name(panel: IrPanel | None) -> str | None:
    if panel is None:
        return None
    return panel.name or panel.id
