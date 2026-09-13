# OCX Cross-Section Extraction + MCP Server — Design Spec

Date: 2026-09-13
Status: approved design, pending user spec review

## 1. Goal

Feed DNV Nauticus Hull rule checks (via the `nauticushull-mcp` server in
`C:\PythonDev\nh-mcp`) with data extracted from an OCX 3D ship model:

1. Extend **ocx-model-validator** to attach geometry to the IR and derive:
   - the Nauticus **frame table** from the OCX X ref planes,
   - a **cross-section** at any frame position (plane intersection of the
     3D model): all longitudinal stiffener positions and plate segments,
   - **compartments** (name, type, volume, COG, extents).
2. Represent the result as a **lean JSON document** (schema below).
3. Expose it through a new **OCX MCP server** inside ocx-model-validator.
4. Verify the **full pipeline**: OCX → JSON → nh-mcp tool calls → real
   plate/stiffener rule results, via a demo/integration script in nh-mcp.

### Success criterion

For the reference model
`C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx`
(OCX 3.0.0, plain XML — not zipped), the demo script produces real
`calculate_shell_plate` and `calculate_stiffener` results in Nauticus Hull
for at least one cross-section, using the frame table, compartments, plates
and stiffeners extracted from the model.

### Reference model facts (verified by inspection)

- Plain XML, `schemaVersion="3.0.0"`, ~21 MB.
- 402 X ref planes (named `X0`, `X0.8`, `X1.6`, …), Y/Z planes present.
- 3963 stiffeners with `TraceLine` = `CompositeCurve3D` of mostly `Line3D`
  segments (4182) plus some `NURBS3D` (138).
- 523 plates with `OuterContour` = `CompositeCurve3D` of `NURBS3D`.
- 143 panels; `UnboundedGeometry` is mostly `GridRef` (99 — planar) plus
  `SurfaceRef`/`NURBSSurface` (hull).
- 38 `BarSection` catalogue entries, 4082 `SectionRef`s, 5 `Compartment`s.

The sibling sample `examples\TankerTutorial_midship-section.json` in nh-mcp
is actually a Nauticus Hull **CrossSectionPart XML** export (utf-16 XML with
a text header line). It is the *inspiration* for the JSON content
(plates with thickness/material, stiffener groups with positions/profiles),
not a format to mirror: the JSON is lean and purpose-built (user decision).

## 2. Architecture

```
.3docx ──OcxParser──▶ IrVessel (extended with geometry)
                          │
             sections/ module (new, pure functions)
                          │
        ┌─ frame table ──┴─ build_section(x) ── compartments ─┐
        ▼                                                     ▼
   lean JSON document (mm / MPa, NH conventions)  ◀── mcp/ server tools
                          │
   nh-mcp examples\demo_ocx_pipeline.py → nh-mcp tools → rule results
```

Units rule: the IR keeps OCX/SI units as parsed; **the JSON document and
everything downstream uses mm for lengths, MPa for stress, m³ for volume**
(Nauticus Hull conventions), converted via the existing unit registry.

New units inside ocx-model-validator (each independently testable):

| Unit | Purpose | Depends on |
|---|---|---|
| `model/ir` (extended) | geometry fields on parts | nothing new |
| `builders/v3_builder` (extended) | populate the new fields | ir |
| `sections/geometry.py` | curve/plane intersection math | ir, numpy |
| `sections/frame_table.py` | frame table derivation | ir |
| `sections/section_builder.py` | cross-section assembly | geometry, ir |
| `sections/document.py` | lean JSON document build/serialise | all sections |
| `mcp/server.py`, `mcp/state.py` | MCP tools | sections, mcp SDK |

In nh-mcp: `examples\demo_ocx_pipeline.py` + `tests\test_ocx_pipeline.py`
(integration-marked). No changes to the nh-mcp server itself.

## 3. IR extension (ocx-model-validator)

All new fields are optional with defaults, so existing builder output and
tests remain valid.

- `IrPlate.outer_contour: IrCurve3D | None = None`
- `IrStiffener.trace: IrCurve3D | None = None`
- `IrPanel.unbounded_geometry: IrUnboundedGeometry | None = None` — a small
  union record: `surface: IrSurface3D | None`, `surface_ref: str | None`,
  `grid_ref: str | None` (ref plane id).
- `IrVessel` already holds `coordinate_systems` / ref planes; ensure the
  builder wires `IrCoordinateSystem.x_ref_plane_ids` to parseable
  `IrRefPlane` objects with plane origin/normal (x position derivable).

`OcxV3Builder` is extended to populate these from the existing xsdata
objects, reusing its geometry dispatch (Line3D, CircumArc3D, NURBS3D,
CompositeCurve3D, PolyLine3D already have IR types). Unknown curve types
are logged and left `None` (existing shallowness convention).

## 4. Section module (`ocx_model_validator/sections/`)

