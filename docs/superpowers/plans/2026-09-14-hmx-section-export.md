# HMX Section Export — Implementation Plan

> **For the executor:** This plan is designed for subagent-driven or inline execution. Each task is
> self-contained: TDD (test first), exact commands, and a commit at the end. Run all commands from
> the repo root. Use `uv run pytest ...` for tests. Every commit message ends with the trailer:
> `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
>
> **Spec:** `docs/superpowers/specs/2026-09-14-hmx-section-export-design.md` (authoritative).
> Read it before starting.

## Overview

Export cross-sections from OCX models as Nauticus Hull **HMX** XML (`HullModel`), replacing JSON
as the default `section create` output. Add `--format xml|json` and `--rule-set DNV|RV5|CSR-H`
CLI options. `section plot` accepts both `.json` and `.hmx`. Includes Compartments and correct
bilge modeling (semicircular bilge → signed-radius SEGMENT inferred from OCX arc curves).

New modules: `ocx_model_validator/sections/hmx_export.py`, `hmx_import.py`.
Modified: `section_builder.py`, `document.py`, `cli.py`, `reporting/generators/model_extent.py`,
`pyproject.toml`, `.github/copilot-instructions.md`.

---

## Task 1: Schema test assets + xmlschema dev dep

**Goal:** XSDs available under `tests/data/hmx_schema/` and a session-scoped `hmx_schema` pytest
fixture that loads `HullModel_HMX.xsd` with XSD 1.1.

- [ ] Copy schemas (note the rename — `HullModel_HMX.xsd` includes `CrossSection_2DLX.xsd` but the
      source file is named `CrossSection_DLX.xsd`):

```powershell
New-Item -ItemType Directory -Force tests\data\hmx_schema | Out-Null
Copy-Item docs\superpowers\HullModel_HMX.xsd tests\data\hmx_schema\HullModel_HMX.xsd
Copy-Item "docs\superpowers\CrossSection_DLX.xsd" tests\data\hmx_schema\CrossSection_2DLX.xsd
Copy-Item docs\superpowers\Base.xsd tests\data\hmx_schema\Base.xsd
```

- [ ] Add `xmlschema` to the dev dependency group: `uv add --dev xmlschema`
- [ ] Add to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def hmx_schema():
    import xmlschema

    xsd = Path(__file__).parent / "data" / "hmx_schema" / "HullModel_HMX.xsd"
    return xmlschema.XMLSchema11(str(xsd))
```

- [ ] Write `tests/test_hmx_schema.py` with a smoke test: fixture loads, and
      `hmx_schema.is_valid(str(Path("docs/ISSCFrame170.hmx")))` is True (sample doc validates).
      If the sample does not validate, inspect errors — the fixture itself loading is the hard
      requirement; relax the sample assertion to `iter_errors` count reporting only if needed and
      note why in the test.
- [ ] `uv run pytest tests/test_hmx_schema.py`
- [ ] Commit: `test: add HMX schema assets and xmlschema fixture`

## Task 2: Public `extent_mm(vessel)` helper

**Goal:** Reusable model-extent helper for MainDimensions derivation.

- [ ] Test first (`tests/test_model_extent.py` — extend or create): using
      `make_synthetic_vessel()` from `tests/section_fixtures.py`, assert
      `extent_mm(vessel)` returns a dict with keys `min_x,max_x,min_y,max_y,min_z,max_z`
      and plausible values; assert it returns `None` for an empty vessel.
- [ ] In `ocx_model_validator/reporting/generators/model_extent.py`, add:

```python
def extent_mm(vessel) -> dict | None:
    """Return model bounding box in mm, or None if no points found."""
    notes: list[str] = []
    pts = _gather_points(vessel, notes)
    if not pts:
        return None
    xs, ys, zs = zip(*pts)
    return {
        "min_x": min(xs), "max_x": max(xs),
        "min_y": min(ys), "max_y": max(ys),
        "min_z": min(zs), "max_z": max(zs),
    }
```

(Adapt to the actual `_gather_points` signature/return shape — verify before writing.)
- [ ] `uv run pytest tests/test_model_extent.py`
- [ ] Commit: `feat: add public extent_mm helper for model bounding box`

## Task 3: SectionStiffener numeric dims + section_kind

**Goal:** `SectionStiffener` gains `section_kind` and numeric profile dims needed for LSTIFF.

