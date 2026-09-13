"""Rich terminal renderer for Report objects."""
from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ocx_model_validator.reporting.model import Cell, Report, ReportSection

_NA = "N/A"


def _cell(c: Cell) -> str:
    return _NA if c is None else str(c)


class RichRenderer:
    """Renders a Report as Rich tables (terminal output)."""

    def render(self, report: Report) -> str:
        console = Console(record=True, width=120)
        self.render_to_console(report, console)
        return console.export_text()

    def render_to_console(self, report: Report, console: Console) -> None:
        console.print(f"[bold underline]{report.title}[/]")
        for key, value in report.metadata.items():
            console.print(f"[bold]{key}:[/] {value}")
        for section in report.sections:
            self._render_section(section, console)

    def _render_section(self, section: ReportSection, console: Console) -> None:
        console.print(f"\n[bold]{section.title}[/]")
        if section.intro:
            console.print(section.intro)
        for t in section.tables:
            table = Table(title=t.title)
            for col in t.columns:
                table.add_column(escape(col))
            if not t.rows and not t.footer_rows:
                table.add_row("(empty)", *[""] * (len(t.columns) - 1))
            for row in t.rows:
                table.add_row(*[escape(_cell(c)) for c in row])
            for row in t.footer_rows:
                table.add_row(*[f"[bold]{escape(_cell(c))}[/]" for c in row])
            console.print(table)
        for note in section.notes:
            console.print(f"[yellow]Note:[/] {note}")
