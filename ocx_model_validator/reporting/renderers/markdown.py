"""Markdown renderer for Report objects."""
from __future__ import annotations

from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_NA = "N/A"


def _cell(c: Cell) -> str:
    return _NA if c is None else str(c)


def _table_lines(t: ReportTable) -> list[str]:
    lines = [f"### {t.title}", ""]
    lines.append("| " + " | ".join(t.columns) + " |")
    lines.append("|" + "---|" * len(t.columns))
    if not t.rows and not t.footer_rows:
        cells = ["(empty)"] + [""] * (len(t.columns) - 1)
        lines.append("| " + " | ".join(cells) + " |")
    for row in t.rows:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    for row in t.footer_rows:
        lines.append("| " + " | ".join(f"**{_cell(c)}**" for c in row) + " |")
    lines.append("")
    return lines


def _section_lines(section: ReportSection) -> list[str]:
    lines = [f"## {section.title}", ""]
    if section.intro:
        lines.extend([section.intro, ""])
    for t in section.tables:
        lines.extend(_table_lines(t))
    for note in section.notes:
        lines.append(f"> {note}")
    if section.notes:
        lines.append("")
    return lines


class MarkdownRenderer:
    """Renders a Report as a GitHub-flavoured Markdown document."""

    def render(self, report: Report) -> str:
        lines: list[str] = [f"# {report.title}", ""]
        for key, value in report.metadata.items():
            lines.append(f"- **{key}:** {value}")
        if report.metadata:
            lines.append("")
        for section in report.sections:
            lines.extend(_section_lines(section))
        return "\n".join(lines).rstrip("\n") + "\n"
