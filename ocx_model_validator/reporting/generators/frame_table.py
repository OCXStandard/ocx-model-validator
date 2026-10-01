"""Frame table report generator — reuses build_frame_table."""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.frame_table import build_frame_table
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable

_TITLE = "Frame table report"


def build(vessel: IrVessel, source_file: str = "") -> Report:
    metadata = report_metadata(vessel, source_file)
    try:
        ft = build_frame_table(vessel)
    except (GeometryError, SectionError) as exc:
        section = ReportSection(
            title="Frame table",
            tables=[ReportTable("Frame positions",
                                ["#", "Frame", "Name", "x (mm)", "Display grid"], [])],
            notes=[str(exc)],
        )
        return Report(title=_TITLE, metadata=metadata, sections=[section])

    spacing = ReportTable(
        title="Spacing entries",
        columns=["From frame", "Name", "x (mm)", "Spacing (mm)"],
        rows=[[r.label, r.name or "", round(r.x_mm, 1), round(s, 1)]
              for r, s in ft.spacing_rows],
    )

    # Missing displayGrid defaults to true (attribute absent in pre-3.1.0 schemas)
    def _is_grid(display_grid: bool | None) -> bool:
        return display_grid is not False

    counter = 0
    position_rows: list[list] = []
    for f in ft.frames:
        if _is_grid(f.display_grid):
            counter += 1
            num: int | str = counter
        else:
            num = ""
        position_rows.append([num, f.label, f.name or "", round(f.x_mm, 1),
                              "yes" if _is_grid(f.display_grid) else "no"])
    positions = ReportTable(
        title="Frame positions",
        columns=["#", "Frame", "Name", "x (mm)", "Display grid"],
        rows=position_rows,
    )
    frame0 = next((f for f in ft.frames if f.x_mm == ft.frame0_offset_mm), None)
    frame0_name = f" (frame {frame0.name or frame0.label})" if frame0 else ""
    section = ReportSection(
        title="Frame table",
        intro=(
            f"Frame 0 offset: {round(ft.frame0_offset_mm, 1)} mm{frame0_name} — "
            f"{counter} frames"
        ),
        tables=[spacing, positions],
        notes=list(ft.warnings),
    )
    return Report(title=_TITLE, metadata=metadata, sections=[section])
