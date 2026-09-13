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
            tables=[ReportTable("Frame positions", ["Frame", "x (mm)"], [])],
            notes=[str(exc)],
        )
        return Report(title=_TITLE, metadata=metadata, sections=[section])

    spacing = ReportTable(
        title="Spacing entries",
        columns=["From frame", "Spacing (mm)"],
        rows=[[label, round(s, 1)] for label, s in ft.entries],
    )
    positions = ReportTable(
        title="Frame positions",
        columns=["Frame", "x (mm)"],
        rows=[[label, round(x, 1)] for label, x in ft.positions],
    )
    section = ReportSection(
        title="Frame table",
        intro=(
            f"Frame 0 offset: {round(ft.frame0_offset_mm, 1)} mm — "
            f"{len(ft.positions)} frames"
        ),
        tables=[spacing, positions],
        notes=list(ft.warnings),
    )
    return Report(title=_TITLE, metadata=metadata, sections=[section])
