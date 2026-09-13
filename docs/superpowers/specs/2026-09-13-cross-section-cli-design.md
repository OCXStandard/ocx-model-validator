# Cross-Section CLI Design

**Date:** 2026-09-13
**Status:** Approved

## Goal

Two CLI commands under a new `validator section` sub-app:

1. `validator section create` — build a transverse cross-section at a frame or x-position and write the `nh-cross-section/1` JSON document.
2. `validator section plot` — read that JSON and write an SVG plot of the full cross section: plates color-coded by thickness, stiffeners drawn as inclined line stubs with a numbered legend of profile names.

## Existing machinery (reused, not rebuilt)

- `sections/document.py`: `build_document(vessel, source_file, x_mm|frame)` produces the JSON document (schema `nh-cross-section/1`) containing `frame_table`, `cross_section` (plates with `y1_mm/z1_mm/y2_mm/z2_mm/thickness_mm`, stiffeners with `y_mm/z_mm/profile_type/profile_dimensions`), `compartments`, `warnings`. `save_document`/`load_document` handle I/O and schema validation.
- `sections/section_builder.py`: `build_cross_section(vessel, x_mm)` — geometry intersection; raises `SectionError` when nothing intersects.
- `cli.py`: `_load_vessel(model)` helper (parse + build IR, exit 1 on failure).

## New: stiffener inclination through the pipeline

The OCX schema defines `Stiffener.Inclination` (a list of `Inclination` elements, each with `WebDirection` Vector3D, optional `FlangeDirection`, and `Position` Point3D). The current IR/builder drops it, so the section JSON has no mounting-side data (`web_angle_deg` is a constant 90.0).

1. **IR** (`model/ir/structural.py`): add frozen-convention dataclass
   `IrInclination(web_direction: IrVector3D | None, flange_direction: IrVector3D | None, position: IrPoint3D | None)`
   and field `IrStiffener.inclinations: list[IrInclination] = []`.
2. **Builder** (`builders/v3_builder.py`): extract `stiffener.inclination` (getattr-safe) using the existing `_pt`/`_vec` helpers.
3. **Section builder** (`sections/section_builder.py`): add nullable fields
   `web_dir_y: float | None` and `web_dir_z: float | None` to `SectionStiffener` (unit vector in the section plane). Per intersection hit:
   - pick the inclination whose `position` x is nearest the section `x_mm` (first one if positions are absent);
   - project its `web_direction` onto the (y, z) plane and normalize; if the projection is degenerate (near-zero length) treat as absent;
   - if the stiffener has no usable inclination, set both fields to `None` and append a warning (`"stiffener <name>: no inclination; web direction unknown"`).
   The constant `web_angle_deg` field remains for backward compatibility.
4. **JSON**: the new fields flow through `_dataclass_dict` automatically. The change is additive; the schema id stays `nh-cross-section/1` (`load_document` only checks top-level keys).

## CLI commands (`cli.py`, new `section_app` sub-app mirroring `report_app`)

### `validator section create MODEL.3docx (--frame LABEL | --x MM) [--output FILE.json]`

- Exactly one of `--frame` / `--x` is required; both or neither → `typer.BadParameter`.
- `--x` is in millimetres (consistent with internal units).
- Flow: `_load_vessel` → `build_document(vessel, str(model), x_mm=… or frame=…)` → `save_document`.
- Default `--output`: `<model-stem>-<frame>.json` or `<model-stem>-x<mm>.json` in the cwd (e.g. `myship-FR20.json`, `myship-x50000.json`).
- `SectionError` (unknown frame label, no intersecting geometry) and `GeometryError` → `logger.error` + exit 1.
- On success, echo `Section written to <path>`.

### `validator section plot SECTION.json [--output FILE.svg]`

- Flow: `load_document` (schema-validated; `SectionError` → logged, exit 1) → `render_svg(doc)` → write text.
- Default `--output`: input path with `.svg` suffix.
- On success, echo `Plot written to <path>`.

## SVG renderer (`sections/svg_plot.py`, stdlib only)

`render_svg(doc: dict) -> str` — hand-written SVG string; no new dependencies; deterministic output.

**Canvas and mapping**
- Plot area ≈ 1200×900 px plus a ≈ 360 px legend column on the right; margins around the plot.
- y horizontal, z vertical up (SVG y-axis inverted). Uniform mm→px scale fitted to the bounding box of all plates and stiffeners plus a 5 % margin. Empty geometry (no plates and no stiffeners) still renders the title and legends with a "no geometry" note.
- Total SVG height grows to fit the legend when the stiffener list is longer than the plot area.

**Plates**
- One `<line>` per plate, stroke width ≈ 3 px.
- Stroke color from a fixed 12-color qualitative palette, assigned to sorted unique `thickness_mm` values (cycling beyond 12).
- `thickness_mm: null` → dashed grey line.

**Stiffeners**
- Numbered 1-based in JSON document order.
- Each drawn as a line stub from its `(y_mm, z_mm)` hit point along `(web_dir_y, web_dir_z)` — making mounting side visible (above/below a deck plate, inboard/outboard on a side shell).
- Stub length in mm: profile height parsed as the first number in `profile_dimensions` (e.g. `"200 x 20"` → 200) when parseable, else 250 mm; converted with the same mm→px scale.
- Number label placed just beyond the stub tip.
- `web_dir_* = null` → dashed vertical stub (visually flags unknown orientation).

**Legends and title**
- Title block: `Cross section at x=<x_mm> mm (frame <frame>)` — frame part omitted when null — plus source file name.
- "Stiffeners" legend: one row per stiffener, `<n>  <name> — <profile_type> <profile_dimensions>`.
- "Plate thickness" legend: color swatch line + `<t> mm` per unique thickness (plus a grey dashed swatch for unknown when present).
- All user-provided strings are XML-escaped (`xml.sax.saxutils.escape`).

## Error handling summary

| Failure | Behaviour |
|---|---|
| Model parse/build failure | logged, exit 1 (existing `_load_vessel`) |
| Both/neither of `--frame`/`--x` | `BadParameter` (usage error, exit ≠ 0) |
| Unknown frame label / no intersections | logged `SectionError`, exit 1 |
| Invalid/malformed JSON document | logged `SectionError`, exit 1 |
| Stiffener without inclination | warning in document + dashed stub in plot |
| Output file not writable | logged `OSError`, exit 1 |

## Testing

- **Unit — pipeline**: builder extracts `Inclination` (inline stub classes per test conventions); `SectionStiffener.web_dir_*` projection (angled vector → normalized 2D components; missing inclination → `None` + warning; nearest-position selection with two inclinations).
- **Unit — renderer**: synthetic document fixture; string assertions on `<line>` colors matching thickness palette, dashed grey for null thickness, stub endpoints reflecting web direction, dashed stub for null direction, numbered labels, legend rows, XML-escaping of names, title content.
- **CLI** (`tests/test_cli_section.py`, CliRunner): `plot` happy path from a synthetic JSON fixture; `create` with both/neither position flags → usage error; `create` on the 3.1.0 vessel stub (no intersecting geometry) → exit 1; default output-name derivation.
- **Integration** (marked `integration`, VLCC model): `section create --frame` → JSON on disk → `section plot` → SVG containing >0 plate lines and >0 numbered stubs.

## Out of scope (YAGNI)

- Flange rendering, end cuts, brackets, pillars in the plot.
- Interactive/HTML output; PNG export.
- Compartment outlines in the plot.
- Multiple sections per invocation.
