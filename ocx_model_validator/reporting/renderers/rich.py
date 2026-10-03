"""Rich terminal renderer for Report objects."""
from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ocx_model_validator.reporting.model import Cell, Link, Report, ReportSection

_NA = ""


def _cell(c: Cell) -> str:
    if isinstance(c, Link):
        c = c.text
    return _NA if c is None else str(c)


class RichRenderer:
    """Renders a Report as Rich tables (terminal output)."""

    def render(self, report: Report) -> str:
        console = Console(record=True, width=120)
        self.render_to_console(report, console)
        return console.export_text()

    def render_to_console(self, report: Report, console: Console) -> None:
        console.print(f"[bold underline]{escape(report.title)}[/]")
        for key, value in report.metadata.items():
            console.print(f"[bold]{escape(key)}:[/] {escape(str(value))}")
        for section in report.sections:
            self._render_section(section, console)

    def _render_section(self, section: ReportSection, console: Console) -> None:
        console.print(f"\n[bold]{escape(section.title)}[/]")
        if section.intro:
            console.print(escape(section.intro))
        for t in section.tables:
            table = Table(title=escape(t.title))
            for col in t.columns:
                table.add_column(escape(col))
            if not t.rows and not t.footer_rows:
                table.add_row("(empty)", *[""] * (len(t.columns) - 1))
            for i, row in enumerate(t.rows):
                children = t.row_children[i] if i < len(t.row_children) else []
                if children:  # group rows stand out in bold
                    table.add_row(*[f"[bold]{escape(_cell(c))}[/]" for c in row])
                else:
                    table.add_row(*[escape(_cell(c)) for c in row])
                for child in children:
                    table.add_row(*[f"[dim]{escape(_cell(c))}[/]" for c in child])
            for row in t.footer_rows:
                table.add_row(*[f"[bold]{escape(_cell(c))}[/]" for c in row])
            console.print(table)
        for note in section.notes:
            console.print(f"[yellow]Note:[/] {escape(note)}")
