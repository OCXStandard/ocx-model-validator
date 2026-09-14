"""Frame table report generator — reuses sections.build_frame_table."""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable
from ocx_model_validator.sections.frame_table import build_frame_table

_TITLE = "Frame table report"


def build(vessel: IrVessel, source_file: str = "") -> Report:
    metadata = report_metadata(vessel, source_file)
    try:
        ft = build_frame_table(vessel)
    except (GeometryError, SectionError) as exc:
        section = ReportSection(
            title="Frame table",
            tables=[ReportTable("Frame positions",
                                ["Frame", "Name", "x (mm)", "Display grid"], [])],
            notes=[str(exc)],
        )
        return Report(title=_TITLE, metadata=metadata, sections=[section])

    spacing = ReportTable(
        title="Spacing entries",
        columns=["From frame", "Spacing (mm)"],
        rows=[[label, round(s, 1)] for label, s in ft.entries],
    )

    def _grid_cell(display_grid: bool | None) -> str:
        if display_grid is None:
            return ""
        return "yes" if display_grid else "no"

    positions = ReportTable(
        title="Frame positions",
        columns=["Frame", "Name", "x (mm)", "Display grid"],
        rows=[[f.label, f.name or "", round(f.x_mm, 1), _grid_cell(f.display_grid)]
              for f in ft.frames],
    )
    frame0 = next((f for f in ft.frames if f.x_mm == ft.frame0_offset_mm), None)
    frame0_name = f" (frame {frame0.name or frame0.label})" if frame0 else ""
    section = ReportSection(
        title="Frame table",
        intro=(
            f"Frame 0 offset: {round(ft.frame0_offset_mm, 1)} mm{frame0_name} — "
            f"{len(ft.frames)} frames"
        ),
        tables=[spacing, positions],
        notes=list(ft.warnings),
    )
    return Report(title=_TITLE, metadata=metadata, sections=[section])
