# OCX v3 builder extension + IR/OCX alignment — design spec

**Date:** 2026-06-10
**Status:** Approved (alignment strategy chosen by user: *align IR classes with the OCX dataclasses*)
**Predecessor:** `2026-06-10-ir-model-extension-design.md` (IR dataclass layer — committed)

## Problem

The IR dataclass layer (committed in `f5cd36e`/`24d429f`) was authored *before* the
real OCX 3.1.0 field names were introspected. Several IR types declare fields that
do **not** exist in the OCX 3.1.0 bindings (`ocx.ocx_310.ocx_310`), so a builder
written against them would only ever populate `None`. `OcxV3Builder` also does not
yet extract any of the new IR collections (seams, geometry, cargoes, design-view,
coordinate systems, surfaces, holes, typed metadata).

## Decision

**Align the IR dataclasses to the OCX 3.1.0 structure, then extend `OcxV3Builder`
to populate them.** The IR remains schema-neutral in *typing* (OCX quantity wrappers
→ `Quantity`, OCX `*Ref` → `Ref`, OCX child-wrapper elements like `SplitBy`/`ComposedOf`
flattened away), but its **field set mirrors what OCX 3.1.0 actually provides**. No IR
field exists that has no OCX source.

### Alignment principles

1. **Names** follow IR snake_case conventions; where an OCX field renames a concept
   the IR adopts the OCX name (e.g. `radius` → `diameter`, `gross_tonnage` → `tonnage`).
2. **OCX quantity types** (`Tonnage`, `Lpp`, `CutbackDistance`, …) → `Quantity`.
3. **OCX `*Ref` elements** (`MaterialRef`, `SeamRef`, …) → `Ref`.
4. **OCX wrapper elements** that only group children (`SplitBy.seam`, `ComposedOf.plate`,
   `StiffenedBy.stiffener`, `ControlPtList.control_point`, `KnotVector.value`) are
   flattened — the IR stores the inner collection directly.
5. **`Point3D`/`Vector3D`**: OCX stores `coordinates`/`direction` as a list. The IR keeps
   the existing `x,y,z(,unit)` shape (a lossless unpacking of `coordinates[0:3]`); the
   builder unpacks. This is the one deliberate ergonomic divergence and is documented in
   each dataclass.
6. **Deep, low-value sub-trees** (coordinate-system reference planes, connection
   configuration internals, NURBS control nets) are represented by a *faithful subset*
   of OCX fields, explicitly noted, rather than a 1:1 mirror.
7. **Shallowness (overriding rule).** The IR mirrors OCX field *semantics*, **not** its
   nesting depth. OCX is deeply nested through grouping/wrapper elements
   (`PhysicalProperties`, `CompartmentProperties`, `ClassificationData`, `TraceLine`,
   `SplitBy`, `ControlPtList`, `XRefPlanes`, `ConnectionConfiguration`, …). The IR
   **flattens these away**:
   - Wrapper elements that only hold a child quantity/collection are *hoisted* — their
     contents land directly on the parent IR object (e.g. `PhysicalProperties.dry_weight`
     → `IrPlate.dry_weight`; `ClassificationData.principal_particulars` →
     `IrVessel.principal_particulars`; `TraceLine.composite_curve3_d` → `IrSeam.trace_line`
     as the curve itself).
   - Deep multi-level sub-trees are collapsed to **scalars, `Ref`s, id-lists, or a single
     flat `dict`** — never a chain of nested IR dataclasses. (e.g. coordinate-system ref
     planes → `list[str]` of plane ids, not nested `IrRefPlane` trees; hole parametric
     variants → one `dict`.)
   - Genuinely recursive *domain* structures (the design-view occurrence tree, composite
     curves) stay recursive but each node holds only **refs/ids and scalars**, never
     embedded part objects.
   The test for every new IR field: *is this one shallow hop from its parent, holding a
   scalar / Quantity / Ref / id-list / flat dict?* If it would require walking two or more
   OCX wrapper levels to reconstruct, flatten it.

## IR changes (before → after)

### geometry.py

| Type | Change |
|------|--------|
| `IrCircle3D` | `radius` → `diameter: Quantity` |
| `IrCircumArc3D` | `middle` → `intermediate` (OCX `intermediate_point`) |
| `IrEllipse3D` | add `major_diameter: Quantity`, `minor_diameter: Quantity`, `normal: IrVector3D` |
| `IrPolyLine3D` | add `is_closed: bool = False` (keep `vertices` = OCX `point3_d`) |
| `IrNurbs3D` | add `is_rational: bool = False`, `form: str | None` (degree/knot_vector/control_points kept) |
| `IrPlane3D` | add `udirection: IrVector3D` |
| `IrSphere3D` | `center` → `origin` |
| `IrCone3D` | replace `axis`,`half_angle` with `tip: IrPoint3D`, `base_radius: Quantity`, `tip_radius: Quantity` |
| `IrCylinder3D` | add `height: Quantity` |
| `IrExtrudedSurface` | replace `direction`,`length` with `sweep: IrVector3D`, `sweep_curve: IrCurve3D`, `face_boundary_curve: IrCurve3D` |
| `IrNurbsSurface` | add `u_knot_vector: list[float]`, `v_knot_vector: list[float]` |
| `IrCoordinateSystem` | replace `origin`,`primary_axis`,`secondary_axis` with `is_global: bool = False`, `local_origin: IrPoint3D | None`, `x_ref_plane_ids/y_ref_plane_ids/z_ref_plane_ids: list[str]` (faithful subset of `XRefPlanes`/`YRefPlanes`/`ZRefPlanes` + `LocalCartesian`) |

