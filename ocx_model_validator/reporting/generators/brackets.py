"""Bracket report generator.

One row per bracket: attributes (panel parent, material), thicknesses
(as-built, renewal, voluntary addition), material offset, physical
properties (moulded dry weight) and the full BracketParameters set:
arm lengths, origin and U/V directions, nose dimensions, free edge
radius, edge reinforcement,
supports, reinforcement type, FeatureCope and FlangeEdgeReinforcement
properties. Bracket geometry is intentionally excluded.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import ParentKind
from ocx_model_validator.model.ir.structural import IrBracket, IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_tonnes_cell,
    report_metadata,
    xyz_m_cells,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Id", "Name", "Parent Panel", "Material",
    "Thickness (mm)", "Renewal thickness (mm)",
    "Voluntary addition (mm)", "Offset (mm)", "Dry weight (t)",
    "Arm length U (mm)", "Arm length V (mm)",
    "Origin (m)", "U direction", "V direction",
    "U nose (mm)", "V nose (mm)", "Free edge radius (mm)",
    "Edge reinforcement", "Supports", "Reinforcement type",
    "Cope radius (mm)", "Cope length (mm)", "Cope height (mm)",
    "Flange width (mm)", "Flange radius (mm)",
]


def _panel_name(b: IrBracket, vessel: IrVessel) -> str | None:
    if b.parent_ref is None or b.parent_ref.kind != ParentKind.PANEL:
        return None
    panel = vessel.panels.get(b.parent_ref.id)
    return (panel.name or panel.id) if panel is not None else b.parent_ref.id


def _material_name(b: IrBracket, vessel: IrVessel) -> str | None:
    if b.material_ref is None:
        return None
    m = vessel.materials.get(b.material_ref.local_ref)
    return (m.name or m.grade or m.id) if m is not None else None


def _vector_cell(v) -> Cell:
    if v is None:
        return None
    return f"[{v.x}, {v.y}, {v.z}]"


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for b in sorted(vessel.brackets.values(), key=lambda b: b.name or b.id):
        ctx = f"bracket {b.id}"
        mp = b.mass_properties
        offset = b.material_ref.offset if b.material_ref is not None else None
        fc = b.feature_cope
        origin_cell: Cell = None
        if b.origin is not None:
            coords = xyz_m_cells(b.origin.x, b.origin.y, b.origin.z,
                                 b.origin.unit, reg, notes, f"{ctx} origin")
            origin_cell = "(" + ", ".join(str(c) for c in coords) + ")"
        rows.append([
            b.id, b.name, _panel_name(b, vessel), _material_name(b, vessel),
            qty_mm_cell(b.thickness, reg, notes, f"{ctx} thickness"),
            qty_mm_cell(b.renewal_thickness, reg, notes,
                        f"{ctx} renewal thickness"),
            qty_mm_cell(b.voluntary_thickness_addition, reg, notes,
                        f"{ctx} voluntary addition"),
            qty_mm_cell(offset, reg, notes, f"{ctx} offset"),
            qty_tonnes_cell(mp.moulded_dry_weight if mp is not None else None,
                            reg, notes, f"{ctx} dry weight"),
            qty_mm_cell(b.arm_length_u, reg, notes, f"{ctx} arm length U"),
            qty_mm_cell(b.arm_length_v, reg, notes, f"{ctx} arm length V"),
            origin_cell,
            _vector_cell(b.udirection),
            _vector_cell(b.vdirection),
            qty_mm_cell(b.unose, reg, notes, f"{ctx} U nose"),
            qty_mm_cell(b.vnose, reg, notes, f"{ctx} V nose"),
            qty_mm_cell(b.free_edge_radius, reg, notes,
                        f"{ctx} free edge radius"),
            "yes" if b.has_edge_reinforcement else None,
            b.number_of_supports,
            b.reinforcement_type,
            qty_mm_cell(fc.cope_radius if fc else None, reg, notes,
                        f"{ctx} cope radius"),
            qty_mm_cell(fc.cope_length if fc else None, reg, notes,
                        f"{ctx} cope length"),
            qty_mm_cell(fc.cope_height if fc else None, reg, notes,
                        f"{ctx} cope height"),
            qty_mm_cell(b.flange_width, reg, notes, f"{ctx} flange width"),
            qty_mm_cell(b.flange_radius, reg, notes, f"{ctx} flange radius"),
        ])
    section = ReportSection(title="Brackets",
                            tables=[ReportTable("Brackets", _COLUMNS, rows)],
                            notes=notes)
    return Report(title="Bracket report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
