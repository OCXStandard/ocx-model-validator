"""Compartments report generator — reuses sections.build_compartments_block."""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable
from ocx_model_validator.sections.document import build_compartments_block
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table

_COLUMNS = [
    "Name", "Tank type", "Volume (m³)",
    "COG x (mm)", "COG y (mm)", "COG z (mm)",
    "min x (frame)", "max x (frame)", "min y (mm)", "max y (mm)", "min z (mm)", "max z (mm)",
    "Filling height (mm)", "Air pipe height (mm)", "Relief valve pressure (kPa)",
]

_FRAME_TOL_MM = 0.5


def _frame_pos(x_mm: float | None, ft: FrameTable | None) -> Cell:
    """Render an x position as '#<frame>' plus/minus the offset in mm."""
    if x_mm is None or ft is None:
        return x_mm
    label, frame_x = ft.nearest_frame(x_mm)
    offset = x_mm - frame_x
    if abs(offset) < _FRAME_TOL_MM:
        return f"#{label}"
    sign = "+" if offset >= 0 else "-"
    return f"#{label}{sign}{abs(round(offset, 1)):g}"


def build(vessel: IrVessel, source_file: str = "") -> Report:
    raw_rows, warnings = build_compartments_block(vessel)
    try:
        ft: FrameTable | None = build_frame_table(vessel)
    except (GeometryError, SectionError):
        ft = None
    rows: list[list[Cell]] = []
    for r in sorted(raw_rows, key=lambda r: r["name"]):
        cog = r.get("cog_mm") or [None, None, None]
        ext = r.get("extent_mm") or {}
        rows.append([
            r.get("name"), r.get("tank_type"), r.get("volume_m3"),
            cog[0], cog[1], cog[2],
            _frame_pos(ext.get("min_x"), ft), _frame_pos(ext.get("max_x"), ft),
            ext.get("min_y"), ext.get("max_y"),
            ext.get("min_z"), ext.get("max_z"),
            r.get("filling_height_mm"), r.get("air_pipe_height_mm"),
            r.get("relief_valve_pressure_kpa"),
        ])
    section = ReportSection(
        title="Compartments",
        tables=[ReportTable("Compartments", _COLUMNS, rows)],
        notes=list(warnings),
    )
    return Report(title="Compartments report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