- [ ] New fields on `SectionStiffener` (all optional, default `None`):
      `section_kind: str | None`, `h_mm`, `bf_mm`, `tw_mm`, `tf_mm` (floats).
      `section_kind` values: `"flat_bar" | "bulb_flat" | "t_section" | "l_section" |
      "l_overshoot_flange" | "l_overshoot_web"`.
- [ ] Refactor `_profile()` in `section_builder.py` to additionally return
      `(section_kind, h, bf, tw, tf)` derived from the IR section object; keep the existing
      `(profile_type, dims_str)` behavior intact. FlatBar: `bf=None`, `tf=None`, HMX later maps
      T=width. Distinguish the three L variants by IR class name
      (LBar/LBarOF/LBarOW-style names → l_section / l_overshoot_flange / l_overshoot_web).
- [ ] Tests first in `tests/test_sections_builder.py`: extend existing synthetic-vessel test to
      assert `section_kind` and dims on the produced stiffeners (fixture uses flat bar / bulb /
      T — check `section_fixtures.py` for which and assert accordingly).
- [ ] `uv run pytest tests/test_sections_builder.py`
- [ ] Commit: `feat: add section_kind and numeric dims to SectionStiffener`

## Task 4: SectionPlate arc fields + bilge inference

**Goal:** Plates whose defining OCX contour contains a transverse arc get
`radius_mm`, `arc_center_y_mm`, `arc_center_z_mm`.

- [ ] New optional fields on `SectionPlate`: `radius_mm`, `arc_center_y_mm`,
      `arc_center_z_mm` (default `None`).
- [ ] Add `_plate_arc_info(ir_plate, x_mm)` in `section_builder.py`:
  - Walk `ir_plate.outer_contour` segments (unwrap `IrCompositeCurve3D.segments`).
  - For `IrCircumArc3D`: compute circle via `sections.geometry._circle_from_three_points`
    on start/intermediate/end. Accept only if unit normal has `abs(n[0]) >= 0.99`
    (transverse arc). For `IrCircle3D`: use `center`, `diameter/2`, `normal` directly with the
    same normal test.
  - Among accepted arcs, pick the one whose center x is nearest to `x_mm`.
  - Return `(radius_mm, center_y_mm, center_z_mm)` or `None`. Catch `GeometryError`
    (collinear) and skip that segment.
- [ ] Wire into `_build_plates`: set the new fields on the produced `SectionPlate`s of that plate.
- [ ] Tests first (`tests/test_sections_builder.py`): build a synthetic plate whose contour is a
      composite of lines + one `IrCircumArc3D` lying in a transverse plane (constant x); assert
      radius/center are extracted; assert a longitudinal arc (normal along z) is ignored.
- [ ] `uv run pytest tests/test_sections_builder.py`
- [ ] Commit: `feat: infer bilge arc radius/center on SectionPlate`

## Task 5: `resolve_section` refactor in document.py

**Goal:** Shared frame/x resolution for JSON and HMX paths.

- [ ] Extract the inline x/frame resolution logic from `build_document` into:

```python
def resolve_section(vessel, x_mm=None, frame=None) -> tuple[FrameTable, CrossSection]:
    ...
```

      `build_document` calls it; behavior unchanged (same errors, same nearest-frame logic).
- [ ] Existing tests must stay green: `uv run pytest tests/test_sections_builder.py
      tests/test_sections_integration.py` (integration marker excluded by default addopts — run
      builder + any document tests that exist).
- [ ] Commit: `refactor: extract resolve_section from build_document`

## Task 6: hmx_export geometry helpers (chaining, radius, position, level codes)

**Goal:** Pure helper layer of `hmx_export.py`, fully unit-tested.