`IrLine3D`, `IrCompositeCurve3D` (generic ordered `segments` — justified polymorphic
abstraction, builder collects from all OCX typed lists), `IrPoint3D`, `IrVector3D`,
`IrRefPlane`, `IrSurface`, `IrSurfaceCollection` are unchanged.

### metadata.py

| Type | Change |
|------|--------|
| `IrShipDesignation` | fields → `ship_name`, `call_sign`, `number_imo`, `ship_type` (drop `flag_state` — lives on statutory) |
| `IrTonnageData` | fields → `tonnage: Quantity`, `dead_weight: Quantity` |
| `IrStatutoryData` | fields → `port_registration: str`, `flag_state: str` (freeboard/upper-deck move to principal particulars) |
| `IrBuilderInformation` | fields → `yard: str`, `designer: str`, `owner: str`, `year_of_build: str` |
| `IrPrincipalParticulars` | align to OCX: `lpp`, `rule_length`, `block_coefficient`, `moulded_breadth`, `moulded_depth`, `scantling_draught`, `design_speed`, `freeboard_length`, `normal_ballast_draught`, `heavy_ballast_draught`, `length_of_waterline`, `upper_deck_area`, `freeboard_type: str` (drop invented `displacement`/`deadweight`) |

### arrangement.py

| Type | Change |
|------|--------|
| `IrLiquidCargo` | fields → `density`, `carriage_pressure`, `cargo_type` (drop `filling_height`,`permeability`) |
| `IrGaseousCargo` | fields → `density`, `carriage_pressure`, `cargo_type`, `liquid_state: bool` |
| `IrBulkCargo` | fields → `stowage_factor`, `permeability: Quantity`, `angle_of_repose`, `cargo_type` (drop `stowage_height`) |
| `IrUnitCargo` | unchanged (`cargo_type`) |
| `IrOccurrence` | replace `definition_ref`,`transformation` with typed refs: `plate_ref`, `stiffener_ref`, `seam_ref`, `bracket_ref`, `pillar_ref`, `hole_contour_ref`, `edge_reinforcement_ref`, `lug_plate_ref`, `connected_bracket_ref` (all `Ref | None`), `type_value: str | None` |
| `IrOccurrenceGroup` | keep recursive `children`; add `type_value: str | None` |
| `IrDesignView` | add `vessel_ref: Ref | None` |
| `IrCompartment` | keep (note `cog`, `volume`, `filling_height` come from `CompartmentProperties`) |

### structural.py

| Type | Change |
|------|--------|
| `IrSeam` | fields → `id`, `name`, `guidref`, `trace_line: IrCurve3D | None` (drop `plate_refs`,`material_ref`,`section_ref`,`dry_weight`,`cog`,`function_type`). Source = `Panel.split_by.seam`. |
| `IrMember` | fields → `id`, `parent_ref`, `name`, `guidref`, `dry_weight`, `cog: IrCog`, `external_geometry_ref: Ref` (drop points/material/section). *No reachable vessel-tree source in 3.1.0 — kept aligned but builder leaves `members` empty unless a source appears.* |
| `IrEndCut` | align to OCX `EndCutEnd1/2`: `id`, `name`, `cutback_distance`, `web_cut_back_angle`, `web_nose_height`, `flange_cut_back_angle`, `flange_nose_height`, `symmetric_flange: bool`, `sniped: bool`, `feature_cope: IrFeatureCope | None`. Rename stiffener fields `end_cut_start`/`end_cut_end` → `end_cut_end1`/`end_cut_end2`. |

`IrPlate`, `IrBracket`, `IrStiffener` (other than end-cut field names), `IrPillar`,
`IrEdgeReinforcement`, `IrPanel`, `IrVessel` unchanged.

### catalogues.py / connections.py

- `IrHole2D` gains typed shape fields kept minimal: `contour: IrCurve3D | None` plus
  `parametric: dict | None` capturing the chosen parametric variant
  (`rectangular_hole`/`super_elliptical`/`symmetrical_hole`/`parametric_circle`). Faithful subset.
- `IrConnectionConfiguration` / `IrPenetration` remain minimal placeholders (ref fields
  only); full model still deferred. Builder records `id`/`name` and the present ref ids.

