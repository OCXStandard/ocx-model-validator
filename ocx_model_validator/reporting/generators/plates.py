"""Plate report generator.

One row per plate: attributes (panel parent, function, material),
thicknesses (as-built, renewal, voluntary addition), material offset,
net area, physical properties (moulded dry weight), point on surface and
the number of cut-by openings. Plate geometry is intentionally excluded.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import ParentKind
from ocx_model_validator.model.ir.structural import IrPlate, IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_m2_cell,
    qty_mm_cell,
    qty_tonnes_cell,
    report_metadata,
    xyz_m_cells,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Id", "Name", "Parent Panel", "Function", "Material",
    "Thickness (mm)", "Renewal thickness (mm)",
    "Voluntary addition (mm)", "Offset (mm)", "Net area (m²)",
    "Dry weight (t)", "Point on surface (m)", "Openings",
]


def _panel_name(plate: IrPlate, vessel: IrVessel) -> str | None:
    if plate.parent_ref is None or plate.parent_ref.kind != ParentKind.PANEL:
        return None
    panel = vessel.panels.get(plate.parent_ref.id)
    return (panel.name or panel.id) if panel is not None else plate.parent_ref.id


def _material_name(plate: IrPlate, vessel: IrVessel) -> str | None:
    if plate.material_ref is None:
        return None
    m = vessel.materials.get(plate.material_ref.local_ref)
    return (m.name or m.grade or m.id) if m is not None else None


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for p in sorted(vessel.plates.values(), key=lambda p: p.name or p.id):
        ctx = f"plate {p.id}"
        mp = p.mass_properties
        offset = p.material_ref.offset if p.material_ref is not None else None
        pos = p.point_on_surface
        pos_cell: Cell = None
        if pos is not None:
            coords = xyz_m_cells(pos.x, pos.y, pos.z, pos.unit, reg, notes,
                                 f"{ctx} point on surface")
            pos_cell = "(" + ", ".join(str(c) for c in coords) + ")"
        rows.append([
            p.id, p.name, _panel_name(p, vessel), p.function_type,
            _material_name(p, vessel),
            qty_mm_cell(p.thickness, reg, notes, f"{ctx} thickness"),
            qty_mm_cell(p.renewal_thickness, reg, notes,
                        f"{ctx} renewal thickness"),
            qty_mm_cell(p.voluntary_thickness_addition, reg, notes,
                        f"{ctx} voluntary addition"),
            qty_mm_cell(offset, reg, notes, f"{ctx} offset"),
            qty_m2_cell(p.net_area, reg, notes, f"{ctx} net area"),
            qty_tonnes_cell(mp.moulded_dry_weight if mp is not None else None,
                            reg, notes, f"{ctx} dry weight"),
            pos_cell,
            len(p.cut_by_contours),
        ])
    section = ReportSection(title="Plates",
                            tables=[ReportTable("Plates", _COLUMNS, rows)],
                            notes=notes)
    return Report(title="Plate report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
