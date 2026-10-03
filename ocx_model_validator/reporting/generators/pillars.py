"""Pillar report generator.

One row per pillar: attributes (panel parent, function, material,
profile), material offset, trace length, physical properties (moulded
dry weight) and counts of inclinations and penetrations. Pillar
geometry is intentionally excluded.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import ParentKind
from ocx_model_validator.model.ir.structural import IrPillar, IrVessel
from ocx_model_validator.reporting.generators._common import (
    inherited_function_cell,
    qty_m_cell,
    qty_mm_cell,
    qty_tonnes_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Id", "Name", "Parent Panel", "Function", "Material", "Profile",
    "Offset (mm)", "Length (m)", "Dry weight (t)", "Inclinations",
    "Penetrations",
]


def _panel_name(p: IrPillar, vessel: IrVessel) -> str | None:
    if p.parent_ref is None or p.parent_ref.kind != ParentKind.PANEL:
        return None
    panel = vessel.panels.get(p.parent_ref.id)
    return (panel.name or panel.id) if panel is not None else p.parent_ref.id


def _material_name(p: IrPillar, vessel: IrVessel) -> str | None:
    if p.material_ref is None:
        return None
    m = vessel.materials.get(p.material_ref.local_ref)
    return (m.name or m.grade or m.id) if m is not None else None


def _profile_name(p: IrPillar, vessel: IrVessel) -> str | None:
    if p.section_ref is None:
        return None
    sec = vessel.sections.get(p.section_ref.local_ref)
    return (sec.name or sec.id) if sec is not None else p.section_ref.local_ref


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for p in sorted(vessel.pillars.values(), key=lambda p: p.name or p.id):
        ctx = f"pillar {p.id}"
        mp = p.mass_properties
        length = p.trace.curve_length if p.trace is not None else None
        offset = p.material_ref.offset if p.material_ref is not None else None
        rows.append([
            p.id, p.name, _panel_name(p, vessel),
            inherited_function_cell(p.function_type, p.parent_ref, vessel),
            _material_name(p, vessel), _profile_name(p, vessel),
            qty_mm_cell(offset, reg, notes, f"{ctx} offset"),
            qty_m_cell(length, reg, notes, f"{ctx} length"),
            qty_tonnes_cell(mp.moulded_dry_weight if mp is not None else None,
                            reg, notes, f"{ctx} dry weight"),
            len(p.inclinations), len(p.penetrations),
        ])
    section = ReportSection(title="Pillars",
                            tables=[ReportTable("Pillars", _COLUMNS, rows)],
                            notes=notes)
    return Report(title="Pillar report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