## Builder extension (`OcxV3Builder`)

New private methods, each pure (`getattr`-guarded) and returning IR objects, wired into
`build()` after the existing structural pass:

| Method | Reads | Produces |
|--------|-------|----------|
| `_build_point3d`/`_build_vector3d` | `Point3D.coordinates`,`Vector3D.direction` | `IrPoint3D`/`IrVector3D` |
| `_build_curve(obj)` | dispatch on curve class name | `IrLine3D`/`IrCircumArc3D`/`IrCircle3D`/`IrEllipse3D`/`IrPolyLine3D`/`IrNurbs3D`/`IrCompositeCurve3D` |
| `_build_surface(obj)` | dispatch on surface class name | `IrPlane3D`/`IrSphere3D`/`IrCone3D`/`IrCylinder3D`/`IrExtrudedSurface`/`IrNurbsSurface` |
| `_build_reference_surfaces` | `Vessel.reference_surfaces` | populate `surfaces`, `surface_collections` |
| `_build_coordinate_system` | `Vessel.coordinate_system` | populate `coordinate_systems`, `ref_planes` |
| `_build_seams_for_panel` | `Panel.split_by.seam` | populate `seams`, `panel.seam_ids` |
| `_build_end_cut(obj)` | `EndCutEnd1/2` | `IrEndCut` (+ `IrFeatureCope`) |
| `_build_cargoes_for_compartment` | `Compartment.{bulk,liquid,unit}_cargo` | populate cargo dicts with `compartment_ref` |
| `_build_design_view` | `Vessel.design_view` | populate `design_views` (recursive occurrence tree) |
| `_build_hole_catalogue` | root/vessel `HoleShapeCatalogue` | populate `hole_shape_catalogue` |
| `_build_metadata` (replace dict version) | ship designation / tonnage / statutory / builder info / principal particulars | typed IR metadata objects |

Existing helpers reused: `_qty`, `_enum`, `_ref`, `_cog`, `_register`. Add `_pt`
(Point3D→IrPoint3D) and `_vec` (Vector3D→IrVector3D) helpers. `_SECTION_TYPE_MAP`
pattern (substring on lowercased class name) is reused for curve/surface dispatch via
new `_CURVE_DISPATCH`/`_SURFACE_DISPATCH` maps.

Stiffener `_build_stiffener` extended to populate `end_cut_end1`/`end_cut_end2` and
`penetrations`.

## Data flow

```
Vessel
 ├─ coordinate_system ─────────► _build_coordinate_system ─► coordinate_systems, ref_planes
 ├─ reference_surfaces ────────► _build_reference_surfaces ─► surfaces, surface_collections
 ├─ ship_designation/tonnage_data/statutory_data/builder_information/
 │   classification_data.principal_particulars ─► _build_metadata ─► typed IR fields
 ├─ design_view ───────────────► _build_design_view ─► design_views
 ├─ panel[*]
 │    ├─ split_by.seam ────────► _build_seams_for_panel ─► seams
 │    ├─ stiffened_by.stiffener.{end_cut_end1,end_cut_end2,penetration} ─► _build_stiffener
 │    └─ composed_of.{plate,bracket,pillar} (already handled)
 └─ (HoleShapeCatalogue) ──────► _build_hole_catalogue
Compartment[*].{bulk,liquid,unit}_cargo ─► _build_cargoes_for_compartment
```

## Error handling

- All raw access via `getattr(obj, "field", None)`; missing fields degrade to `None`/`[]`.
- Curve/surface dispatch falls back to `None` (logged at `debug`) for unknown class names.
- Duplicate ids recorded via `_register` into `vessel.duplicate_ids` (existing behaviour).
- No exceptions raised for absent optional structure — a sparse model yields a sparse IR.

## Testing

- Mirror `tests/test_ir_builder.py` stub style: inline OCX-shaped stub classes (matching
  the real field names above) fed to each `_build_*` method, asserting IR output.
- New test modules under `tests/`: `test_builder_geometry.py`, `test_builder_metadata.py`,
  `test_builder_cargoes.py`, `test_builder_seams_endcuts.py`, `test_builder_design_view.py`,
  `test_builder_surfaces_coords.py`.
- Update the IR-layer tests that assert the *old* field names
  (`test_ir_geometry.py`, `test_ir_metadata.py`, `test_ir_structural_additions.py`,
  `test_ir_arrangement_additions.py`) to the aligned fields.
- `tests/test_ir_builder.py::MISSING_IR_CLASSES` kept in sync.
- Gate: `uv run pytest` green after every phase.

## Out of scope

- Full connection-configuration / penetration semantics (placeholders remain).
- `IrMember` population (no 3.1.0 vessel-tree source).
- Unit→SI conversion of new quantities (existing `UnitConverter` already covers it).
- Older schema majors (v3 builder only).
