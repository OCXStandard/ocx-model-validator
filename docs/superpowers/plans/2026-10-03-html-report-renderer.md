# HTML Report Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an HTML renderer producing a single self-contained tabbed report document with working internal cross-links (BOM material/section names → their catalogue rows).

**Architecture:** Extend the neutral report model with a minimal `Link` cell type and per-row `row_anchors` on `ReportTable`. The BOM generator emits `Link` cells; the catalogues generator emits row anchors. A new `HtmlRenderer` (registered as `"html"`) renders one tab per section and resolves a `Link` to `<a href>` only when its target anchor exists in the report, degrading to plain text otherwise. Markdown/rich renderers degrade `Link` to its text. CLI gains `--format html` plus inference from a `.html`/`.htm` destination suffix.

**Tech Stack:** Python 3.12, dataclasses, stdlib `html.escape`, typer CLI, pytest. Run everything with `uv` from the repo root. Spec: `docs/superpowers/specs/2026-10-03-html-report-renderer-design.md`.

**Conventions:** loguru only (no print/logging) — though no logging is needed here; frozen dataclasses in the report model; renderers are pure (string in → string out, no I/O). Do NOT commit the untracked `scripts/` directory — always stage explicit paths. Every commit message ends with the trailer:

```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## File structure

| File | Change | Responsibility |
|---|---|---|
| `ocx_model_validator/reporting/model.py` | Modify | Add `Link` dataclass, widen `Cell`, add `ReportTable.row_anchors` |
| `ocx_model_validator/reporting/renderers/markdown.py` | Modify | `Link` → plain text |
| `ocx_model_validator/reporting/renderers/rich.py` | Modify | `Link` → plain text |
| `ocx_model_validator/reporting/renderers/html.py` | Create | Self-contained tabbed HTML document |
| `ocx_model_validator/reporting/renderers/__init__.py` | Modify | Register `"html"` |
| `ocx_model_validator/reporting/generators/catalogues.py` | Modify | Emit `row_anchors` for materials and cross-sections tables |
| `ocx_model_validator/reporting/generators/bom.py` | Modify | Emit `Link` cells for resolvable materials/sections |
| `ocx_model_validator/cli.py` | Modify | `ReportFormat.html`; destination-suffix inference |
| `tests/test_reporting_model.py` | Modify | Link/row_anchors model tests |
| `tests/test_reporting_renderers.py` | Modify | Link degradation tests |
| `tests/test_html_renderer.py` | Create | HTML renderer tests |
| `tests/test_reporting_links.py` | Create | Generator anchor/link tests |
| `tests/test_reporting_bom.py` | Modify | Update exact-row expectations to `Link` cells |
| `tests/test_cli_report.py` | Modify | html format/inference tests |
| `tests/test_integration_reports.py` | Modify | HTML smoke on reference model |

Anchor id convention: `material-<IR id>` and `section-<IR id>` (ids are the dict keys of `IrVessel.materials` / `IrVessel.sections`, unique per table).

---

### Task 1: Report model — `Link` cell and `row_anchors`

**Files:**
- Modify: `ocx_model_validator/reporting/model.py`
- Test: `tests/test_reporting_model.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_model.py` (and extend the existing import line to include `Link`):

```python
from ocx_model_validator.reporting.model import Link, Report, ReportSection, ReportTable


def test_link_cell():
    link = Link(text="NV A36", target="material-M1")
    assert link.text == "NV A36"
    assert link.target == "material-M1"
    t = ReportTable(title="T", columns=["A"], rows=[[link]])
    assert t.rows[0][0] is link


def test_report_table_row_anchors():
    t = ReportTable(title="T", columns=["A"], rows=[["x"], ["y"]],
                    row_anchors=["material-M1", None])
    assert t.row_anchors == ["material-M1", None]