### 4.1 `geometry.py` — intersection math (Approach: pure Python + numpy)

- `plane_x(x_mm)` — the section plane X = x (normal = global X).
- `intersect_curve_plane(curve, x) -> list[tuple[y_mm, z_mm]]`:
  - `IrLine3D` / `IrPolyLine3D` segments: exact parametric solution.
  - `IrNurbs3D`: de Boor point evaluation (own ~50-line evaluator; no new
    dependency), coarse parameter sampling to bracket sign changes of
    (X(t) − x), then bisection to tolerance **0.1 mm**.
  - `IrCompositeCurve3D`: union of segment results (deduplicate points
    closer than tolerance).
  - `IrCircumArc3D`/others: sample-based fallback (same bracketing).
- No OpenCascade / trimesh: the data is dominated by lines and planes, and
  NH consumes 2D positions, not B-rep. (User-approved decision.)

### 4.2 `frame_table.py`

- `extract_frame_table(vessel) -> FrameTable` with
  `frame0_offset_mm: float` and `entries: list[tuple[label, spacing_mm]]`.
- Source: X ref planes of the global coordinate system, sorted by x.
  Frame labels come from ref-plane names (`X0` → `"0"`; non-numeric names
  kept verbatim). Spacing = distance to next plane; a new entry is emitted
  at every spacing change (handles non-uniform tables). This is exactly the
  input format of nh-mcp `setup_frame_table(frame0_offset, entries)`.
- `frame_to_x(frame_table, label) -> x_mm` and
  `nearest_frame(frame_table, x_mm)` helpers for the MCP tools.

### 4.3 `section_builder.py`

`build_section(vessel, x_mm) -> CrossSection` (frozen dataclasses):

- **Stiffeners:** for every stiffener with `function_type` longitudinal
  (or trace crossing the plane), intersect trace with the plane → (y, z).
  Multiple crossings (return stiffeners) produce one entry each.
- **Plates:** intersect each plate's outer contour with the plane. A plate
  cut by the plane yields ≥ 2 intersection points → pair consecutive
  points (sorted along the contour) into section segment(s)
  `(p1=(y,z), p2=(y,z))` with plate thickness (mm) and material ref.
  Plates with < 2 points are not in this section.
- **Profiles:** resolve `stiffener.section_ref` → `IrSection`/BarSection →
  NH profile strings via an explicit mapping table
  (OCX bar-section type → NH `profile_type` e.g. `"HpBulb"`, `"FlatBar"`;
  dimensions formatted space-separated, e.g. `"300 x 11"` — the format the
  NH ProfileLibrary parser accepts, established in nh-mcp work).
- **Spacing:** per stiffener from OCX spacing data when present, else
  nearest-neighbour distance between adjacent stiffener positions on the
  same panel; recorded per stiffener in mm.
- Items that cannot be resolved (missing profile ref, unsupported curve
  type, no material) are skipped and recorded as human-readable strings in
  `warnings` — never silently dropped.

### 4.4 `document.py` — the lean JSON document

```json
{
  "model": {"name": "...", "schema_version": "3.0.0", "source_file": "..."},
  "frame_table": {"frame0_offset": 0.0,
                   "entries": [["0", 800.0], ["148", 5690.0]]},
  "materials": [{"id": "...", "name": "A", "reh": 235.0}],
  "compartments": [{"name": "...", "type": "...", "volume_m3": 0.0,
                     "cog": [x, y, z],
                     "extents": {"min_x": 0, "max_x": 0, "min_y": 0,
                                  "max_y": 0, "min_z": 0, "max_z": 0}}],
  "cross_section": {
    "x": 118400.0,
    "frame": "148",
    "plates": [{"name": "...", "panel": "...", "p1": [y, z], "p2": [y, z],
                 "thickness": 19.0, "material_id": "..."}],
    "stiffeners": [{"name": "...", "panel": "...", "y": 0.0, "z": 0.0,
                     "profile_type": "HpBulb",
                     "profile_dimensions": "300 x 11",
                     "material_id": "...", "spacing": 800.0,
                     "web_angle": 90.0, "orientation": "Longitudinal"}]},
  "warnings": ["..."]
}
```

All lengths mm, `reh` MPa, volume m³, `cog` in mm. `materials` carries the
yield stress (`reh`) needed by `calculate_epp`/`calculate_stiffener`; the
OCX material catalogue provides it. Compartment `type` maps OCX
compartment purpose to nh-mcp tank-type strings (`BALLASTWATERTANK`,
`CARGOHOLD`, `VOIDSPACE`, …) via an explicit table with a fallback of the
verbatim OCX value. Serialisation via `dataclasses.asdict` + `json.dumps`;
a `load_document(path)` counterpart validates required keys.

## 5. OCX MCP server (`ocx_model_validator/mcp/`)

