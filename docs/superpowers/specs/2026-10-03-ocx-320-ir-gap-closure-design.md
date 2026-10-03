# OCX 3.2.0 IR Gap Closure

**Date:** 2026-10-03
**Status:** Approved
**Scope:** Close remaining IR gaps against OCX schema 3.2.0; one coordinated change covering IR, `OcxV3Builder`, stub generation from `models/TR05`, and the parametrized test suite.

---

## Problem Statement

OCX 3.2.0 model files (now in `models/TR05/`, all `schemaVersion="3.2.0"`) parse through the existing pipeline — `(3, 2)` is registered to `OcxV3Builder` in the factory — but silently lose data:

- `_build_materials` iterates `mc.material`, which no longer exists in 3.2.0 (`MaterialCatalogue` now holds `steel` and `aluminium` lists).
- Part builders read `physical_properties`, removed in 3.2.0 in favour of `MassProperties` (moulded/physical dry weight and centres of gravity). Dry weight and CoG come back `None` for every part.
- None of the genuinely new 3.2.0 fields (renewal thicknesses, voluntary thickness additions, ref offsets, orientation rules, surface `Normal`/`PointOnSurface`, `Ellipse` hole contours, `TraceLine` refs, `bracket_ref` on penetrations, `minimum_ballast_draught`, `BulkCargo.density`) reach the IR.

There are no 3.2.0 stubs in `tests/data/`, so the parametrized suite never exercises the 3.2.0 binding.

### Field-level diff, 3.1.0 → 3.2.0 (from the xsdata bindings)

**New elements (39):** `Steel`, `Aluminium`, `MetallicMaterial`, `MassProperties`, `MouldedDryWeight`, `PhysicalDryWeight`, `MouldedCenterOfGravity`, `PhysicalCenterOfGravity`, `WeldedYieldStrength`, `UnweldedYieldStrength`, `WeldedTensileStrength`, `UnweldedTensileStrength`, `RenewalThickness`, `WebRenewalThickness`, `FlangeRenewalThickness`, `VoluntaryThicknessAddition`, `VoluntaryWebThicknessAddition`, `VoluntaryFlangeThicknessAddition`, `OffsetDirection`, `OrientationRuleValue`, `PointOnSurface`, `ContourMidPoint`, `Ellipse`, `MinimumBallastDraught`, `StrStiffenerRef`, `StrSeamRef`, `StrEdgeReinforcementRef`, `UnboundedGridRef`, `UnboundedSurfaceRef` (plus `*T` type variants).

**Removed (5):** `Material`, `MaterialT`, `PhysicalProperties`, `PhysicalPropertiesT`, `DryWeight`.

**Changed (key items):**
- All structure parts (`Plate`, `Panel`, `Bracket`, `Stiffener`, `Pillar`, `Member`, `EdgeReinforcement`): `physical_properties` → `mass_properties`.
- `Stiffener`, `EdgeReinforcement`: + `orientation_rule`.
- `Plate`, `Panel`: + `point_on_surface`.
- `MaterialCatalogue`: `material` → `steel` + `aluminium`.
- `PlateMaterial`: + `renewal_thickness`, `voluntary_thickness_addition`.
- `SectionRef`: + `web_renewal_thickness`, `flange_renewal_thickness`, `voluntary_web_thickness_addition`, `voluntary_flange_thickness_addition`.
- Refs (`BoundedRef`, `CellBoundary`, `EdgeCurveRef`, `GridRef`, `PanelRef`, `SeamRef`, `StiffenerRef`, `SurfaceRef`, `EdgeReinforcementRef`): + `offset`, `offset_direction`.
- `Occurrence`: `stiffener_ref`/`seam_ref`/`edge_reinforcement_ref` → `str_stiffener_ref`/`str_seam_ref`/`str_edge_reinforcement_ref`.
- `UnboundedGeometry`: `grid_ref`/`surface_ref` → `unbounded_grid_ref`/`unbounded_surface_ref`.
- Surfaces (`Plane3D`, `Sphere3D`, `Cone3D`, `Cylinder3D`, `ExtrudedSurface`, `NurbsSurface`, `Surface`): + `normal`, `point_on_surface`; `Plane3D` loses `origin`.
- `Hole2D`: + `ellipse`, `rectangular_mickey_mouse_ears`.
- `RoundBar`: `height` → `diameter`; `SuperElliptical`: `height`/`width` → `major_diameter`/`minor_diameter`.
- `PlateCutBy`: `outer_contour` → `inner_contour`; `ContourBounds`: + `contour_mid_point`.
- `Penetration`, `ConnectionConfiguration`: + `bracket_ref`.
- `PrincipalParticulars`: + `minimum_ballast_draught`; `BulkCargo`: + `density`.
- `TraceLine`: + `edge_curve_ref`, `edge_reinforcement_ref`, `grid_ref`, `panel_ref`, `seam_ref`, `stiffener_ref`, `surface_ref`.
- `BarSection`: + `catalogue_reference`.

