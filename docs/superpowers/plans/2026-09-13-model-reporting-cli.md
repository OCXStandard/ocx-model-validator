# Model Reporting CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `validator report` subcommands (frame-table, compartments, catalogues, bom, all) that render IR-based reports through pluggable renderers (Rich terminal + Markdown file).

**Architecture:** Report generators produce a neutral `Report` dataclass (title, metadata, sections of tables); renderers implement a `ReportRenderer` protocol and never see IR objects. The CLI is restructured into subcommands (`report` sub-app + `generate-stubs`).

**Tech Stack:** Python ≥3.12, typer, rich, loguru, pytest (`uv run pytest`). Spec: `docs/superpowers/specs/2026-09-13-model-reporting-cli-design.md`.

**Conventions for the implementer:**
- Run every command from the repo root. Tests: `uv run pytest tests/<file>.py -v` (pytest config already deselects `integration`).
- All logging via `from loguru import logger` — never `print()` or stdlib `logging`.
- `ocx_model_validator/exeptions.py` (intentional typo) holds `SectionError` and `GeometryError` — both subclass `XmlParserError`.
- IR quantities are `Quantity(value, unit)` where `unit` is an OCX unit id (`"Umm"`, `"Ut"`, …). `ocx_model_validator.sections.units.to_si(qty, registry)` converts to SI (raises `GeometryError` for unknown units) and has a built-in fallback table covering `""`, `Um`, `Umm`, `Ucm`, `Um3`, `UPa`, `UMPa`, `UKg`, `Ut` — so tests can pass `registry={}` when using those unit ids.
- `IrVessel` is a plain (non-frozen) dataclass with all-default fields except `id` — tests construct it directly.

---

### Task 1: Report data model

**Files:**
- Create: `ocx_model_validator/reporting/__init__.py`
- Create: `ocx_model_validator/reporting/model.py`
- Test: `tests/test_reporting_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_reporting_model.py`:

```python
"""Tests for the neutral report data model."""
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable


def test_report_table_defaults():
    t = ReportTable(title="T", columns=["A", "B"], rows=[["x", 1]])
    assert t.footer_rows == []
    assert t.rows[0] == ["x", 1]


def test_report_defaults():
    r = Report(title="R")
    assert r.metadata == {}
    assert r.sections == []


def test_section_defaults():
    s = ReportSection(title="S")
    assert s.intro is None
    assert s.tables == []
    assert s.notes == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reporting_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocx_model_validator.reporting'`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/__init__.py`:

```python
"""Model reporting — neutral report model, generators and renderers."""
```

Create `ocx_model_validator/reporting/model.py`:

```python
"""Neutral report data model consumed by renderers.

Cells are plain scalars with units already resolved by the generators.
Renderers never see IR objects or Quantity values. ``None`` renders as N/A.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Cell = str | int | float | None


@dataclass(frozen=True)
class ReportTable:
    """A single table: column headers plus rows of pre-formatted cells."""
    title: str
    columns: list[str]
    rows: list[list[Cell]]
    footer_rows: list[list[Cell]] = field(default_factory=list)  # totals, styled bold


@dataclass(frozen=True)
class ReportSection:
    """A titled group of tables with optional intro text and notes."""
    title: str
    intro: str | None = None
    tables: list[ReportTable] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    """Root report object: title, metadata key/values, and sections."""
    title: str
    metadata: dict[str, str] = field(default_factory=dict)
    sections: list[ReportSection] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reporting_model.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting tests/test_reporting_model.py
git commit -m "feat(reporting): add neutral report data model"
```

---

### Task 2: Markdown renderer

**Files:**
- Create: `ocx_model_validator/reporting/renderers/__init__.py`
- Create: `ocx_model_validator/reporting/renderers/base.py`
- Create: `ocx_model_validator/reporting/renderers/markdown.py`
- Test: `tests/test_reporting_renderers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reporting_renderers.py`:

```python
"""Tests for report renderers."""
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer


def _sample_report() -> Report:
    table = ReportTable(
        title="Parts",
        columns=["Id", "Weight (t)"],
        rows=[["P1", 1.5], ["P2", None]],
        footer_rows=[["Total", 1.5]],
    )
    section = ReportSection(title="BOM", intro="Grouped by material.",
                            tables=[table], notes=["1 item missing weight"])
    return Report(title="Test report",
                  metadata={"Vessel": "MV Test", "Schema version": "3.1.0"},
                  sections=[section])


def test_markdown_full_document():
    out = MarkdownRenderer().render(_sample_report())
    assert out == (
        "# Test report\n"
        "\n"
        "- **Vessel:** MV Test\n"
        "- **Schema version:** 3.1.0\n"
        "\n"
        "## BOM\n"
        "\n"
        "Grouped by material.\n"
        "\n"
        "### Parts\n"
        "\n"
        "| Id | Weight (t) |\n"
        "|---|---|\n"
        "| P1 | 1.5 |\n"
        "| P2 | N/A |\n"
        "| **Total** | **1.5** |\n"
        "\n"
        "> 1 item missing weight\n"
    )


def test_markdown_empty_table_renders_empty_marker():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[ReportTable("T", ["A", "B"], [])])
    ])
    out = MarkdownRenderer().render(report)
    assert "| (empty) |  |" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_renderers.py -v`
Expected: FAIL — `ModuleNotFoundError` on `renderers.markdown`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/renderers/__init__.py` (registry filled in Task 3):

```python
"""Report renderers."""
```

Create `ocx_model_validator/reporting/renderers/base.py`:

```python
"""Renderer protocol — all renderers turn a Report into a string."""
from __future__ import annotations

from typing import Protocol

from ocx_model_validator.reporting.model import Report


class ReportRenderer(Protocol):
    def render(self, report: Report) -> str:
        """Render the full report to a string."""
        ...
```

Create `ocx_model_validator/reporting/renderers/markdown.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_renderers.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/renderers tests/test_reporting_renderers.py
git commit -m "feat(reporting): add Markdown renderer"
```

---

### Task 3: Rich renderer and renderer registry

**Files:**
- Modify: `pyproject.toml` (add `rich` dependency)
- Create: `ocx_model_validator/reporting/renderers/rich.py`
- Modify: `ocx_model_validator/reporting/renderers/__init__.py`
- Test: `tests/test_reporting_renderers.py` (append)

- [ ] **Step 1: Add the rich dependency**

Run: `uv add "rich>=13"`
Expected: `pyproject.toml` `[project.dependencies]` gains `"rich>=13"` and `uv.lock` updates. (rich is already an indirect dep of typer; this makes the direct import explicit.)

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_reporting_renderers.py`:

```python
import pytest

from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer


def test_rich_renderer_smoke():
    out = RichRenderer().render(_sample_report())
    assert "Test report" in out
    assert "P1" in out
    assert "N/A" in out
    assert "Total" in out


def test_get_renderer_dispatch():
    assert isinstance(get_renderer("markdown").render(_sample_report()), str)
    assert isinstance(get_renderer("rich"), RichRenderer)


def test_get_renderer_unknown_format():
    with pytest.raises(ValueError, match="markdown, rich"):
        get_renderer("pdf")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_renderers.py -v`
Expected: new tests FAIL — `ImportError: cannot import name 'get_renderer'`

- [ ] **Step 4: Write the implementation**

Create `ocx_model_validator/reporting/renderers/rich.py`:

```python
"""Rich terminal renderer for Report objects."""
from __future__ import annotations

from rich.console import Console
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
                table.add_column(col)
            if not t.rows and not t.footer_rows:
                table.add_row("(empty)", *[""] * (len(t.columns) - 1))
            for row in t.rows:
                table.add_row(*[_cell(c) for c in row])
            for row in t.footer_rows:
                table.add_row(*[f"[bold]{_cell(c)}[/]" for c in row])
            console.print(table)
        for note in section.notes:
            console.print(f"[yellow]Note:[/] {note}")
```

Replace the content of `ocx_model_validator/reporting/renderers/__init__.py` with:

```python
"""Report renderers — registry and public API."""
from __future__ import annotations

from ocx_model_validator.reporting.renderers.base import ReportRenderer
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer

_RENDERERS: dict[str, type] = {
    "markdown": MarkdownRenderer,
    "rich": RichRenderer,
}


def get_renderer(fmt: str) -> ReportRenderer:
    """Return a renderer instance for ``fmt``; raise ValueError if unknown."""
    try:
        return _RENDERERS[fmt]()
    except KeyError:
        supported = ", ".join(sorted(_RENDERERS))
        raise ValueError(f"Unknown report format {fmt!r}; supported: {supported}") from None


__all__ = ["ReportRenderer", "MarkdownRenderer", "RichRenderer", "get_renderer"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_renderers.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock ocx_model_validator/reporting/renderers tests/test_reporting_renderers.py
git commit -m "feat(reporting): add Rich renderer and renderer registry"
```

---

### Task 4: Shared generator helpers

**Files:**
- Create: `ocx_model_validator/reporting/generators/__init__.py`
- Create: `ocx_model_validator/reporting/generators/_common.py`
- Test: `tests/test_reporting_generators.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reporting_generators.py`:

```python
"""Tests for report generators."""
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_mpa_cell,
    qty_tonnes_cell,
    report_metadata,
)
from ocx_model_validator.model.ir.structural import IrVessel


def test_qty_mm_cell_converts():
    notes: list[str] = []
    assert qty_mm_cell(Quantity(0.5, "Um"), {}, notes, "x") == 500.0
    assert notes == []


def test_qty_cell_none_passthrough():
    notes: list[str] = []
    assert qty_mm_cell(None, {}, notes, "x") is None
    assert notes == []


def test_qty_cell_unknown_unit_falls_back_to_raw():
    notes: list[str] = []
    cell = qty_mm_cell(Quantity(12.5, "Ubogus"), {}, notes, "plate P1 thickness")
    assert cell == "12.5 Ubogus"
    assert notes == ["plate P1 thickness: unknown unit 'Ubogus'; raw value shown"]


def test_qty_mpa_cell_is_integer():
    notes: list[str] = []
    assert qty_mpa_cell(Quantity(235.0, "UMPa"), {}, notes, "x") == 235


def test_qty_tonnes_cell():
    notes: list[str] = []
    assert qty_tonnes_cell(Quantity(1500.0, "UKg"), {}, notes, "x") == 1.5


def test_report_metadata():
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    md = report_metadata(vessel, "model.3docx")
    assert md["Vessel"] == "MV Test"
    assert md["Schema version"] == "3.1.0"
    assert md["Source"] == "model.3docx"
    assert "Generated" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: FAIL — `ModuleNotFoundError` on `generators._common`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/generators/__init__.py`:

```python
"""Report generators — each builds a Report from an IrVessel."""
```

Create `ocx_model_validator/reporting/generators/_common.py`:

```python
"""Shared unit-conversion and formatting helpers for report generators.