Same patterns as nauticushull-mcp (FastMCP over stdio, one model per
process, thin tools, errors propagate):

- `mcp/state.py` — module-level holder: `load(path)` parses + builds the
  IR once; `require_model()` raises with a "call load_model first" message.
- `mcp/server.py` — `mcp = FastMCP("ocx-mcp")`, console script
  `ocx-mcp = ocx_model_validator.mcp.server:main`. Tools:

| Tool | Signature | Returns |
|---|---|---|
| `load_model` | `(path: str)` | model name, schema version, part counts |
| `get_model_info` | `()` | same summary for the loaded model |
| `get_frame_table` | `()` | frame table dict (JSON schema section) |
| `get_compartments` | `()` | compartments list |
| `build_cross_section` | `(x: float \| None, frame: str \| None)` — exactly one | the full JSON document as dict |
| `save_cross_section` | `(path: str, x: float \| None, frame: str \| None)` | confirmation message |

Dependencies added to ocx-model-validator: `mcp>=1.0,<2`, `numpy`.
Unit tests call the tools as plain functions (FastMCP 1.x returns the
original function from `@mcp.tool()` — established in nh-mcp work).

## 6. nh-mcp integration (demo script)

`C:\PythonDev\nh-mcp\examples\demo_ocx_pipeline.py` (user-chosen
integration style):

1. Import ocx-model-validator directly — nh-mcp adds it to its `dev`
   dependency group as an editable path dependency
   (`{ path = "../ocx-model-validator", editable = true }`); it is not a
   runtime dependency of the nh-mcp server. Parse the VLCC model and build
   the JSON document at a chosen frame.
2. Start nh-mcp tool functions (same pattern as `demo_tanker_tutorial.py`):
   `initialize_api`, `load_workspace` (Tanker Tutorial workspace as the NH
   scratch project), `setup_frame_table` from `frame_table`,
   `create_compartment` + `create_standard_loading_conditions` +
   `set_compartment_density` from `compartments`.
3. For a selection of section items: `calculate_shell_plate` per plate
   segment and `calculate_stiffener` per stiffener (position, spacing,
   profile and reh from the JSON; adjacent compartment names from the
   compartment extents vs. the item position, with `"EXTERNAL"` for the
   shell side).
4. Print per-item summary tables (reusing the demo table style).

An integration test `tests\test_ocx_pipeline.py` (marked `integration`,
auto-skips without NH/model) asserts the pipeline yields > 0 plate and
stiffener results without errors.

Known constraint: principal dimensions and cross-section properties
(`set_principal_dimensions`, `setup_cross_section_properties`) are NOT
extracted from OCX in this phase — the demo supplies workspace/hardcoded
values, since the loaded NH workspace already carries them.

## 7. Error handling

- New exceptions in ocx-model-validator: `GeometryError`,
  `SectionError` (subclass existing hierarchy in `exeptions.py`).
- Intersection code raises `GeometryError` on malformed geometry
  (e.g. NURBS with inconsistent knots); the section builder converts
  per-item failures into `warnings` entries and continues; document-level
  failures (no X ref planes, no coordinate system) raise `SectionError`.
- MCP tools let exceptions propagate (FastMCP reports them as tool
  errors), mirroring nh-mcp.

## 8. Testing strategy

TDD throughout (each unit gets failing tests first):

1. **geometry.py** — synthetic curves with known analytic intersections:
   line through plane, polyline multiple crossings, NURBS arc (compare
   against exact circle points), composite dedup, tolerance behaviour.
2. **frame_table.py** — synthetic ref planes: uniform spacing → one entry;
   spacing changes → entry per change; label normalisation (`X0.8` etc.);
   frame↔x round trip.
3. **section_builder.py** — a small synthetic IrVessel (flat bottom panel,
   two stiffeners with line traces, one plate with rectangular contour):
   exact expected positions/segments; warning paths (missing profile).
4. **document.py** — build → serialise → load round trip; unit conversion
   (IR metres → JSON mm) asserted explicitly.
5. **mcp tools** — plain-function tests with a stubbed model state;
   tool registration/schema test (list_tools), like nh-mcp.
6. **Integration (ocx side)** — parse the real VLCC model: frame table has
   ~hundreds of X positions with plausible spacings; a midship section has
   > 50 stiffeners and > 10 plate segments; JSON document validates.
7. **Integration (pipeline)** — the nh-mcp demo/test above, real NH run.

Existing ocx-model-validator and nh-mcp test suites must stay green.

## 9. Out of scope (this phase)

- Principal dimensions / hull girder cross-section properties from OCX.
- Transverse stiffeners, brackets, pillars, face plates in the section.
- Writing NH CrossSectionPart XML (JSON only).
- EPP panel definitions (plate segments + stiffener positions suffice for
  `calculate_shell_plate` / `calculate_stiffener`).
- Y/Z ref-plane tables (only the X frame table is extracted).