- [ ] Create `ocx_model_validator/sections/hmx_export.py` with:
  - `@dataclass _Chain: points: list[tuple[float, float]]; plates: list[SectionPlate]`
    (points are (y, z) mm vertices; plates parallel to segments, `len(points) == len(plates)+1`).
  - `_chain_segments(plates, tol=1.0) -> list[_Chain]`: greedy chaining, matching endpoints at
    both ends of a growing chain within `tol` mm; each plate used once; preserve per-segment
    plate association; leftover plates start new chains.
  - `_signed_radius(plate, p1, p2) -> float | None`: if `plate.radius_mm` is set, sign by
    `cross = dy * (cz - z1) - dz * (cy - y1)`; positive cross (center left of travel, CCW)
    → `+r`, else `-r`. Returns `None` when no arc.
  - `_arc_length_of(plate, p1, p2) -> float`: chord length if no arc; else `r * theta` where
    `theta = 2 * asin(min(1.0, chord / (2 * r)))`.
  - `_arc_position(chain, y, z) -> float`: per-segment chord projection with clamped t in [0,1];
    best (nearest) segment wins; result = cumulative segment lengths (arc-aware via
    `_arc_length_of`) + `t * seg_len`.
  - `_level1_code(plate, p1, p2, extent) -> str`: radius segment → `"BILGE"`;
    horizontal (`|dz| <= 0.05 * max(|dy|, 1)`) near min-z (within 5% of z-range) → `"GBOTTOM"`,
    near max-z → `"STRDECK"`; vertical segment with `|y| >= 0.95 * max_abs_y` → `"SIDE"`;
    else `"Undefined"`.
  - `_side(chain) -> str`: mean y over vertices; `> +1` → `"LEFT"`, `< -1` → `"RIGHT"`,
    else `"CENTER"`.
  - `_angles(stiffener) -> tuple[float, float]`: from `web_dir_y/z`:
    `web = degrees(atan2(web_dir_z, web_dir_y)) % 360`; `fl = 90.0 if web < 180 else 270.0`;
    fallback `(90.0, 270.0)` when dirs missing (append warning at call site).
  - `_MaterialIds`: maps yield value → sequential string id starting at `"1"`;
    `.id_for(yield_mpa)` and `.items()` for MaterialData emission.
  - `_LSTIFF_TYPE = {"flat_bar": 10, "bulb_flat": 20, "l_section": 31,
    "l_overshoot_flange": 35, "l_overshoot_web": 36, "t_section": 40}`.
- [ ] Tests first: `tests/test_hmx_export_helpers.py` covering: chaining of the synthetic-vessel
      plates (Plate A1 spans (0,0)-(2000,0)); two disjoint chains; signed radius both signs;
      arc length vs chord; `_arc_position` on a 2-segment chain; level codes for bottom/deck/
      side/bilge/undefined; `_side`; `_angles` incl. fallback; `_MaterialIds` sequencing.
- [ ] `uv run pytest tests/test_hmx_export_helpers.py`
- [ ] Commit: `feat: hmx_export geometry helpers with unit tests`

## Task 7: ShipData / FrameTable / Compartments / left-right resolution

**Goal:** Non-Scantling HMX blocks as lxml element builders in `hmx_export.py`.

- [ ] `_ship_data(rule_set, extent, warnings) -> Element`:
  - `rule_set` ∈ `{"DNV", "RV5", "CSR-H"}` selecting child element `DNVType` / `RV5Type` /
    `CSR-HType` (verify exact element names against `HullModel_HMX.xsd` before coding).
  - DNVType children in order: `ApplicableRules` (`RuleSet="DNV-1A1"`, `RuleEdition="2024"`),
    `MainDimensions`, element literally named `GeneralShipDataType`, `MaterialData`.
  - RV5/CSR-H: `ApplicableRules` (`RuleEdition` only), `MainDimensions`, `GeneralShipData`,
    `MaterialData`, **required** `IceClassData` (empty, attrs optional). RV5 extras optional — omit.
  - `MainDimensions` from `extent_mm` (m): Lbp≈(max_x−min_x)/1000, B≈(max_y−min_y)/1000,
    D≈(max_z−min_z)/1000; draught T = 0.7·D placeholder + warning. All attrs optional — emit
    what we have.
  - `GeneralShipDataType` required attrs (placeholders + warning): MaxServiceSpeed,
    MinNormBalDraught, HeavyBalDraught, DeepestEqWLDamaged, SlammingDraughtEmpty,
    SlammingDraughtFull = `"0"`; DeadWeightLT50000=`"false"`; FreeboardType=`"B"`;
    BilgKeel=`"false"`. ShipType=`"Other"` where applicable.
  - `MaterialData` rows from `_MaterialIds`.
- [ ] `_frame_table(ft: FrameTable) -> Element`: attrs `FrameOffset` (m,
      `frame0_offset_mm/1000`), `FrameRef="AP"`. `Spacing` rows from `ft.entries`
      (spacing in **metres**, must be in (0, 200) exclusive); first row `FrameNo="Stern"`.
