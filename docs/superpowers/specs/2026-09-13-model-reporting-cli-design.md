# Model Reporting CLI — Design

**Date:** 2026-09-13
**Status:** Approved for planning
**Scope:** First stage of the `validator` CLI expansion (reporting). Model validation and
cross-section building commands are future stages and out of scope here.

## Goal

Extend the `validator` Typer CLI with model-reporting commands that parse a `.3docx`
file into the IR and render structured reports:

1. **Frame table** — frame 0 offset, spacing entries, frame label → x position
2. **Compartments** — name, type/purpose, volume, COG, extents
3. **Catalogues** — material, cross-section, and opening (hole shape) catalogues
4. **Bill of material (BOM)** — plates, stiffeners, edge reinforcements, brackets
   grouped by material, with per-item weights and aggregated totals

Rendering is pluggable. Two renderers ship now: **Rich** (terminal, default) and
**Markdown** (file output). JSON and HTML renderers are anticipated later.

## Architecture

Chosen approach: **neutral report model + renderer protocol**. Report generators
produce a plain data structure; renderers consume it. Adding a format later means one
new renderer and zero generator changes. (Rejected: render methods on each report
class — N×M growth; jinja2 templates — doesn't fit Rich, unneeded dependency now.)

```
.3docx → OcxParser → get_builder → IrVessel
                                      │
                     reporting.generators.<report>.build(vessel) → Report
                                      │
                     reporting.renderers.<format>  → terminal (Rich) / file (Markdown)
```

## CLI

Breaking restructure of `ocx_model_validator/cli.py` into subcommands:

```
validator report frame-table  MODEL.3docx [--format rich|markdown] [--destination FILE]
validator report compartments MODEL.3docx [--format ...] [--destination FILE]
validator report catalogues   MODEL.3docx [--catalogue material|section|opening|all] [...]
validator report bom          MODEL.3docx [--detailed] [...]
validator report all          MODEL.3docx [...]
validator generate-stubs [--force]
```

- `report` is a Typer sub-app; `generate-stubs` replaces the current
  `--generate/--force` flags (breaking change, accepted).
- Default `--format` is `rich`, written to stdout.
- `--destination FILE` writes to a file. If `--format` is not given with
  `--destination`, it defaults to `markdown`. `--destination` with `--format rich`
  is an error.
- `report all` runs every report and renders them as sections of one document
  (one Markdown file, or sequential Rich output). It uses each report's defaults
  (all catalogues, summary BOM); per-report flags are not accepted on `all`.
- `--catalogue` defaults to `all`.
- `--detailed` (BOM only) adds per-item rows.

## Package layout

New package `ocx_model_validator/reporting/`:

```
reporting/
├── __init__.py          ← public API: build_report(s), get_renderer
├── model.py             ← Report, ReportSection, ReportTable (frozen dataclasses)
├── generators/
│   ├── frame_table.py   ← build(vessel) -> Report  (reuses sections.build_frame_table)
│   ├── compartments.py  ← build(vessel) -> Report
│   ├── catalogues.py    ← build(vessel, which="all") -> Report
│   └── bom.py           ← build(vessel, detailed=False) -> Report
└── renderers/
    ├── base.py          ← ReportRenderer protocol
    ├── markdown.py      ← MarkdownRenderer: render(report) -> str
    └── rich.py          ← RichRenderer: render_to_console(report, console)
```

### Report model (`model.py`)

- `ReportTable`: `title`, `columns: list[str]`, `rows: list[list[Cell]]` where
  `Cell = str | int | float | None` (`None` renders as "N/A"). Optional
  `footer_rows` for subtotals/totals so renderers can style them.
- `ReportSection`: `title`, optional intro text, `tables: list[ReportTable]`,
  optional `notes: list[str]` (e.g. missing-weight warnings).
- `Report`: `title`, `metadata: dict[str, str]` (vessel name, schema version,
  source file, generated-at timestamp), `sections: list[ReportSection]`.
- All cells are pre-formatted scalars with units already resolved by the
  generator. Renderers never see IR objects or `Quantity`.

### Renderer protocol (`renderers/base.py`)

```python
class ReportRenderer(Protocol):
    def render(self, report: Report) -> str: ...
```

Markdown implements `render`. Rich implements `render` by capturing console output
plus a convenience `render_to_console` for direct terminal printing. A registry
`get_renderer(format: str) -> ReportRenderer` dispatches; unknown format → typer
error listing supported formats.

## Report contents

### Frame table

- Metadata row: frame 0 offset (mm), number of frames.
- Table 1 — spacing entries: from-frame, to-frame, spacing (mm).
- Table 2 — positions: frame label, x (mm).
- Reuses `ocx_model_validator.sections.build_frame_table`. If the model has no
  X ref planes, render an "(empty)" table with a note.

### Compartments

One table over `vessel.compartments`: id, name, compartment/tank type, volume (m³),
COG (x, y, z in mm), extents (min/max x, y, z in mm). Physical spaces are excluded
(compartments only, per request).

### Catalogues

Three sections (filterable via `--catalogue`):

- **Materials** (`vessel.materials`): id, name, grade, density (t/m³),
  yield stress (MPa), ultimate stress (MPa), Young's modulus (MPa).
- **Cross sections** (`vessel.sections`): id, name, section type (IR class name
  minus `Ir`/`Section`), and key dimensions in mm collected per subtype via
  `dataclasses.fields` (columns are the union of dimension names present;
  missing → N/A).
- **Openings** (`vessel.hole_shape_catalogue`): hole id, name, parametric
  dimensions (mm). Absent catalogue → "(empty)" with note.

### Bill of material

Grouping hierarchy: **material → part type → sub-group**:

- Part types: plate, stiffener, edge reinforcement, bracket.
- Sub-group key: thickness (mm) for plates and brackets; cross-section ref name
  for stiffeners and edge reinforcements.
- Parts with no `material_ref` or a dangling ref group under "(no material)".

Summary mode (default): one row per material × part type × sub-group with
count and total weight (t); subtotal rows per material; grand-total row
(count, weight). Detailed mode (`--detailed`): per-item rows under each
sub-group: id, name, thickness or section, weight (t).

**Missing weights:** items whose `dry_weight` is `None` (or has an unresolvable
unit) show N/A in detailed mode, are excluded from all totals, and each group
row reports the count of items missing weight. A section note summarizes the
total number of excluded items.

## Units and conversion

- Weights → **tonnes**, lengths → **mm**, volumes → **m³**, stresses → **MPa**,
  density → **t/m³**.
- Conversion uses the existing `UnitConverter` / `vessel.unit_registry` on
  `Quantity` values. If a unit id cannot be resolved, the generator emits the
  raw value with the unit id appended (e.g. `12.5 Ubogus`) and adds a section
  note; it never raises.
- Numeric formatting is done in the generators: weights 3 decimals, lengths
  1 decimal or integer, stresses integer MPa.

## Error handling

- Parse or build failure → loguru error, exit code 1.
- Missing model file → typer error ("file not found"), exit code 2 (typer default).
- Unwritable `--destination` → typer error, exit code 1.
- Empty collections never crash: render "(empty)" tables with a note.
- `--destination` combined with `--format rich` → typer error.

## Dependencies

Add `rich` to `[project.dependencies]` (already an indirect dependency via typer;
made explicit because it is imported directly).

## Testing

- **Generator unit tests** (`tests/test_reporting_*.py`): build IRs from existing
  stub fixtures (conftest `_build_session`) and hand-constructed `IrVessel`
  instances; assert table columns, grouping keys, totals arithmetic,
  missing-weight exclusion, and N/A handling.
- **Renderer tests**: Markdown output snapshot assertions (stable ordering
  required: groups sorted by material name, then part type, then sub-group key);
  Rich smoke test rendering to a captured `Console` without error.
- **CLI tests**: `typer.testing.CliRunner` covering each subcommand, format
  dispatch, `--destination` file writing, and the rich+destination error.
- **Integration test** (marked `integration`): `validator report bom --detailed`
  against the real VLCC model; assert non-empty groups and a positive grand total.

## Out of scope

- Model validation and cross-section CLI commands (future stages).
- JSON/HTML renderers (design supports them; not implemented now).
- Computing weight from geometry when `dry_weight` is missing.
- Pillars, members, seams in the BOM.