def test_report_table_row_anchors_default_empty():
    t = ReportTable(title="T", columns=["A"], rows=[["x"]])
    assert t.row_anchors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_model.py -v`
Expected: FAIL / ERROR — `ImportError: cannot import name 'Link'`

- [ ] **Step 3: Implement**

In `ocx_model_validator/reporting/model.py`:

Replace the module docstring's second paragraph line "Renderers never see IR objects or Quantity values. ``None`` renders as N/A." with:

```python
"""Neutral report data model consumed by renderers.

Cells are plain scalars with units already resolved by the generators.
Renderers never see IR objects or Quantity values. ``None`` renders as N/A.
``Link`` cells are internal cross-references: ``target`` names a row anchor
(see ``ReportTable.row_anchors``); renderers that cannot link render the text.
"""
```

Replace:

```python
Cell = str | int | float | None
```

with:

```python
@dataclass(frozen=True)
class Link:
    """Internal cross-reference: display text plus a target anchor id (no '#')."""
    text: str
    target: str


Cell = str | int | float | Link | None
```

Add a field to `ReportTable` after `footer_rows`:

```python
    # Optional anchor id per row (parallel to ``rows``); shorter list = no
    # anchor for the remaining rows. Empty (default) = no anchors.
    row_anchors: list[str | None] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_model.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/model.py tests/test_reporting_model.py
git commit -m "feat(report-model): Link cell type and per-row anchors"
```

---

### Task 2: Markdown and rich renderers degrade `Link` to text

**Files:**
- Modify: `ocx_model_validator/reporting/renderers/markdown.py`
- Modify: `ocx_model_validator/reporting/renderers/rich.py`
- Test: `tests/test_reporting_renderers.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_renderers.py` (add `Link` to the existing `reporting.model` import):

```python
from ocx_model_validator.reporting.model import Link, Report, ReportSection, ReportTable


def _link_report() -> Report:
    return Report(title="R", sections=[
        ReportSection(title="S", tables=[
            ReportTable("T", ["Material"],
                        [[Link("NV A36", "material-M1")]])
        ])
    ])


def test_markdown_link_renders_as_plain_text():
    out = MarkdownRenderer().render(_link_report())
    assert "| NV A36 |" in out
    assert "material-M1" not in out


def test_rich_link_renders_as_plain_text():
    out = RichRenderer().render(_link_report())
    assert "NV A36" in out
    assert "material-M1" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_renderers.py -v -k link`
Expected: FAIL — cells render as `Link(text='NV A36', target='material-M1')`

- [ ] **Step 3: Implement**

In `markdown.py`, change the import and `_cell`:

```python
from ocx_model_validator.reporting.model import Cell, Link, Report, ReportSection, ReportTable
```

```python
def _cell(c: Cell) -> str:
    if isinstance(c, Link):
        c = c.text
    return _NA if c is None else _escape(str(c))
```

In `rich.py`, change the import and `_cell`:

```python
from ocx_model_validator.reporting.model import Cell, Link, Report, ReportSection
```

```python
def _cell(c: Cell) -> str:
    if isinstance(c, Link):
        c = c.text
    return _NA if c is None else str(c)
```

(`rich.py` currently imports `Report` unused by `_cell` — keep its existing imports, only add `Link`.)

- [ ] **Step 4: Run the renderer test file**

Run: `uv run pytest tests/test_reporting_renderers.py -v`
Expected: all PASS (existing tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/renderers/markdown.py ocx_model_validator/reporting/renderers/rich.py tests/test_reporting_renderers.py
git commit -m "feat(renderers): markdown and rich render Link cells as text"
```

---

### Task 3: HTML renderer

**Files:**
- Create: `ocx_model_validator/reporting/renderers/html.py`
- Modify: `ocx_model_validator/reporting/renderers/__init__.py`
- Test: `tests/test_html_renderer.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_html_renderer.py`:

```python
"""Tests for the self-contained tabbed HTML renderer."""
from ocx_model_validator.reporting.model import (
    Link,
    Report,
    ReportSection,
    ReportTable,
)
from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.html import HtmlRenderer


def _report() -> Report:
    bom = ReportSection(
        title="Bill of material",
        intro="Grouped by material.",
        tables=[ReportTable(
            title="Summary",
            columns=["Material", "Weight (t)"],
            rows=[[Link("NV A36", "material-M1"), 1.5],
                  [Link("Ghost", "material-MISSING"), None]],
            footer_rows=[["Grand total", 1.5]],
        )],
        notes=["1 item missing weight"],
    )
    materials = ReportSection(
        title="Materials",
        tables=[ReportTable(
            title="Materials",
            columns=["Id", "Name"],
            rows=[["M1", "NV A36"]],
            row_anchors=["material-M1"],
        )],
    )
    return Report(title="Model report",
                  metadata={"Vessel": "MV Test", "Schema version": "3.2.0"},
                  sections=[bom, materials])


def test_document_shell():
    out = HtmlRenderer().render(_report())
    assert out.startswith("<!DOCTYPE html>")
    assert "<title>Model report</title>" in out
    assert "<h1>Model report</h1>" in out
    assert "<style>" in out
    assert "<script>" in out


def test_metadata_definition_list():
    out = HtmlRenderer().render(_report())
    assert "<dt>Vessel</dt><dd>MV Test</dd>" in out
    assert "<dt>Schema version</dt><dd>3.2.0</dd>" in out


def test_one_tab_button_and_panel_per_section():
    out = HtmlRenderer().render(_report())
    assert out.count('data-tab="tab-') == 2
    assert '<button type="button" data-tab="tab-0">Bill of material</button>' in out
    assert '<button type="button" data-tab="tab-1">Materials</button>' in out
    assert '<section class="tab-panel" id="tab-0">' in out
    assert '<section class="tab-panel" id="tab-1">' in out


def test_resolved_link_renders_anchor():
    out = HtmlRenderer().render(_report())
    assert '<a href="#material-M1">NV A36</a>' in out


def test_unresolved_link_degrades_to_text():
    out = HtmlRenderer().render(_report())
    assert ">Ghost<" in out
    assert 'href="#material-MISSING"' not in out


def test_row_anchor_emitted_as_id():
    out = HtmlRenderer().render(_report())
    assert '<tr id="material-M1">' in out


def test_none_renders_na_and_footer_in_tfoot():
    out = HtmlRenderer().render(_report())
    assert "<td>N/A</td>" in out
    assert "<tfoot>" in out
    assert "<td>Grand total</td>" in out


def test_intro_and_notes():
    out = HtmlRenderer().render(_report())
    assert "<p>Grouped by material.</p>" in out
    assert '<aside class="note">1 item missing weight</aside>' in out


def test_empty_table_placeholder():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[ReportTable("T", ["A", "B"], [])])
    ])
    out = HtmlRenderer().render(report)
    assert "<td>(empty)</td><td></td>" in out


def test_html_escaping():
    report = Report(
        title="A <b>& title",
        metadata={"K<": "v&"},
        sections=[ReportSection(title="S <i>", tables=[
            ReportTable("T <x>", ["Col <y>"], [["val <z> & more"]])
        ])],
    )
    out = HtmlRenderer().render(report)
    assert "<b>" not in out
    assert "A &lt;b&gt;&amp; title" in out
    assert "val &lt;z&gt; &amp; more" in out


def test_registry_dispatch():
    assert isinstance(get_renderer("html"), HtmlRenderer)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_html_renderer.py -v`
Expected: ERROR — `ModuleNotFoundError: ocx_model_validator.reporting.renderers.html`

- [ ] **Step 3: Implement the renderer**

Create `ocx_model_validator/reporting/renderers/html.py`:

```python
"""HTML renderer — single self-contained tabbed document.

One tab per report section. ``Link`` cells render as in-page anchors when
their target row anchor exists anywhere in the report, and degrade to plain
text otherwise. Inline CSS/JS only; the file works offline from file://.
"""
from __future__ import annotations

import html

from ocx_model_validator.reporting.model import (
    Cell,
    Link,
    Report,
    ReportSection,
    ReportTable,
)

_NA = "N/A"

_CSS = """
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 2rem; color: #1f2328; }
h1 { margin-bottom: 0.25rem; }
dl.meta { display: grid; grid-template-columns: max-content auto;
  gap: 0.15rem 0.75rem; margin: 0.5rem 0 1.5rem; }
dl.meta dt { font-weight: 600; }
dl.meta dd { margin: 0; }
.tab-bar { display: flex; flex-wrap: wrap; gap: 0.25rem;
  border-bottom: 2px solid #d0d7de; margin-bottom: 1rem; }
.tab-bar button { border: 1px solid #d0d7de; border-bottom: none;
  background: #f6f8fa; padding: 0.4rem 0.9rem; cursor: pointer;
  border-radius: 6px 6px 0 0; font: inherit; }
.tab-bar button.active { background: #fff; font-weight: 600;
  border-color: #0969da; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
table { border-collapse: collapse; margin: 0.5rem 0 1.5rem; }
th, td { border: 1px solid #d0d7de; padding: 0.3rem 0.6rem; text-align: left; }
th { background: #f6f8fa; }
tfoot td { font-weight: 700; }
tr.highlight td { background: #fff8c5; }
aside.note { border-left: 4px solid #d4a72c; background: #fff8c5;
  padding: 0.4rem 0.8rem; margin: 0.5rem 0; }
"""

_JS = """
const buttons = document.querySelectorAll('.tab-bar button');
function activate(id) {
  document.querySelectorAll('.tab-panel').forEach(
    (p) => p.classList.toggle('active', p.id === id));
  buttons.forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
}
buttons.forEach((b) => b.addEventListener('click', () => activate(b.dataset.tab)));
if (buttons.length) activate(buttons[0].dataset.tab);
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const target = document.getElementById(
    decodeURIComponent(a.getAttribute('href').slice(1)));
  if (!target) return;
  const panel = target.closest('.tab-panel');
  if (panel) activate(panel.id);
  target.scrollIntoView();
  target.classList.add('highlight');
  setTimeout(() => target.classList.remove('highlight'), 1500);
  e.preventDefault();
});
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _collect_anchors(report: Report) -> set[str]:
    return {a for s in report.sections for t in s.tables
            for a in t.row_anchors if a}


def _cell_html(c: Cell, anchors: set[str]) -> str:
    if c is None:
        return _NA
    if isinstance(c, Link):
        if c.target in anchors:
            return f'<a href="#{_esc(c.target)}">{_esc(c.text)}</a>'
        return _esc(c.text)
    return _esc(c)


def _table_html(t: ReportTable, anchors: set[str]) -> list[str]:
    out = [f"<h3>{_esc(t.title)}</h3>", "<table>"]
    out.append("<thead><tr>"
               + "".join(f"<th>{_esc(col)}</th>" for col in t.columns)
               + "</tr></thead>")
    out.append("<tbody>")
    if not t.rows and not t.footer_rows:
        out.append("<tr><td>(empty)</td>"
                   + "<td></td>" * (len(t.columns) - 1) + "</tr>")
    for i, row in enumerate(t.rows):
        anchor = t.row_anchors[i] if i < len(t.row_anchors) else None
        id_attr = f' id="{_esc(anchor)}"' if anchor else ""
        out.append(f"<tr{id_attr}>"
                   + "".join(f"<td>{_cell_html(c, anchors)}</td>" for c in row)
                   + "</tr>")
    out.append("</tbody>")
    if t.footer_rows:
        out.append("<tfoot>")
        for row in t.footer_rows:
            out.append("<tr>"
                       + "".join(f"<td>{_cell_html(c, anchors)}</td>"
                                 for c in row)
                       + "</tr>")
        out.append("</tfoot>")
    out.append("</table>")
    return out


def _panel_html(section: ReportSection, index: int,
                anchors: set[str]) -> list[str]:
    out = [f'<section class="tab-panel" id="tab-{index}">']
    if section.intro:
        out.append(f"<p>{_esc(section.intro)}</p>")
    for t in section.tables:
        out.extend(_table_html(t, anchors))
    for note in section.notes:
        out.append(f'<aside class="note">{_esc(note)}</aside>')
    out.append("</section>")
    return out


class HtmlRenderer:
    """Renders a Report as a self-contained tabbed HTML document."""

    def render(self, report: Report) -> str:
        anchors = _collect_anchors(report)
        out = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{_esc(report.title)}</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            f"<h1>{_esc(report.title)}</h1>",
        ]
        if report.metadata:
            out.append('<dl class="meta">')
            for key, value in report.metadata.items():
                out.append(f"<dt>{_esc(key)}</dt><dd>{_esc(value)}</dd>")
            out.append("</dl>")
        out.append('<div class="tab-bar">')
        for i, section in enumerate(report.sections):
            out.append(f'<button type="button" data-tab="tab-{i}">'
                       f"{_esc(section.title)}</button>")
        out.append("</div>")
        for i, section in enumerate(report.sections):
            out.extend(_panel_html(section, i, anchors))
        out.append(f"<script>{_JS}</script>")
        out.append("</body>")
        out.append("</html>")
        return "\n".join(out) + "\n"
```