- [ ] `_compartments(vessel, warnings) -> tuple[Element | None, dict[str, str]]`:
      reuse `build_compartments_block(vessel)` from `document.py`. Map tank types via
      `_COMPARTMENT_TYPE = {"VOIDSPACE": "VoidSpace", "BALLASTWATERTANK": "BallastWaterTank",
      "FUELTANK": "FuelOilTank", "FRESHWATERTANK": "FreshWaterTank", "CARGOHOLD": "CargoHold"}`
      else `"Undefined"` + warning. Per compartment: attrs Name/Type/Id; `General` (Volume,
      CgX/CgY/CgZ int mm, TopOfAirPipe, Length — omit missing); required choice child: emit
      `RV5` (`RV5_CompartmentData`: OverPressure from relief_valve_pressure_kpa, all optional);
      `Geometry/BoundingBox` with MinX..MaxZ (required — skip compartment + warning if extent
      all-None). Return element + `{compartment_name: bbox}` map for segment tagging.
  - Also implement `_segment_compartments(p_mid, normal, comp_boxes) -> (left, right)`:
    offset midpoint ± 100 mm along the segment's left normal (left = 90° CCW of travel
    direction); test each offset point against compartment bounding boxes (y/z at section x);
    return matched names or `None`.
- [ ] Tests: `tests/test_hmx_export_blocks.py` — ship data for all 3 rule sets (element names,
      required attrs present), frame table from a manually constructed `FrameTable`,
      compartments from a synthetic vessel with one compartment (bbox, type mapping, Undefined
      fallback), `_segment_compartments` left/right resolution with two boxes.
- [ ] `uv run pytest tests/test_hmx_export_blocks.py`
- [ ] Commit: `feat: hmx_export ShipData, FrameTable and Compartments builders`

## Task 8: Scantling assembly + build_hmx/save_hmx + XSD validation

**Goal:** Full document assembly; output validates against the schema.

- [ ] In `hmx_export.py`:
  - `build_hmx(vessel, cross_section, frame_table, rule_set="DNV") -> etree._Element`:
    1. Root `HullModel` (check XSD for target namespace / no-namespace; match sample
       `docs/ISSCFrame170.hmx`).
    2. Children in schema order: ShipData, FrameTable, Compartments?, CrossSections.
    3. `CrossSections` → one `Scantling` (`Section2DLX`) with children in order:
       `IDDATA` (NAME=model/section name, DATE=today ISO, SIGNATURE="ocx-model-validator",
       COMMENTS=""), `POSITION` (DISTAP = x/1000 m; MIDSHIP true iff
       `|x − min_x − Lbp/2| ≤ 0.05·Lbp`), `MATERIAL` (YIELDBOTT/YIELDDECK/YIELDBETW = mode of
       plate yields in bottom/deck/between z-bands, 15% bands, fallback 235),
       `MISC` (STRUCTTYPE="SECTION", HSIDE, STDSPAN = frame spacing at section x from
       `ft.entries` fallback 800, STDSPACE = median stiffener spacing fallback 800),
       then one `PANEL` per chain.
    4. PANEL children order: `BENDEFF` (100), `SHEAREFF` (100), `SHAPE`
       (SEGMENTs: Y, Z in m per vertex; Position=`_level1_code`; Girder="Undefined";
       Radius=`_signed_radius` (m) or "0"; LeftCompartment/RightCompartment from
       `_segment_compartments`), `PLATES` (per chain segment: Width=`_arc_length_of` (m),
       RefCode="CURVE", Thickness (mm per sample — verify against sample file), Yield,
       MaterialId, Material="STDSTEEL", Side=`_side`), `LONGS` (LSTIFF per stiffener assigned
       to nearest chain: Name, Position=`_arc_position` (m), RefCode="CURVE",
       Type=`_LSTIFF_TYPE[section_kind]` fallback 10 + warning, RusCode="", H/BF/T/TF from
       numeric dims (FlatBar: T=width rule), WebAngle/FlAngle=`_angles`, Span=STDSPAN,
       Yield, MaterialId, K="0", BuckStiff="false"), empty `CUTOUTS`, empty `TRVSTIFFS`.
       Multiple chains from one panel → multiple PANELs with the same name.
    5. Warnings list → `root.insert(0, etree.Comment("warnings: ..."))`.
  - `save_hmx(root, path)`:
    `etree.ElementTree(root).write(str(path), xml_declaration=True, encoding="UTF-8",
    pretty_print=True)`.
  - **Verify units against `docs/ISSCFrame170.hmx` sample before finalizing** (Y/Z/Width in m
    vs mm; Thickness/H/BF in mm) — the sample is authoritative where spec is ambiguous.
