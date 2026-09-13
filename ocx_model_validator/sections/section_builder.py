"""Assemble transverse cross-section inputs from the schema-neutral IR."""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import hypot
from typing import Iterable

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.model.ir.base import Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
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
from ocx_model_validator.sections.geometry import intersect_curve_plane
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
    orientation: str = "Longitudinal"
    web_angle_deg: float = 90.0


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


@dataclass(frozen=True)
class CrossSection:
    x_mm: float
    frame: str | None
    stiffeners: list[SectionStiffener]
    plates: list[SectionPlate]
    warnings: list[str]


@dataclass(frozen=True)
class _PanelItem:
    panel: IrPanel | None
    item: IrPlate | IrStiffener


def build_cross_section(
    vessel: IrVessel,
    x_mm: float,
    frame: str | None = None,
    tol: float = 0.1,
) -> CrossSection:
    """Build a transverse cross-section at ``x_mm`` from vessel IR geometry."""
    warnings: list[str] = []
    to_mm = lambda p: point_mm(p, vessel.unit_registry)

    stiffeners = _build_stiffeners(vessel, x_mm, to_mm, tol, warnings)
    stiffeners = _with_spacing(stiffeners, warnings)
    plates = _build_plates(vessel, x_mm, to_mm, tol, warnings)

    if not stiffeners and not plates:
        raise SectionError(f"No plates or stiffeners intersect x={x_mm} mm")

    return CrossSection(
        x_mm=x_mm,
        frame=frame,
        stiffeners=stiffeners,
        plates=plates,
        warnings=warnings,
    )


def _build_stiffeners(
    vessel: IrVessel,
    x_mm: float,
    to_mm,
    tol: float,
    warnings: list[str],
) -> list[SectionStiffener]:
    result: list[SectionStiffener] = []
    for panel_item in _panel_stiffeners(vessel):
        stiffener = panel_item.item
        assert isinstance(stiffener, IrStiffener)
        if stiffener.trace is None:
            continue
        name = _name(stiffener)
        try:
            hits = intersect_curve_plane(stiffener.trace, x_mm, to_mm, tol)
        except GeometryError as exc:
            warnings.append(f"stiffener {name}: {exc}")
            continue

        if not hits:
            continue

        profile_type, profile_dimensions = _profile(stiffener, vessel, warnings, name)
        material_reh_mpa = _material_reh_mpa(stiffener.material_ref, vessel)
        panel_name = _panel_name(panel_item.panel)
        for y_mm, z_mm in hits:
            result.append(
                SectionStiffener(
                    name=name,
                    y_mm=y_mm,
                    z_mm=z_mm,
                    panel=panel_name,
                    profile_type=profile_type,
                    profile_dimensions=profile_dimensions,
                    material_reh_mpa=material_reh_mpa,
                    spacing_mm=None,
                )
            )
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
        except GeometryError as exc:
            warnings.append(f"plate {name}: {exc}")
            continue

        if not hits:
            continue

        hits = sorted(hits, key=lambda yz: (yz[1], yz[0]))
        if len(hits) % 2 == 1:
            warnings.append(f"plate {name}: odd number of intersection points ({len(hits)}); dropping leftover")
        thickness_mm = qty_mm(plate.thickness, vessel.unit_registry)
        material_reh_mpa = _material_reh_mpa(plate.material_ref, vessel)
        panel_name = _panel_name(panel_item.panel)
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
                )
            )
    return result


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


def _with_spacing(stiffeners: list[SectionStiffener], warnings: list[str]) -> list[SectionStiffener]:
    by_panel: dict[str | None, list[int]] = {}
    for index, stiffener in enumerate(stiffeners):
        by_panel.setdefault(stiffener.panel, []).append(index)

    updated = list(stiffeners)
    for panel_name, indexes in by_panel.items():
        if len(indexes) == 1:
            warnings.append(f"panel {panel_name or '<none>'}: one stiffener intersects section; spacing unavailable")
            updated[indexes[0]] = replace(updated[indexes[0]], spacing_mm=None)
            continue
        for index in indexes:
            current = stiffeners[index]
            nearest = min(
                hypot(current.y_mm - stiffeners[other].y_mm, current.z_mm - stiffeners[other].z_mm)
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
) -> tuple[str | None, str | None]:
    section = _resolve(vessel.sections, stiffener.section_ref)
    if section is None:
        warnings.append(f"stiffener {stiffener_name}: section reference is missing or unresolved")
        return None, None

    registry = vessel.unit_registry
    if isinstance(section, IrBulbFlatSection):
        dimensions = _dimensions([qty_mm(section.height, registry), qty_mm(section.web_thickness, registry)])
        profile_type = "HpBulb"
    elif isinstance(section, IrFlatBarSection):
        dimensions = _dimensions([qty_mm(section.height, registry), qty_mm(section.width, registry)])
        profile_type = "FlatBar"
    elif isinstance(section, IrTSection):
        dimensions = _dimensions([
            qty_mm(section.height, registry),
            qty_mm(section.width, registry),
            qty_mm(section.web_thickness, registry),
            qty_mm(section.flange_thickness, registry),
        ])
        profile_type = "TBar"
    elif isinstance(section, (IrLSection, IrLSectionOvershootFlange, IrLSectionOvershootWeb)):
        dimensions = _dimensions([
            qty_mm(section.height, registry),
            qty_mm(section.width, registry),
            qty_mm(section.web_thickness, registry),
            qty_mm(section.flange_thickness, registry),
        ])
        profile_type = "AngleBar"
    else:
        warnings.append(f"stiffener {stiffener_name}: unsupported section type {type(section).__name__}")
        return None, None

    if dimensions is None:
        warnings.append(f"stiffener {stiffener_name}: section dimensions are incomplete")
        return profile_type, None
    return profile_type, dimensions


def _material_reh_mpa(ref: Ref | None, vessel: IrVessel) -> float | None:
    material = _resolve(vessel.materials, ref)
    if not isinstance(material, IrMaterial):
        return None
    return qty_mpa(material.yield_stress, vessel.unit_registry)


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


def _dimensions(values: list[float | None]) -> str | None:
    if any(value is None for value in values):
        return None
    return " x ".join(_format_mm(value) for value in values if value is not None)


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