All helpers degrade gracefully: missing quantities become None (rendered as
N/A) and unknown units become a raw ``"<value> <unit>"`` string plus a note —
generators never raise on bad units.
"""
from __future__ import annotations

from datetime import datetime

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.model import Cell
from ocx_model_validator.sections.units import to_si


def _safe_convert(
    qty: Quantity | None,
    registry: dict[str, IrUnit],
    si_scale: float,
    digits: int,
    notes: list[str],
    context: str,
) -> Cell:
    if qty is None:
        return None
    try:
        return round(to_si(qty, registry) * si_scale, digits)
    except GeometryError:
        notes.append(f"{context}: unknown unit {qty.unit!r}; raw value shown")
        return f"{qty.value} {qty.unit}"


def qty_mm_cell(qty, registry, notes, context) -> Cell:
    """SI metres → mm, 1 decimal."""
    return _safe_convert(qty, registry, 1e3, 1, notes, context)


def qty_mpa_cell(qty, registry, notes, context) -> Cell:
    """SI Pa → MPa, integer."""
    cell = _safe_convert(qty, registry, 1e-6, 0, notes, context)
    return int(cell) if isinstance(cell, float) else cell


def qty_m3_cell(qty, registry, notes, context) -> Cell:
    """SI m³ → m³, 2 decimals."""
    return _safe_convert(qty, registry, 1.0, 2, notes, context)


def qty_tonnes_cell(qty, registry, notes, context) -> Cell:
    """SI kg → tonnes, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def qty_t_per_m3_cell(qty, registry, notes, context) -> Cell:
    """SI kg/m³ → t/m³, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def report_metadata(vessel: IrVessel, source_file: str) -> dict[str, str]:
    """Standard report metadata block."""
    return {
        "Vessel": vessel.name or vessel.id,
        "Schema version": vessel.schema_version,
        "Source": source_file,
        "Generated": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators tests/test_reporting_generators.py
git commit -m "feat(reporting): add shared generator unit helpers"
```

---

### Task 5: Frame table generator

**Files:**
- Create: `ocx_model_validator/reporting/generators/frame_table.py`
- Test: `tests/test_reporting_generators.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_generators.py`:

```python
from ocx_model_validator.model.ir.geometry import IrRefPlane
from ocx_model_validator.reporting.generators import frame_table as frame_table_gen


def _vessel_with_frames() -> IrVessel:
    # IrRefPlane fields: id, name, guidref, location (Quantity), axis ("X"|"Y"|"Z")
    # Check ocx_model_validator/model/ir/geometry.py:173 for the exact signature
    # before writing this helper — adjust field names if they differ.
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    for i, x in enumerate([0.0, 0.8, 1.6]):
        rp = IrRefPlane(id=f"FR{i}", name=f"FR{i}", location=Quantity(x, "Um"), axis="X")
        vessel.ref_planes[rp.id] = rp
    return vessel


def test_frame_table_report():
    report = frame_table_gen.build(_vessel_with_frames(), source_file="m.3docx")
    assert report.title == "Frame table report"
    section = report.sections[0]
    titles = [t.title for t in section.tables]
    assert titles == ["Spacing entries", "Frame positions"]
    positions = section.tables[1]
    assert positions.columns == ["Frame", "x (mm)"]
    assert positions.rows == [["FR0", 0.0], ["FR1", 800.0], ["FR2", 1600.0]]


def test_frame_table_report_empty_model():
    report = frame_table_gen.build(IrVessel(id="V1"), source_file="m.3docx")
    section = report.sections[0]
    assert section.tables[0].rows == []
    assert any("reference planes" in n for n in section.notes)
```

**Important:** before finalising the `_vessel_with_frames` helper, open
`ocx_model_validator/model/ir/geometry.py` line ~173 and
`ocx_model_validator/sections/frame_table.py` `_x_ref_plane_ids` to confirm how
X ref planes are identified (field names / axis detection), and adapt the stub
so `build_frame_table` finds the planes. The assertion values stay the same.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: new tests FAIL — no module `generators.frame_table`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/generators/frame_table.py`:

```python
"""Frame table report generator — reuses sections.build_frame_table."""
from __future__ import annotations

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import report_metadata
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable
from ocx_model_validator.sections.frame_table import build_frame_table

_TITLE = "Frame table report"


def build(vessel: IrVessel, source_file: str = "") -> Report:
    metadata = report_metadata(vessel, source_file)
    try:
        ft = build_frame_table(vessel)
    except SectionError as exc:
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
        intro=(f"Frame 0 offset: {round(ft.frame0_offset_mm, 1)} mm — "
               f"{len(ft.positions)} frames"),
        tables=[spacing, positions],
        notes=list(ft.warnings),
    )
    return Report(title=_TITLE, metadata=metadata, sections=[section])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators/frame_table.py tests/test_reporting_generators.py
git commit -m "feat(reporting): add frame table report generator"
```

---

### Task 6: Compartments generator

**Files:**
- Create: `ocx_model_validator/reporting/generators/compartments.py`
- Test: `tests/test_reporting_generators.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_generators.py`:

```python
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog
from ocx_model_validator.reporting.generators import compartments as compartments_gen


def test_compartments_report():
    vessel = IrVessel(id="V1", name="MV Test")
    vessel.compartments["C1"] = IrCompartment(
        id="C1", name="WB Tank 1", compartment_purpose="ballast",
        volume=Quantity(120.0, "Um3"), cog=IrCog(10.0, 0.0, 2.0, "Um"),
    )
    report = compartments_gen.build(vessel, source_file="m.3docx")
    table = report.sections[0].tables[0]
    assert table.columns[:4] == ["Name", "Tank type", "Volume (m³)", "COG x (mm)"]
    row = table.rows[0]
    assert row[0] == "WB Tank 1"
    assert row[1] == "BALLASTWATERTANK"
    assert row[2] == 120.0
    assert row[3] == 10000.0


def test_compartments_report_empty():
    report = compartments_gen.build(IrVessel(id="V1"), source_file="m.3docx")
    assert report.sections[0].tables[0].rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: new tests FAIL — no module `generators.compartments`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/generators/compartments.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators/compartments.py tests/test_reporting_generators.py
git commit -m "feat(reporting): add compartments report generator"
```

---

### Task 7: Catalogues generator

**Files:**
- Create: `ocx_model_validator/reporting/generators/catalogues.py`
- Test: `tests/test_reporting_generators.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_generators.py`:

```python
from ocx_model_validator.model.ir.catalogues import IrHole2D, IrHoleShapeCatalogue, IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection, IrTSection
from ocx_model_validator.reporting.generators import catalogues as catalogues_gen


def _vessel_with_catalogues() -> IrVessel:
    vessel = IrVessel(id="V1", name="MV Test")
    vessel.materials["M1"] = IrMaterial(
        id="M1", name="NV A36", grade="A36",
        density=Quantity(7850.0, ""),        # blank unit == already SI (kg/m³)
        yield_stress=Quantity(355.0, "UMPa"),
    )
    vessel.sections["S1"] = IrFlatBarSection(
        id="S1", name="FB200x20",
        height=Quantity(0.2, "Um"), width=Quantity(0.02, "Um"),
    )
    vessel.sections["S2"] = IrTSection(id="S2", name="T300")
    vessel.hole_shape_catalogue = IrHoleShapeCatalogue(
        id="H", name="Holes",
        holes={"H1": IrHole2D(id="H1", name="Manhole",
                              parametric={"length": 600, "width": 400})},
    )
    return vessel


def test_catalogues_report_all_sections():
    report = catalogues_gen.build(_vessel_with_catalogues(), source_file="m.3docx")
    assert [s.title for s in report.sections] == ["Materials", "Cross sections", "Openings"]


def test_catalogues_materials_table():
    report = catalogues_gen.build(_vessel_with_catalogues())
    table = report.sections[0].tables[0]
    assert table.columns == ["Id", "Name", "Grade", "Density (t/m³)",
                             "Yield (MPa)", "Ultimate (MPa)", "E (MPa)"]
    assert table.rows[0] == ["M1", "NV A36", "A36", 7.85, 355, None, None]


def test_catalogues_sections_table_union_columns():
    report = catalogues_gen.build(_vessel_with_catalogues())
    table = report.sections[1].tables[0]
    assert table.columns[:3] == ["Id", "Name", "Type"]
    assert "height (mm)" in table.columns
    fb_row = next(r for r in table.rows if r[0] == "S1")
    assert fb_row[table.columns.index("height (mm)")] == 200.0


def test_catalogues_filter_material_only():
    report = catalogues_gen.build(_vessel_with_catalogues(), which="material")
    assert [s.title for s in report.sections] == ["Materials"]


def test_catalogues_no_hole_catalogue():
    report = catalogues_gen.build(IrVessel(id="V1"), which="opening")
    section = report.sections[0]
    assert section.tables[0].rows == []
    assert any("hole shape catalogue" in n.lower() for n in section.notes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: new tests FAIL — no module `generators.catalogues`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/generators/catalogues.py`:

```python
"""Catalogue report generator — materials, cross sections, openings."""
from __future__ import annotations

import dataclasses

from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_mpa_cell,
    qty_t_per_m3_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

# Non-dimension fields on IrSection subclasses (see model/ir/sections.py)
_SECTION_BASE_FIELDS = {"id", "name", "guidref", "section_type"}


def _materials_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for m in sorted(vessel.materials.values(), key=lambda m: m.name or m.id):
        ctx = f"material {m.id}"
        rows.append([
            m.id, m.name, m.grade,
            qty_t_per_m3_cell(m.density, reg, notes, f"{ctx} density"),
            qty_mpa_cell(m.yield_stress, reg, notes, f"{ctx} yield"),
            qty_mpa_cell(m.ultimate_stress, reg, notes, f"{ctx} ultimate"),
            qty_mpa_cell(m.youngs_modulus, reg, notes, f"{ctx} E"),
        ])
    columns = ["Id", "Name", "Grade", "Density (t/m³)",
               "Yield (MPa)", "Ultimate (MPa)", "E (MPa)"]
    return ReportSection(title="Materials",
                         tables=[ReportTable("Materials", columns, rows)],
                         notes=notes)


def _section_type_name(section) -> str:
    if section.section_type:
        return section.section_type
    return type(section).__name__.removeprefix("Ir").removesuffix("Section")


def _sections_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    reg = vessel.unit_registry
    secs = sorted(vessel.sections.values(), key=lambda s: s.name or s.id)
    dim_names = sorted({
        f.name for s in secs for f in dataclasses.fields(s)
        if f.name not in _SECTION_BASE_FIELDS
    })
    columns = ["Id", "Name", "Type"] + [f"{n} (mm)" for n in dim_names]
    rows: list[list[Cell]] = []
    for s in secs:
        row: list[Cell] = [s.id, s.name, _section_type_name(s)]
        for n in dim_names:
            row.append(qty_mm_cell(getattr(s, n, None), reg, notes,
                                   f"section {s.id} {n}"))
        rows.append(row)
    return ReportSection(title="Cross sections",
                         tables=[ReportTable("Cross sections", columns, rows)],
                         notes=notes)


def _openings_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    rows: list[list[Cell]] = []
    cat = vessel.hole_shape_catalogue
    if cat is None:
        notes.append("Model has no hole shape catalogue")
    else:
        for h in sorted(cat.holes.values(), key=lambda h: h.name or h.id):
            parametric = "; ".join(f"{k}={v}" for k, v in (h.parametric or {}).items())
            rows.append([h.id, h.name, parametric or None])
    return ReportSection(title="Openings",
                         tables=[ReportTable("Hole shapes",
                                             ["Id", "Name", "Parametric dimensions"],
                                             rows)],
                         notes=notes)


def build(vessel: IrVessel, which: str = "all", source_file: str = "") -> Report:
    """Build the catalogue report. ``which``: material|section|opening|all."""
    builders = {
        "material": _materials_section,
        "section": _sections_section,
        "opening": _openings_section,
    }
    keys = list(builders) if which == "all" else [which]
    sections = [builders[k](vessel) for k in keys]
    return Report(title="Catalogue report",
                  metadata=report_metadata(vessel, source_file),
                  sections=sections)
```

Note: `bulb_angle` on `IrBulbFlatSection` is an angle, not a length — the
`qty_mm_cell` fallback renders it as a raw `"value unit"` string with a note,
which is the accepted graceful degradation from the spec.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_generators.py -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators/catalogues.py tests/test_reporting_generators.py
git commit -m "feat(reporting): add catalogues report generator"
```

---

### Task 8: BOM generator — summary mode

**Files:**
- Create: `ocx_model_validator/reporting/generators/bom.py`
- Test: `tests/test_reporting_bom.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reporting_bom.py`:

```python
"""Tests for the bill-of-material report generator."""
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import (
    IrPlate,
    IrStiffener,
    IrVessel,
)
from ocx_model_validator.reporting.generators import bom as bom_gen

_PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    v.plates["P1"] = IrPlate(id="P1", parent_ref=_PARENT, name="P1",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             dry_weight=Quantity(1000.0, "UKg"))
    v.plates["P2"] = IrPlate(id="P2", parent_ref=_PARENT, name="P2",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             dry_weight=Quantity(500.0, "UKg"))
    v.plates["P3"] = IrPlate(id="P3", parent_ref=_PARENT, name="P3",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"))  # no weight
    v.stiffeners["ST1"] = IrStiffener(id="ST1", parent_ref=_PARENT, name="ST1",
                                      material_ref=Ref("M1"),
                                      section_ref=Ref("S1"),
                                      dry_weight=Quantity(250.0, "UKg"))
    v.plates["P4"] = IrPlate(id="P4", parent_ref=_PARENT, name="P4",
                             thickness=Quantity(12.0, "Umm"),
                             dry_weight=Quantity(2000.0, "UKg"))  # no material
    return v


def test_bom_summary_grouping_and_totals():
    report = bom_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.columns == ["Material", "Part type", "Group", "Count",
                             "Weight (t)", "Missing weight"]
    # Sorted: "(no material)" < "NV A36"
    assert table.rows == [
        ["(no material)", "Plate", "t=12.0 mm", 1, 2.0, 0],
        ["Subtotal — (no material)", None, None, 1, 2.0, 0],
        ["NV A36", "Plate", "t=10.0 mm", 3, 1.5, 1],
        ["NV A36", "Stiffener", "FB200x20", 1, 0.25, 0],
        ["Subtotal — NV A36", None, None, 4, 1.75, 1],
    ]
    assert table.footer_rows == [["Grand total", None, None, 5, 3.75, 1]]
    assert any("1 item" in n and "missing" in n for n in report.sections[0].notes)


def test_bom_summary_has_no_items_table():
    report = bom_gen.build(_vessel())
    assert [t.title for t in report.sections[0].tables] == ["Summary"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_bom.py -v`
Expected: FAIL — no module `generators.bom`

- [ ] **Step 3: Write the implementation**

Create `ocx_model_validator/reporting/generators/bom.py`:

```python
"""Bill-of-material report generator.