- [ ] Test: `tests/test_hmx_export.py` — build from synthetic vessel + manually constructed
      `FrameTable` (synthetic vessel has no X ref planes), save to tmp_path, assert
      `hmx_schema.is_valid(path)` and spot-check: 1 Scantling, expected PANEL count,
      LSTIFF count == stiffener count, a BILGE segment when arc plate present.
- [ ] `uv run pytest tests/test_hmx_export.py`
- [ ] Commit: `feat: full HMX Scantling assembly with XSD-validated output`

## Task 9: hmx_import — load .hmx for plotting

**Goal:** `load_hmx_document(path) -> dict` producing an nh-cross-section/1-shaped dict that
`render_svg` accepts.

- [ ] Create `ocx_model_validator/sections/hmx_import.py`:
  - Parse with lxml; locate first Scantling; raise `SectionError` if absent/malformed.
  - Rebuild `cross_section["plates"]`: walk SHAPE vertices per PANEL; each consecutive vertex
    pair + corresponding PLATES row → plate dict (y1,z1,y2,z2 in mm, thickness_mm, yield).
  - Rebuild `cross_section["stiffeners"]`: LSTIFF Position via cumulative chord `_point_at`
    along the SHAPE polyline (chord approximation acceptable for plotting); reverse
    `_LSTIFF_TYPE` for profile_type; web_dir from `(cos(WebAngle), sin(WebAngle))`.
  - Set `doc["schema"] = "nh-cross-section/1"` and minimal `section` metadata (x from
    POSITION/DISTAP).
- [ ] Test: `tests/test_hmx_import.py` — round-trip smoke: export synthetic vessel to .hmx,
      load it, assert plate endpoints/stiffener positions match originals within tolerance
      (1 mm for straight chains), and `render_svg(doc)` returns non-empty SVG.
- [ ] `uv run pytest tests/test_hmx_import.py`
- [ ] Commit: `feat: hmx_import loader for plotting .hmx documents`

## Task 10: CLI — --format, --rule-set, plot dispatch

**Goal:** Wire it all into `cli.py`.

- [ ] Add enums:

```python
class SectionFormat(str, Enum):
    xml = "xml"
    json = "json"

class HmxRuleSet(str, Enum):
    dnv = "DNV"
    rv5 = "RV5"
    csr_h = "CSR-H"
```

- [ ] `_default_section_output(model, frame, x_mm, suffix=".hmx")` — suffix param; callers pass
      `.hmx` for xml, `.json` for json.
- [ ] `section create`: add `--format` (default `SectionFormat.xml`) and `--rule-set`
      (default DNV). xml path: `resolve_section` → `build_hmx` → `save_hmx`. json path:
      unchanged `build_document`/`save_document`.
- [ ] `section plot`: dispatch loader by suffix — `.hmx` → `load_hmx_document`, `.json` →
      `load_document`, else error.
- [ ] Tests: extend `tests/test_cli_section.py` (typer CliRunner pattern): default output is
      `.hmx` and schema-valid; `--format json` still writes JSON; plot works on both formats;
      unknown suffix errors cleanly.
- [ ] `uv run pytest tests/test_cli_section.py`
- [ ] Commit: `feat: section create --format/--rule-set and .hmx plot support`

## Task 11: Round-trip / integration test

- [ ] `tests/test_hmx_roundtrip.py`: synthetic vessel with a bilge arc plate → export →
      validate against schema → import → plot SVG; assert BILGE segment has non-zero signed
      Radius and imported geometry matches within tolerance. If real `.3docx` models exist in
      `models/`, add an `@pytest.mark.integration` case exporting a real model.
- [ ] `uv run pytest tests/test_hmx_roundtrip.py`
- [ ] Full suite: `uv run pytest`
- [ ] Commit: `test: HMX round-trip and integration coverage`

## Task 12: Documentation

- [ ] Update `.github/copilot-instructions.md` CLI section: new `--format`/`--rule-set` options,
      `.hmx` default output, plot accepting both formats.
- [ ] Commit: `docs: document HMX export CLI options`

---

## Verification (definition of done)

1. `uv run pytest` — all green.
2. `uv run validator section create <model>.3docx --frame FRx` produces a `.hmx` that
   `xmlschema.XMLSchema11` validates.
3. `uv run validator section plot <out>.hmx -o s.svg` renders.
4. `--format json` path unchanged (existing JSON tests green).
5. Bilge arcs appear as BILGE SEGMENTs with signed Radius; compartment left/right tags present
   where compartments exist.
