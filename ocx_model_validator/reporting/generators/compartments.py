"""Compartments report generator — reuses sections.build_compartments_block."""
from __future__ import annotations

from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable
from ocx_model_validator.sections.document import build_compartments_block

_COLUMNS = [
    "Name", "Tank type", "Volume (m³)",
    "COG x (mm)", "COG y (mm)", "COG z (mm)",
    "min x (mm)", "max x (mm)", "min y (mm)", "max y (mm)", "min z (mm)", "max z (mm)",
]


def build(vessel: IrVessel, source_file: str = "") -> Report:
    raw_rows, warnings = build_compartments_block(vessel)
    rows: list[list[Cell]] = []
    for r in sorted(raw_rows, key=lambda r: r["name"]):
        cog = r.get("cog_mm") or [None, None, None]
        ext = r.get("extent_mm") or {}
        rows.append([
            r.get("name"), r.get("tank_type"), r.get("volume_m3"),
            cog[0], cog[1], cog[2],
            ext.get("min_x"), ext.get("max_x"),
            ext.get("min_y"), ext.get("max_y"),
            ext.get("min_z"), ext.get("max_z"),
        ])
    section = ReportSection(
        title="Compartments",
        tables=[ReportTable("Compartments", _COLUMNS, rows)],
        notes=list(warnings),
    )
    return Report(title="Compartments report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
