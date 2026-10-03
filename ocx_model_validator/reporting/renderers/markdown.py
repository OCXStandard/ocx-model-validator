"""Markdown renderer for Report objects."""
from __future__ import annotations

from ocx_model_validator.reporting.model import Cell, Link, Report, ReportSection, ReportTable

_NA = ""


def _escape(text: str) -> str:
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def _cell(c: Cell) -> str:
    if isinstance(c, Link):
        c = c.text
    return _NA if c is None else _escape(str(c))


def _table_lines(t: ReportTable) -> list[str]:
    lines = [f"### {t.title}", ""]
    lines.append("| " + " | ".join(_escape(col) for col in t.columns) + " |")
    lines.append("|" + "---|" * len(t.columns))
    if not t.rows and not t.footer_rows:
        cells = ["(empty)"] + [""] * (len(t.columns) - 1)
        lines.append("| " + " | ".join(cells) + " |")
    for i, row in enumerate(t.rows):
        children = t.row_children[i] if i < len(t.row_children) else []
        cells = [_cell(c) for c in row]
        if children:  # group rows stand out in bold
            cells = [f"**{c}**" if c and c != _NA else c for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
        for child in children:
            lines.append("| " + " | ".join(_cell(c) for c in child) + " |")
    for row in t.footer_rows:
        cells = []
        for c in row:
            cell_text = _cell(c)
            cells.append(f"**{cell_text}**" if cell_text and cell_text != _NA else cell_text)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _section_lines(section: ReportSection) -> list[str]:
    lines = [f"## {section.title}", ""]
    if section.intro:
        lines.extend([section.intro, ""])
    for t in section.tables:
        lines.extend(_table_lines(t))
    for note in section.notes:
        for note_line in note.split("\n"):
            lines.append(f"> {note_line}")
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
