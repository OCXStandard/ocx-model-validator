# HTML Report Renderer — Design

**Date:** 2026-10-03
**Status:** Approved

## Goal

Add an HTML renderer that outputs a full model report as a single self-contained
HTML file with tabbed sections and working internal cross-links (e.g. a BOM
material name links to its row in the Materials catalogue tab). Units remain in
column headers, as today.

## Decisions

- Links are **internal only** (within the report document); no external links.
- Units stay in **column headers** (e.g. "Volume (m³)"); cells remain bare values.
- Format selection: new `--format html`, **plus** inference when
  `--destination` ends in `.html`/`.htm` (case-insensitive).
- Output is a **single self-contained file**: inline CSS and minimal inline JS,
  no external dependencies; works from `file://`.
- Tabs: **one tab per report section**.
- Approach: link-aware report model (minimal `Link` cell + per-row anchors),
  not renderer heuristics and not a full hyperdocument model.

## 1. Report model extensions (`reporting/model.py`)

```python
@dataclass(frozen=True)
class Link:
    text: str
    target: str   # anchor id, without leading '#'

Cell = str | int | float | Link | None
```

`ReportTable` gains:

```python
row_anchors: list[str | None] = field(default_factory=list)
```

Parallel to `rows`; an anchor id for each row. Empty list (the default) means
no anchors. If `row_anchors` is shorter than `rows`, missing entries mean no
anchor (tolerated, never an error).

## 2. Generator changes

- `generators/catalogues.py`:
  - Materials table: `row_anchors = [f"material-{id}", ...]` (one per row, in
    row order).
  - Sections table: `row_anchors = [f"section-{id}", ...]`.
- `generators/bom.py`:
  - Material cells in summary and detailed item rows become
    `Link(material_name, f"material-{material_id}")` when the material ref
    resolves; otherwise plain string (including `"(no material)"`).
  - Section-group cells (stiffener/pillar/edge-reinforcement groups) become
    `Link(group_name, f"section-{section_id}")` when the section ref resolves.
    Thickness groups (`t=...`) stay plain.
  - Subtotal and grand-total rows stay plain strings.
  - BOM groups by *display name*, so link targets are resolved via
    display-name → anchor maps. If two catalogue entries share a display
    name, their parts collapse into one BOM group and the link points to one
    representative catalogue row (first id wins). *(Correction recorded
    during implementation: the original per-ref wording above is not
    well-defined at group level.)*

Anchor id convention: `material-<IR id>` / `section-<IR id>` — IR ids are the
dict keys in `IrVessel.materials` / `IrVessel.sections`, so anchors are unique
per table.

## 3. HTML renderer (`renderers/html.py`)

Class `HtmlRenderer` with `render(report) -> str`, registered in
`_RENDERERS` under `"html"`.

- Document: `<!DOCTYPE html>`, `<h1>` title, metadata as a definition list,
  tab bar (`<button>` per section), one `<div class="tab-panel">` per section
  containing its tables and notes.
- Tables: `<h3>` title, `<thead>` from columns, `<tbody>` rows, footer rows
  styled bold (`<tfoot>`), `None` cells render "N/A", empty table renders an
  "(empty)" row.
- Notes render as styled `<aside>`/blockquote elements after the tables; the
  section `intro` renders as a paragraph before them.
- Tabs: inline CSS + ~15 lines of inline JS. Buttons toggle panel visibility;
  first tab active on load.
- **Link resolution:** the renderer first collects every anchor id present in
  the report (`row_anchors` across all tables). A `Link` whose target is in
  that set renders `<a href="#target">text</a>`; otherwise it renders as plain
  text. Clicking an internal link activates the tab containing the target and
  scrolls to the row (JS intercepts in-page anchor clicks; row elements carry
  `id` attributes).
- All user-derived text passes through `html.escape`.
- The renderer is pure (string in, string out); no I/O.

## 4. Existing renderers

- `markdown.py` `_cell`: `Link` renders as its `.text`.
- `rich.py` cell formatting: same degradation.

No other behavioural change to either renderer.

## 5. CLI (`cli.py`)

- `ReportFormat` gains `html`.
- `_emit` logic:
  - `--destination` with suffix `.html`/`.htm` (case-insensitive) → html
    renderer, unless `--format` explicitly says otherwise (explicit
    `--format markdown` to an `.html` path writes markdown — explicit wins).
  - `--format html` with any destination writes html regardless of suffix.
  - `--format html` without destination prints the HTML document to stdout.
  - `--format rich` + `--destination` remains a `BadParameter` error.

## 6. Error handling

- File-write errors: already handled in `_emit` (logged, exit 1).
- Unresolvable `Link` targets: silent degradation to plain text (by design —
  standalone reports lack catalogue sections).
- `row_anchors`/`rows` length mismatch: tolerated; missing anchors skipped.

## 7. Testing

- `tests/test_html_renderer.py`: one tab button + panel per section; HTML
  escaping of titles/cells; `None` → N/A; footer rows bold; resolved `Link`
  → `<a href>`; unresolved `Link` → plain text; row `id` attributes emitted
  from `row_anchors`; empty-table placeholder.
- `tests/test_reporting_links.py`: BOM emits `Link` cells for resolvable
  materials/sections and plain strings otherwise; catalogues emit
  `row_anchors`; markdown and rich render `Link` as text.
- CLI tests: `--destination x.html` infers html; `--format html` without
  destination writes HTML to stdout; explicit `--format markdown` to `.html`
  path writes markdown.
- Smoke: `validator report all` on a TR05 model writes parseable HTML whose
  BOM links resolve to catalogue anchors.

## Out of scope

- External links, per-cell units, linking parts/compartments, PDF output,
  styling themes, JS frameworks.