Register it in `ocx_model_validator/reporting/renderers/__init__.py`:

```python
"""Report renderers — registry and public API."""
from __future__ import annotations

from ocx_model_validator.reporting.renderers.base import ReportRenderer
from ocx_model_validator.reporting.renderers.html import HtmlRenderer
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer

_RENDERERS: dict[str, type[ReportRenderer]] = {
    "markdown": MarkdownRenderer,
    "rich": RichRenderer,
    "html": HtmlRenderer,
}


def get_renderer(fmt: str) -> ReportRenderer:
    """Return a renderer instance for ``fmt``; raise ValueError if unknown."""
    try:
        return _RENDERERS[fmt]()
    except KeyError:
        supported = ", ".join(sorted(_RENDERERS))
        raise ValueError(f"Unknown report format {fmt!r}; supported: {supported}") from None


__all__ = ["HtmlRenderer", "MarkdownRenderer", "ReportRenderer", "RichRenderer",
           "get_renderer"]
```

Note: `tests/test_reporting_renderers.py::test_get_renderer_unknown_format` matches
`"markdown, rich"` — the new sorted list `"html, markdown, rich"` still contains
that substring, so it keeps passing. Verify in Step 4.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_html_renderer.py tests/test_reporting_renderers.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/renderers/html.py ocx_model_validator/reporting/renderers/__init__.py tests/test_html_renderer.py
git commit -m "feat(renderers): self-contained tabbed HTML renderer with internal links"
```

---

### Task 4: Catalogues generator emits row anchors

**Files:**
- Modify: `ocx_model_validator/reporting/generators/catalogues.py`
- Test: `tests/test_reporting_links.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reporting_links.py`:

```python
"""Tests for internal cross-link emission by report generators."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import IrPlate, IrStiffener, IrVessel
from ocx_model_validator.reporting.generators import bom as bom_gen
from ocx_model_validator.reporting.generators import catalogues as catalogues_gen
from ocx_model_validator.reporting.model import Link

_PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.materials["M2"] = IrMaterial(id="M2", name="AH36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    return v


def test_materials_table_row_anchors_follow_sorted_rows():
    report = catalogues_gen.build(_vessel(), which="material")
    table = report.sections[0].tables[0]
    # rows sorted by name: AH36 (M2) before NV A36 (M1)
    assert [r[0] for r in table.rows] == ["M2", "M1"]
    assert table.row_anchors == ["material-M2", "material-M1"]


def test_sections_table_row_anchors():
    report = catalogues_gen.build(_vessel(), which="section")
    table = report.sections[0].tables[0]
    assert table.row_anchors == ["section-S1"]


def test_openings_table_has_no_anchors():
    report = catalogues_gen.build(_vessel(), which="opening")
    assert report.sections[0].tables[0].row_anchors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_links.py -v`
Expected: the two anchor tests FAIL (`row_anchors == []`); openings test PASSES

- [ ] **Step 3: Implement**

In `catalogues.py` `_materials_section`, collect anchors alongside rows:

```python
def _materials_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    row_anchors: list[str | None] = []
    for m in sorted(vessel.materials.values(), key=lambda m: m.name or m.id):
        ctx = f"material {m.id}"
        row_anchors.append(f"material-{m.id}")
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
                         tables=[ReportTable("Materials", columns, rows,
                                             row_anchors=row_anchors)],
                         notes=notes)
```

In `_sections_section`, add anchors in the row loop and pass them through:

```python
    rows: list[list[Cell]] = []
    row_anchors: list[str | None] = []
    for s in secs:
        row_anchors.append(f"section-{s.id}")
        row: list[Cell] = [s.id, s.name, _section_type_name(s)]
        ...  # existing dim/angle loop unchanged
        rows.append(row)
    return ReportSection(title="Cross sections",
                         tables=[ReportTable("Cross sections", columns, rows,
                                             row_anchors=row_anchors)],
                         notes=notes)
```

(The `...` marks the existing unchanged dim/angle field loops — do not retype them, only insert the `row_anchors` lines and the new `ReportTable` keyword argument.)

`_openings_section` is unchanged (no anchors).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_links.py tests/test_reporting_generators.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/reporting/generators/catalogues.py tests/test_reporting_links.py
git commit -m "feat(catalogues): row anchors for material and section rows"
```

---

### Task 5: BOM generator emits `Link` cells

**Files:**
- Modify: `ocx_model_validator/reporting/generators/bom.py`
- Modify: `tests/test_reporting_bom.py` (update exact-row expectations)
- Test: `tests/test_reporting_links.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporting_links.py`:

```python
def _vessel_with_parts() -> IrVessel:
    v = _vessel()
    v.plates["P1"] = IrPlate(id="P1", parent_ref=_PARENT, name="P1",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(1000.0, "UKg")))
    v.stiffeners["ST1"] = IrStiffener(id="ST1", parent_ref=_PARENT, name="ST1",
                                      material_ref=Ref("M1"),
                                      section_ref=Ref("S1"),
                                      mass_properties=IrMassProperties(
                                          moulded_dry_weight=Quantity(250.0, "UKg")))
    v.plates["P2"] = IrPlate(id="P2", parent_ref=_PARENT, name="P2",
                             thickness=Quantity(12.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(2000.0, "UKg")))  # no material
    return v


def test_bom_material_cells_are_links():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    plate_row = next(r for r in table.rows if r[1] == "Plate" and r[2] == "t=10.0 mm")
    assert plate_row[0] == Link("NV A36", "material-M1")


def test_bom_section_group_cells_are_links():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    stiff_row = next(r for r in table.rows if r[1] == "Stiffener")
    assert stiff_row[2] == Link("FB200x20", "section-S1")


def test_bom_unresolved_material_stays_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    no_mat_row = next(r for r in table.rows if r[2] == "t=12.0 mm")
    assert no_mat_row[0] == "(no material)"


def test_bom_thickness_groups_stay_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    plate_row = next(r for r in table.rows if r[1] == "Plate" and r[2] == "t=10.0 mm")
    assert isinstance(plate_row[2], str)


def test_bom_subtotal_and_total_rows_stay_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    subtotal = next(r for r in table.rows if isinstance(r[0], str)
                    and r[0].startswith("Subtotal"))
    assert isinstance(subtotal[0], str)
    assert table.footer_rows[0][0] == "Grand total"


def test_bom_detailed_items_are_links_too():
    report = bom_gen.build(_vessel_with_parts(), detailed=True)
    items = report.sections[0].tables[1]
    st1_row = next(r for r in items.rows if r[3] == "ST1")
    assert st1_row[0] == Link("NV A36", "material-M1")
    assert st1_row[2] == Link("FB200x20", "section-S1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting_links.py -v -k bom`
Expected: all new bom tests FAIL (cells are plain strings)

- [ ] **Step 3: Implement**

In `bom.py`, extend the model import:

```python
from ocx_model_validator.reporting.model import Cell, Link, Report, ReportSection, ReportTable
```

Add two module-level helpers after `_weight_tonnes`:

```python
def _anchor_maps(vessel: IrVessel) -> tuple[dict[str, str], dict[str, str]]:
    """Display name → anchor id for materials and sections.

    Grouping keys stay plain strings (sortable); cells get wrapped in Link
    at emission time via these maps. On duplicate display names the first
    id wins — the link then points at one representative catalogue row.
    """
    material_anchor: dict[str, str] = {}
    for mid, m in vessel.materials.items():
        material_anchor.setdefault(m.name or m.grade or mid, f"material-{mid}")
    section_anchor: dict[str, str] = {}
    for sid, s in vessel.sections.items():
        section_anchor.setdefault(s.name or sid, f"section-{sid}")
    return material_anchor, section_anchor


def _link(name: str, anchors: dict[str, str]) -> Cell:
    target = anchors.get(name)
    return Link(name, target) if target else name
```

In `build()`, after the grouping loop and before building `rows`, add:

```python
    material_anchor, section_anchor = _anchor_maps(vessel)
```

Change the group-row emission (inside the `for (material, part_type, group), g in sorted(groups.items()):` loop) from:

```python
        rows.append([material, part_type, group,
                     g.count, round(g.weight_t, 3), g.missing])
```

to:

```python
        rows.append([_link(material, material_anchor), part_type,
                     _link(group, section_anchor),
                     g.count, round(g.weight_t, 3), g.missing])
```

Change the detailed item-row emission from:

```python
                item_rows.append([material, part_type, group, item_id, name,
                                  round(w, 3) if w is not None else None])
```

to:

```python
                item_rows.append([_link(material, material_anchor), part_type,
                                  _link(group, section_anchor), item_id, name,
                                  round(w, 3) if w is not None else None])
```

Subtotal (`_flush_subtotal`) and grand-total rows are NOT changed — they stay plain strings.

Note on `_anchor_maps` key choice: `_material_name` returns `m.name or m.grade or m.id` and `_group_key` returns `s.name or s.id` for sections, so the map keys match the display strings exactly. Thickness groups (`t=...`), `"(no material)"` and `"(no section)"` are never in the maps and stay plain.

- [ ] **Step 4: Update exact-row expectations in `tests/test_reporting_bom.py`**

Add `Link` to the imports:

```python
from ocx_model_validator.reporting.model import Link
```

In `test_bom_summary_grouping_and_totals`, replace the `assert table.rows == [...]` block with:

```python
    assert table.rows == [
        ["(no material)", "Plate", "t=12.0 mm", 1, 2.0, 0],
        ["Subtotal — (no material)", None, None, 1, 2.0, 0],
        [Link("NV A36", "material-M1"), "Pillar", Link("FB200x20", "section-S1"), 1, 0.3, 0],
        [Link("NV A36", "material-M1"), "Plate", "t=10.0 mm", 3, 1.5, 1],
        [Link("NV A36", "material-M1"), "Stiffener", Link("FB200x20", "section-S1"), 1, 0.25, 0],
        ["Subtotal — NV A36", None, None, 5, 2.05, 1],
    ]
```

No other test in that file compares material/group cells by exact equality
(`test_bom_unknown_thickness_unit_group_key` only probes thickness strings,
which remain plain).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting_links.py tests/test_reporting_bom.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/reporting/generators/bom.py tests/test_reporting_links.py tests/test_reporting_bom.py
git commit -m "feat(bom): link material and section cells to catalogue rows"
```

---

### Task 6: CLI — `--format html` and destination-suffix inference

**Files:**
- Modify: `ocx_model_validator/cli.py`
- Test: `tests/test_cli_report.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_report.py`:

```python
def test_report_destination_html_suffix_infers_html(model_310: Path, tmp_path: Path):
    dest = tmp_path / "out.html"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert "<title>Frame table report</title>" in text


def test_report_destination_htm_uppercase_suffix(model_310: Path, tmp_path: Path):
    dest = tmp_path / "OUT.HTM"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_report_format_html_to_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "html"])
    assert result.exit_code == 0
    assert result.output.startswith("<!DOCTYPE html>")


def test_report_explicit_markdown_wins_over_html_suffix(model_310: Path,
                                                        tmp_path: Path):
    dest = tmp_path / "out.html"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "markdown",
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("# Frame table report")


def test_report_format_html_to_md_destination_writes_html(model_310: Path,
                                                          tmp_path: Path):
    dest = tmp_path / "out.md"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "html",
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_report_all_html_has_tabs_and_links(model_310: Path, tmp_path: Path):
    dest = tmp_path / "all.html"
    result = runner.invoke(app, ["report", "all", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    for title in ["Model extent", "Frame table", "Compartments",
                  "Materials", "Bill of material"]:
        assert f">{title}</button>" in text
    # catalogue anchors exist whenever the model declares materials
    if 'id="material-' in text:
        assert "tab-panel" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_report.py -v -k html`
Expected: FAIL — `.html` destination currently writes markdown; `--format html` is not a valid enum value (exit code 2)

- [ ] **Step 3: Implement**

In `cli.py`, add the enum member:

```python
class ReportFormat(str, Enum):
    rich = "rich"
    markdown = "markdown"
    html = "html"
```

Replace `_emit` with:

```python
_HTML_SUFFIXES = {".html", ".htm"}


def _emit(report: Report, fmt: ReportFormat | None, destination: Path | None) -> None:
    if destination is not None:
        if fmt == ReportFormat.rich:
            raise typer.BadParameter(
                "--destination cannot be combined with --format rich")
        if fmt is None:
            fmt = (ReportFormat.html
                   if destination.suffix.lower() in _HTML_SUFFIXES
                   else ReportFormat.markdown)
        try:
            destination.write_text(get_renderer(fmt.value).render(report),
                                   encoding="utf-8")
        except OSError as exc:
            logger.error("Cannot write {}: {}", destination, exc)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Report written to {destination}")
        return
    if fmt is None or fmt == ReportFormat.rich:
        RichRenderer().render_to_console(report, Console())
    else:
        typer.echo(get_renderer(fmt.value).render(report), nl=False)
```

Update `_FORMAT_OPT` help text:

```python
_FORMAT_OPT = typer.Option(None, "--format", "-f",
                           help="Output format (default: rich to stdout; "
                                "markdown with --destination, or html when "
                                "the destination ends in .html/.htm).")
```

Also update the module docstring's first usage line to mention html:

```python
    validator report frame-table MODEL.3docx [--format rich|markdown|html] [--destination FILE]
```

- [ ] **Step 4: Run the CLI test file**

Run: `uv run pytest tests/test_cli_report.py -v`
Expected: all PASS (existing markdown/rich tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/cli.py tests/test_cli_report.py
git commit -m "feat(cli): html report format with destination-suffix inference"
```

---

### Task 7: Integration smoke, docs, full verification

**Files:**
- Modify: `tests/test_integration_reports.py`
- Modify: `.github/copilot-instructions.md` (CLI section)

- [ ] **Step 1: Add an integration smoke test**

Append to `tests/test_integration_reports.py`:

```python
TR05_MODEL = Path("models/TR05/tr05_tc04a_mbrh.3docx")


@pytest.mark.skipif(not TR05_MODEL.exists(),
                    reason="TR05 reference model not present")
def test_report_all_html_links_resolve_on_tr05(tmp_path: Path):
    dest = tmp_path / "all.html"
    result = runner.invoke(
        app, ["report", "all", str(TR05_MODEL), "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    # BOM material links resolve to materials-catalogue row anchors
    assert 'href="#material-' in text
    assert 'id="material-' in text
```

Note: this test is NOT guarded by the module-level `pytestmark` skipif on the
VLCC model — the `pytestmark` list applies to every test in the module, so if
the VLCC model is absent this test is skipped too. That is acceptable: it is
an opt-in integration test, and the local dev machine has both models. Place
it in this file regardless; CI without models skips it.

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/test_integration_reports.py -v -m integration`
Expected: PASS (or SKIP on machines without the models — on this machine it must PASS)

- [ ] **Step 3: Manual smoke check**

Run: `uv run validator report all models/TR05/tr05_tc04a_mbrh.3docx --destination report.html`
Expected: "Report written to report.html". Then confirm content and clean up:

```powershell
Select-String -Path report.html -Pattern 'href="#material-' -Quiet
Remove-Item report.html
```

Expected: `True` from Select-String.

- [ ] **Step 4: Update docs**

In `.github/copilot-instructions.md`, find the CLI usage block (the fenced
block showing `validator report ...` commands) and change the markdown
reference so it reads:

```bash
# Model reports (rich to stdout; markdown or html via --destination / --format)
validator report frame-table  model.3docx
validator report compartments model.3docx
validator report all          model.3docx --destination report.md
validator report all          model.3docx --destination report.html
```

(Keep the rest of the block — `generate-stubs` lines — unchanged.)

- [ ] **Step 5: Full verification**

Run: `uv run pytest -q`
Expected: all pass (prior baseline: 413 passed, 25 skipped; this plan adds ~30 tests)

Run: `uv run ruff check ocx_model_validator tests`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add tests/test_integration_reports.py .github/copilot-instructions.md
git commit -m "test: HTML report integration smoke on TR05 model; document html format"
```

---

## Success criteria (from the spec)

1. `validator report all model.3docx --destination report.html` produces a single self-contained HTML file with one tab per section.
2. BOM material/section names are clickable and jump to the catalogue row (tab switch + scroll + highlight).
3. In standalone reports (e.g. `report bom`), unresolvable links render as plain text — no broken anchors.
4. Markdown and rich output are unchanged except `Link` cells render as text.
5. `--format html` works to stdout and to any destination; `.html`/`.htm` suffix infers html; explicit `--format` wins.
6. Full suite green, ruff clean.