## Decisions (user-approved)

1. **IR shape strategy: adopt 3.2.0 shapes as the IR canon.** The v3 builder maps older 3.x fields onto the 3.2.0-shaped IR.
2. **Coverage: full.** Every new 3.2.0 field is captured in the IR.
3. **Builder: single `OcxV3Builder` for all 3.x.** Reads new names first, falls back to old. No new builder class; no factory changes.
4. **Testing: parametrized.** Generate `tests/data/ocx_320_stubs/` from `models/TR05` and let the existing version-parametrized suite cover both 3.1.0 and 3.2.0.
5. **Delivery: one coordinated change** (IR + builder + stubs + tests in a single spec/plan).

---

## Design

### 1. IR changes (`ocx_model_validator/model/ir/`)

All additions default to `None` or `[]`; no field access raises.

**`base.py`**
- New frozen dataclass `IrMassProperties`: `moulded_dry_weight: Quantity | None`, `physical_dry_weight: Quantity | None`, `moulded_cog: IrCog | None`, `physical_cog: IrCog | None`.
- `Ref` gains `offset: Quantity | None` and `offset_direction: IrVector3D | None` (covers every 3.2.0 ref type uniformly).

**`structural.py`**
- `IrPlate`, `IrBracket`, `IrStiffener`, `IrPillar`, `IrEdgeReinforcement`, `IrMember`, `IrPanel`: replace `dry_weight`/`cog` fields with `mass_properties: IrMassProperties | None`.
- `IrStiffener`, `IrEdgeReinforcement`: add `orientation_rule: str | None`.
- `IrPlate`, `IrPanel`: add `point_on_surface: IrPoint3D | None`.
- `IrPlate`, `IrBracket` (plate-material scantlings): add `renewal_thickness: Quantity | None`, `voluntary_thickness_addition: Quantity | None`.
- `IrStiffener`, `IrPillar`, `IrEdgeReinforcement` (section-ref scantlings): add `web_renewal_thickness`, `flange_renewal_thickness`, `voluntary_web_thickness_addition`, `voluntary_flange_thickness_addition` (all `Quantity | None`).

**`catalogues.py`**
- `IrMaterial`: add `material_type: str | None` (`"steel"` / `"aluminium"` / `None` for 3.1-era materials), `welded_yield_strength`, `unwelded_yield_strength`, `welded_tensile_strength`, `unwelded_tensile_strength` (all `Quantity | None`). Existing fields kept; for 3.1 models the legacy yield/tensile values populate the existing fields as before.
- `IrHole2D`: support `ellipse` and `rectangular_mickey_mouse_ears` contours (dimensions flattened per the existing hole-contour pattern).

**`geometry.py`**
- `IrPlane3D`: rename `origin` → `point_on_surface` (IR canon follows 3.2.0; builder maps 3.1 `origin` into it).
- `IrSphere3D`, `IrCone3D`, `IrCylinder3D`, `IrExtrudedSurface`, `IrNurbsSurface`, `IrSurface`: add `normal: IrVector3D | None` and `point_on_surface: IrPoint3D | None` where 3.2.0 added them.
- `IrUnboundedGeometry`: field names stay IR-neutral (`grid_refs`, `surface_refs`); only the builder's source element names change.

**`sections.py`**
- `IrRoundSection`: populated from `diameter` (3.2.0) with fallback from `height` (3.1.0). Field name: `diameter`.
- SuperElliptical hole contour dimensions follow `major_diameter`/`minor_diameter` naming.
- `IrSection` base: add `catalogue_reference: str | None` (from `BarSection.catalogue_reference`), inherited by all typed section classes.

**`connections.py`**
- `IrConnectionConfiguration` and `IrPenetration`: add `bracket_ref: Ref | None` (corrected during planning: the 3.2.0 binding models `BracketRef` as a single element, not a list).

**`metadata.py` / `arrangement.py`**
- `IrPrincipalParticulars`: add `minimum_ballast_draught: Quantity | None`.
- `IrBulkCargo`: add `density: Quantity | None`.
- `IrOccurrence`: unchanged shape; builder reads new `str_*_ref` element names.
- Trace-line refs: the owning IR objects (`IrStiffener`, `IrSeam`, `IrEdgeReinforcement`) gain `trace_refs: list[Ref]` capturing `TraceLine` child refs (`edge_curve_ref`, `grid_ref`, `panel_ref`, `seam_ref`, `stiffener_ref`, `surface_ref`, `edge_reinforcement_ref`).
- `PlateCutBy` handling follows `inner_contour` (3.2.0) with fallback to `outer_contour` (3.1.0); IR field name: `inner_contour`.
- Contour bounds gain `contour_mid_point: IrPoint3D | None`.