Grouping hierarchy: material → part type → sub-group (thickness for plates
and brackets, cross-section for stiffeners and edge reinforcements). Items
without dry_weight show N/A, are excluded from totals, and are counted per
group in the "Missing weight" column.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable
from ocx_model_validator.sections.units import to_si

_NO_MATERIAL = "(no material)"
_NO_SECTION = "(no section)"

# (display name, IrVessel dict attribute, sub-group kind)
_PART_TYPES = [
    ("Plate", "plates", "thickness"),
    ("Stiffener", "stiffeners", "section"),
    ("Edge reinforcement", "edge_reinforcements", "section"),
    ("Bracket", "brackets", "thickness"),
]


@dataclass
class _Group:
    count: int = 0
    weight_t: float = 0.0
    missing: int = 0
    items: list[tuple[str, str | None, float | None]] = field(default_factory=list)
    # items: (id, name, weight_t or None)


def _material_name(part, vessel: IrVessel) -> str:
    ref = part.material_ref
    if ref is None:
        return _NO_MATERIAL
    m = vessel.materials.get(ref.local_ref)
    if m is None:
        return _NO_MATERIAL
    return m.name or m.grade or m.id


def _group_key(part, kind: str, vessel: IrVessel, notes: list[str]) -> str:
    if kind == "thickness":
        mm = qty_mm_cell(part.thickness, vessel.unit_registry, notes,
                         f"{part.id} thickness")
        return f"t={mm} mm" if mm is not None else "t=N/A"
    ref = part.section_ref
    if ref is None:
        return _NO_SECTION
    s = vessel.sections.get(ref.local_ref)
    return (s.name or s.id) if s is not None else ref.local_ref


