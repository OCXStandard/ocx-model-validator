"""Panel report generator.

One row per panel: attributes (function, tightness), physical properties
(moulded dry weight, COG) and counts of LimitedBy boundaries and child
parts. Panel geometry is intentionally excluded.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.structural import IrPanel, IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_tonnes_cell,
    report_metadata,
    xyz_m_cells,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Id", "Name", "Function", "Tightness", "Dry weight (t)",
    "COG x (m)", "COG y (m)", "COG z (m)", "LimitedBy",
    "Stiffeners", "Plates", "Seams", "Edge reinforcements", "Openings",
]


def _cog_cells(panel: IrPanel, vessel: IrVessel,
               notes: list[str]) -> list[Cell]:
    mp = panel.mass_properties
    cog = (mp.moulded_cog or mp.physical_cog) if mp is not None else None
    if cog is None:
        return [None, None, None]
    return xyz_m_cells(cog.x, cog.y, cog.z, cog.unit, vessel.unit_registry,
                       notes, f"panel {panel.id} COG")


def build(vessel: IrVessel, source_file: str = "") -> Report:
    notes: list[str] = []
    rows: list[list[Cell]] = []
    for p in sorted(vessel.panels.values(), key=lambda p: p.name or p.id):
        mp = p.mass_properties
        weight = qty_tonnes_cell(
            mp.moulded_dry_weight if mp is not None else None,
            vessel.unit_registry, notes, f"panel {p.id} dry weight")
        rows.append([p.id, p.name, p.function_type, p.tightness, weight,
                     *_cog_cells(p, vessel, notes),
                     len(p.limited_by), len(p.stiffener_ids),
                     len(p.plate_ids), len(p.seam_ids),
                     len(p.edge_reinforcement_ids), len(p.hole_shape_refs)])
    section = ReportSection(title="Panels",
                            tables=[ReportTable("Panels", _COLUMNS, rows)],
                            notes=notes)
    return Report(title="Panel report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