### 2. Builder changes (`builders/v3_builder.py`)

All raw access stays `getattr(obj, "field", None)`. Pattern: **read 3.2.0 name first, fall back to 3.1.0 name.**

- New helper `_mass_properties(raw) -> IrMassProperties | None`:
  - 3.2.0 path: read `raw.mass_properties` → moulded/physical dry weights and CoGs.
  - Fallback: read legacy `raw.physical_properties` → map `dry_weight` → `moulded_dry_weight`, `center_of_gravity` → `moulded_cog`; physical variants stay `None`.
  - Used by `_build_plate`, `_build_bracket`, `_build_stiffener`, `_build_pillar`, `_build_edge_reinforcement`, `_build_member`, `_build_panel`.
- `_build_materials`: iterate `mc.steel` and `mc.aluminium` (setting `material_type`), falling back to `mc.material` when both are absent. Extract welded/unwelded yield and tensile strengths when present.
- `_material_ref`: also extract `renewal_thickness` and `voluntary_thickness_addition` from `PlateMaterial`.
- Section-ref extraction: extract the four web/flange renewal/voluntary-addition quantities from `SectionRef`.
- `_ref`: additionally read `offset` and `offset_direction` onto `Ref`.
- `_build_unbounded`: read `unbounded_grid_ref`/`unbounded_surface_ref`, fallback `grid_ref`/`surface_ref`.
- `_build_occurrence`: read `str_stiffener_ref`/`str_seam_ref`/`str_edge_reinforcement_ref`, fallback to old names.
- `_build_surface`: extract `normal` and `point_on_surface`; for `Plane3D`, populate `point_on_surface` from `point_on_surface` (3.2.0) or `origin` (3.1.0).
- `_build_contour` dispatch: add `Ellipse` (reuse `IrEllipse3D` semantics) and `RectangularMickeyMouseEars`; `SuperElliptical` reads `major_diameter`/`minor_diameter` with fallback to `height`/`width`; handle `contour_mid_point`.
- `_build_section`: `RoundBar` reads `diameter` with fallback to `height`.
- Trace lines: extract the new `TraceLine` child refs into `trace_refs`.
- Misc: `orientation_rule`, `bracket_ref` (single) on penetrations/connection configurations, `minimum_ballast_draught`, `BulkCargo.density`, `PlateCutBy.inner_contour` fallback, `BarSection.catalogue_reference`.

**No factory changes** — `(3, 2)` is already registered.

### 3. Stubs & testing

- Place of truth: `models/TR05/*.3docx` (schema 3.2.0, plain XML). Run `validator generate-stubs` → new `tests/data/ocx_320_stubs/`. Existing `ocx_310_stubs` untouched. `conftest.py` auto-discovers `ocx_320_stubs` (digits-only version), so the `ocx_stub_version` parametrization immediately covers both versions.
- Stub-driven tests stay version-tolerant: assert fields are populated when the stub contains the element, `None` otherwise (existing convention).
- `test_builders.py` (inline raw stub classes) gains explicit dual-path cases:
  - raw part with `mass_properties` vs raw part with legacy `physical_properties` → both yield populated `IrMassProperties`;
  - material catalogue with `steel`/`aluminium` vs legacy `material` → both yield `IrMaterial` entries (with/without `material_type`);
  - `UnboundedGeometry`, `Occurrence`, `Plane3D`, `RoundBar` old/new name fallbacks;
  - new-field extraction: renewal thicknesses, ref offsets, orientation rule, `point_on_surface`.
- Migrate any existing tests referencing `dry_weight`/`cog` on IR parts to `mass_properties`.

### 4. Error handling, compatibility, documentation

- Missing fields degrade to `None` — never raise (`getattr` convention preserved).
- Report commands (`frame-table`, `compartments`, `all`) migrate `dry_weight`/`cog` reads to `mass_properties.moulded_dry_weight` / `mass_properties.moulded_cog`. Output structure unchanged.
- `IrVessel.schema_version` still records the source version; no public API change beyond the IR field renames listed above.
- Update `ocx_model_validator.md` and `.github/copilot-instructions.md` where they reference `PhysicalProperties` flattening.

## Success criteria

1. `uv run pytest` is green with both `ocx_310_stubs` and the new `ocx_320_stubs` discovered.
2. Building `models/TR05/tr05_tc04a_mbrh.3docx` yields an `IrVessel` with non-empty `materials` (with `material_type` set) and populated `mass_properties` on parts that carry `MassProperties`.
3. Building a 3.1.0 stub model still yields dry weight/CoG data (now via `mass_properties.moulded_*`) — no regression.
4. `validator report all` runs without error on a TR05 model.

## Out of scope

- 3.2.0 release candidates (`ocx_320rc*`) — conftest intentionally skips them.
- New report content for the new fields (reports only migrate off removed fields).
- Schema 4.x support.