def _weight_tonnes(part, vessel: IrVessel) -> float | None:
    if part.dry_weight is None:
        return None
    try:
        return to_si(part.dry_weight, vessel.unit_registry) / 1000.0
    except GeometryError:
        return None


def build(vessel: IrVessel, detailed: bool = False, source_file: str = "") -> Report:
    notes: list[str] = []
    groups: dict[tuple[str, str, str], _Group] = {}

    for part_type, attr, kind in _PART_TYPES:
        for part in getattr(vessel, attr).values():
            key = (_material_name(part, vessel), part_type,
                   _group_key(part, kind, vessel, notes))
            g = groups.setdefault(key, _Group())
            w = _weight_tonnes(part, vessel)
            g.count += 1
            if w is None:
                g.missing += 1
            else:
                g.weight_t += w
            g.items.append((part.id, part.name, w))

    rows: list[list[Cell]] = []
    total_count = total_weight = total_missing = 0
    current_material: str | None = None
    sub_count = sub_weight = sub_missing = 0

    def _flush_subtotal() -> None:
        if current_material is not None:
            rows.append([f"Subtotal — {current_material}", None, None,
                         sub_count, round(sub_weight, 3), sub_missing])

    for (material, part_type, group), g in sorted(groups.items()):
        if material != current_material:
            _flush_subtotal()
            current_material = material
            sub_count = sub_weight = sub_missing = 0
        rows.append([material, part_type, group,
                     g.count, round(g.weight_t, 3), g.missing])
        sub_count += g.count
        sub_weight += g.weight_t
        sub_missing += g.missing
        total_count += g.count
        total_weight += g.weight_t
        total_missing += g.missing
    _flush_subtotal()

    if total_missing:
        notes.append(f"{total_missing} item(s) missing dry weight; "
                     f"excluded from all totals")

    summary = ReportTable(
        title="Summary",
        columns=["Material", "Part type", "Group", "Count",
                 "Weight (t)", "Missing weight"],
        rows=rows,
        footer_rows=[["Grand total", None, None,
                      total_count, round(total_weight, 3), total_missing]],
    )
    tables = [summary]

    if detailed:
        item_rows: list[list[Cell]] = []
        for (material, part_type, group), g in sorted(groups.items()):
            for item_id, name, w in sorted(g.items, key=lambda it: it[0]):
                item_rows.append([material, part_type, group, item_id, name,
                                  round(w, 3) if w is not None else None])
        tables.append(ReportTable(
            title="Items",
            columns=["Material", "Part type", "Group", "Id", "Name", "Weight (t)"],
            rows=item_rows,
        ))

    section = ReportSection(title="Bill of material", tables=tables, notes=notes)
    return Report(title="Bill of material report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_bom.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators/bom.py tests/test_reporting_bom.py
git commit -m "feat(reporting): add BOM report generator (summary mode)"
```

---

### Task 9: BOM generator — detailed mode

**Files:**
- Modify: `ocx_model_validator/reporting/generators/bom.py` (already supports `detailed`; this task verifies it)
- Test: `tests/test_reporting_bom.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_bom.py`:

```python
def test_bom_detailed_items_table():
    report = bom_gen.build(_vessel(), detailed=True)
    tables = report.sections[0].tables
    assert [t.title for t in tables] == ["Summary", "Items"]
    items = tables[1]
    assert items.columns == ["Material", "Part type", "Group", "Id", "Name", "Weight (t)"]
    p3_row = next(r for r in items.rows if r[3] == "P3")
    assert p3_row[5] is None  # missing weight renders N/A


def test_bom_detailed_item_count():
    report = bom_gen.build(_vessel(), detailed=True)
    assert len(report.sections[0].tables[1].rows) == 5
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_reporting_bom.py -v`
Expected: PASS if Task 8 implemented `detailed` correctly; if any FAIL, fix
`bom.py` until green (the summary-mode assertions from Task 8 must stay green).

- [ ] **Step 3: Commit**

```bash
git add tests/test_reporting_bom.py ocx_model_validator/reporting/generators/bom.py
git commit -m "test(reporting): cover BOM detailed mode"
```

---

### Task 10: CLI restructure — `generate-stubs` + `report frame-table`

**Files:**
- Modify: `ocx_model_validator/cli.py` (full rewrite)
- Test: `tests/test_cli_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_report.py`:

```python
"""CLI tests for the report subcommands (typer CliRunner)."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

runner = CliRunner()


@pytest.fixture()
def model_310(stub_dir_310: Path) -> Path:
    """A small real model file: the vessel stub for OCX 3.1.0."""
    return stub_dir_310 / "vessel.3docx"


def test_report_frame_table_rich_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310)])
    assert result.exit_code == 0
    assert "Frame table report" in result.output


def test_report_frame_table_markdown_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("# Frame table report")


def test_report_destination_writes_markdown(model_310: Path, tmp_path: Path):
    dest = tmp_path / "out.md"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("# Frame table report")


def test_report_destination_rejects_rich(model_310: Path, tmp_path: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "rich",
                                 "--destination", str(tmp_path / "x.md")])
    assert result.exit_code != 0


def test_report_missing_model_file():
    result = runner.invoke(app, ["report", "frame-table", "no_such.3docx"])
    assert result.exit_code != 0


def test_generate_stubs_command_exists():
    result = runner.invoke(app, ["generate-stubs", "--help"])
    assert result.exit_code == 0
```

**Note:** if `tests/data/ocx_310_stubs/vessel.3docx` does not exist, pick any
`.3docx` stub in `stub_dir_310` (e.g. `sorted(stub_dir_310.glob("*.3docx"))[0]`)
— the frame-table report must succeed even on a model with no ref planes
(empty table + note), so any stub works.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_report.py -v`
Expected: FAIL — no `report` command on the app

- [ ] **Step 3: Rewrite the CLI**

Replace the full content of `ocx_model_validator/cli.py` with:

```python
"""CLI entrypoint for ocx-model-validator.

Usage::

    validator report frame-table MODEL.3docx [--format rich|markdown] [--destination FILE]
    validator report compartments MODEL.3docx ...
    validator report catalogues MODEL.3docx [--catalogue material|section|opening|all] ...
    validator report bom MODEL.3docx [--detailed] ...
    validator report all MODEL.3docx ...
    validator generate-stubs [--force]
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from ocx_model_validator.reporting.model import Report
from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer

app = typer.Typer(
    name="validator",
    help="OCX model validator — tools for parsing, reporting and validating .3docx ship models.",
    no_args_is_help=True,
)
report_app = typer.Typer(help="Generate model reports.", no_args_is_help=True)
app.add_typer(report_app, name="report")


class ReportFormat(str, Enum):
    rich = "rich"
    markdown = "markdown"


_MODEL_ARG = typer.Argument(..., exists=True, readable=True,
                            help="Path to a .3docx model file.")
_FORMAT_OPT = typer.Option(None, "--format", "-f",
                           help="Output format (default: rich to stdout, "
                                "markdown with --destination).")
_DEST_OPT = typer.Option(None, "--destination", "-d",
                         help="Write the report to this file (Markdown).")


def _load_vessel(model: Path):
    """Parse and build the IR; exit code 1 on failure."""
    from ocx_model_validator.builders.factory import get_builder
    from ocx_model_validator.parsers.parser import OcxParser

    try:
        root = OcxParser().parse(str(model))
        builder = get_builder(root.schema_version)
        return builder.build(root)
    except Exception as exc:
        logger.error("Failed to parse/build {}: {}", model, exc)
        raise typer.Exit(code=1) from exc


def _emit(report: Report, fmt: ReportFormat | None, destination: Path | None) -> None:
    if destination is not None:
        if fmt == ReportFormat.rich:
            raise typer.BadParameter(
                "--destination cannot be combined with --format rich")
        try:
            destination.write_text(get_renderer("markdown").render(report),
                                   encoding="utf-8")
        except OSError as exc:
            logger.error("Cannot write {}: {}", destination, exc)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Report written to {destination}")
        return
    if fmt is None or fmt == ReportFormat.rich:
        RichRenderer().render_to_console(report, Console())
    else:
        typer.echo(get_renderer("markdown").render(report), nl=False)


@report_app.command("frame-table")
def frame_table_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Frame table: frame 0 offset, spacing entries and frame positions."""
    from ocx_model_validator.reporting.generators import frame_table

    vessel = _load_vessel(model)
    _emit(frame_table.build(vessel, source_file=str(model)), fmt, destination)


@app.command("generate-stubs")
def generate_stubs_cmd(
    force: bool = typer.Option(
        False, "--force",
        help="Delete existing stubs and regenerate all.", is_flag=True),
) -> None:
    """Generate XML test stubs from OCX models in ./models."""
    from ocx_model_validator.generate_stubs import main as generate_stubs

    generate_stubs(force=force)


def entrypoint() -> None:
    app()
```

**Breaking change (per spec):** the old `validator --generate [--force]` flags
are removed; `validator generate-stubs [--force]` replaces them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_report.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Run the full suite to catch regressions**

Run: `uv run pytest`
Expected: all PASS (no other test exercises the removed `--generate` flag; if
one does, update it to call `generate-stubs`).

- [ ] **Step 6: Update README CLI section**

In `README.md`, replace the `## CLI` code block:

````markdown
## CLI

```bash
# model reports (rich to stdout, or markdown to a file)
validator report frame-table  model.3docx
validator report compartments model.3docx
validator report catalogues   model.3docx --catalogue material
validator report bom          model.3docx --detailed
validator report all          model.3docx --destination report.md

# generate xsdata stubs from .3docx models in ./models/
validator generate-stubs

# wipe and regenerate all stubs
validator generate-stubs --force
```
````

Also update the two `validator --generate` mentions in
`.github/copilot-instructions.md` if present (search for `--generate`).

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/cli.py tests/test_cli_report.py README.md .github/copilot-instructions.md
git commit -m "feat(cli)!: restructure into report/generate-stubs subcommands"
```

---

### Task 11: Remaining report commands + `report all`

**Files:**
- Modify: `ocx_model_validator/cli.py`
- Test: `tests/test_cli_report.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_report.py`:

```python
def test_report_compartments(model_310: Path):
    result = runner.invoke(app, ["report", "compartments", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Compartments report" in result.output


def test_report_catalogues_filter(model_310: Path):
    result = runner.invoke(app, ["report", "catalogues", str(model_310),
                                 "--catalogue", "material",
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "## Materials" in result.output
    assert "## Cross sections" not in result.output


def test_report_bom_detailed(model_310: Path):
    result = runner.invoke(app, ["report", "bom", str(model_310),
                                 "--detailed", "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Bill of material report" in result.output
    assert "### Items" in result.output


def test_report_all(model_310: Path, tmp_path: Path):
    dest = tmp_path / "all.md"
    result = runner.invoke(app, ["report", "all", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("# Model report")
    for heading in ["## Frame table", "## Compartments", "## Materials",
                    "## Bill of material"]:
        assert heading in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_report.py -v`
Expected: new tests FAIL — commands not registered

- [ ] **Step 3: Add the commands**

Add to `ocx_model_validator/cli.py` (below `frame_table_cmd`):

```python
class CatalogueKind(str, Enum):
    material = "material"
    section = "section"
    opening = "opening"
    all = "all"


@report_app.command("compartments")
def compartments_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Compartments: name, tank type, volume, COG and extents."""
    from ocx_model_validator.reporting.generators import compartments

    vessel = _load_vessel(model)
    _emit(compartments.build(vessel, source_file=str(model)), fmt, destination)


@report_app.command("catalogues")
def catalogues_cmd(
    model: Path = _MODEL_ARG,
    catalogue: CatalogueKind = typer.Option(
        CatalogueKind.all, "--catalogue",
        help="Which catalogue to report."),
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Catalogues: materials, cross sections and openings."""
    from ocx_model_validator.reporting.generators import catalogues

    vessel = _load_vessel(model)
    _emit(catalogues.build(vessel, which=catalogue.value,
                           source_file=str(model)), fmt, destination)


@report_app.command("bom")
def bom_cmd(
    model: Path = _MODEL_ARG,
    detailed: bool = typer.Option(
        False, "--detailed",
        help="Add per-item rows below the summary.", is_flag=True),
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Bill of material grouped by material, with weights and totals."""
    from ocx_model_validator.reporting.generators import bom

    vessel = _load_vessel(model)
    _emit(bom.build(vessel, detailed=detailed, source_file=str(model)),
          fmt, destination)


@report_app.command("all")
def all_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """All reports merged into one document (report defaults; no per-report flags)."""
    from ocx_model_validator.reporting.generators import (
        bom,
        catalogues,
        compartments,
        frame_table,
    )

    vessel = _load_vessel(model)
    source = str(model)
    parts = [
        frame_table.build(vessel, source_file=source),
        compartments.build(vessel, source_file=source),
        catalogues.build(vessel, source_file=source),
        bom.build(vessel, source_file=source),
    ]
    merged = Report(
        title="Model report",
        metadata=parts[0].metadata,
        sections=[s for p in parts for s in p.sections],
    )
    _emit(merged, fmt, destination)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_report.py -v`
Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/cli.py tests/test_cli_report.py
git commit -m "feat(cli): add compartments, catalogues, bom and all report commands"
```

---

### Task 12: Integration test and final verification

**Files:**
- Create: `tests/test_integration_reports.py`

- [ ] **Step 1: Find how existing integration tests locate the VLCC model**

Run: `grep -rn "integration" tests/*.py | head -20`
Copy the model-path convention (fixture or hard-coded path) used by the
existing integration tests (e.g. `tests/test_integration_*.py`) so the new
test skips identically when the model is absent.

- [ ] **Step 2: Write the integration test**

Create `tests/test_integration_reports.py` (adapt the model fixture to
whatever Step 1 found — the pattern below assumes a `models/` file and skips
when missing):

```python
"""Integration test: BOM report against the real VLCC reference model."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

pytestmark = pytest.mark.integration

runner = CliRunner()

_MODEL_CANDIDATES = sorted(Path("models").glob("*.3docx"))


@pytest.mark.skipif(not _MODEL_CANDIDATES, reason="no reference model in ./models")
def test_bom_report_on_reference_model(tmp_path: Path):
    dest = tmp_path / "bom.md"
    result = runner.invoke(app, ["report", "bom", str(_MODEL_CANDIDATES[0]),
                                 "--detailed", "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert "### Summary" in text
    assert "### Items" in text
    assert "**Grand total**" in text
    # grand total weight must be positive: footer row like
    # | **Grand total** | ... | **<count>** | **<weight>** | ... |
    total_line = next(l for l in text.splitlines() if "Grand total" in l)
    weight = float(total_line.split("|")[5].strip().strip("*"))
    assert weight > 0
```

- [ ] **Step 3: Run the integration test (if a model is available)**

Run: `uv run pytest tests/test_integration_reports.py -m integration -v`
Expected: PASS (or SKIP with "no reference model" if `models/` is empty)

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: all PASS

- [ ] **Step 5: Manual smoke test of Rich output**

Run: `uv run validator report frame-table tests/data/ocx_310_stubs/vessel.3docx`
Expected: Rich-formatted tables in the terminal, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add tests/test_integration_reports.py
git commit -m "test(reporting): add BOM integration test against reference model"
```
