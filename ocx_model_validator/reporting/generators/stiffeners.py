"""Stiffener report generator.

One row per stiffener: attributes (panel parent, function, material,
profile), trace length, physical properties (moulded dry weight) and
counts of inclinations and penetrations plus the end-cut connections.
Stiffener geometry is intentionally excluded.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import ParentKind
from ocx_model_validator.model.ir.structural import IrEndCut, IrStiffener, IrVessel
from ocx_model_validator.reporting.generators._common import (
    inherited_function_cell,
    qty_m_cell,
    qty_tonnes_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Id", "Name", "Parent Panel", "Function", "Material", "Profile",
    "Length (m)", "Dry weight (t)", "Inclinations", "Penetrations",
    "End cut 1", "End cut 2",
]


def _panel_name(s: IrStiffener, vessel: IrVessel) -> str | None:
    if s.parent_ref is None or s.parent_ref.kind != ParentKind.PANEL:
        return None
    panel = vessel.panels.get(s.parent_ref.id)
    return (panel.name or panel.id) if panel is not None else s.parent_ref.id


def _material_name(s: IrStiffener, vessel: IrVessel) -> str | None:
    if s.material_ref is None:
        return None
    m = vessel.materials.get(s.material_ref.local_ref)
    return (m.name or m.grade or m.id) if m is not None else None


def _profile_name(s: IrStiffener, vessel: IrVessel) -> str | None:
    if s.section_ref is None:
        return None
    sec = vessel.sections.get(s.section_ref.local_ref)
    return (sec.name or sec.id) if sec is not None else s.section_ref.local_ref


def _end_cut_cell(ec: IrEndCut | None) -> Cell:
    if ec is None:
        return None
    return ec.name or ec.id or ("sniped" if ec.sniped else "present")


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for s in sorted(vessel.stiffeners.values(), key=lambda s: s.name or s.id):
        ctx = f"stiffener {s.id}"
        mp = s.mass_properties
        length = s.trace.curve_length if s.trace is not None else None
        rows.append([
            s.id, s.name, _panel_name(s, vessel),
            inherited_function_cell(s.function_type, s.parent_ref, vessel),
            _material_name(s, vessel), _profile_name(s, vessel),
            qty_m_cell(length, reg, notes, f"{ctx} length"),
            qty_tonnes_cell(mp.moulded_dry_weight if mp is not None else None,
                            reg, notes, f"{ctx} dry weight"),
            len(s.inclinations), len(s.penetrations),
            _end_cut_cell(s.end_cut_end1), _end_cut_cell(s.end_cut_end2),
        ])
    section = ReportSection(title="Stiffeners",
                            tables=[ReportTable("Stiffeners", _COLUMNS, rows)],
                            notes=notes)
    return Report(title="Stiffener report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
