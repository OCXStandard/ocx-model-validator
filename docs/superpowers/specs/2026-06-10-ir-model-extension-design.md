# IR Model Extension — OCX Schema 3.1.0 Full Coverage

**Date:** 2026-06-10  
**Status:** Approved  
**Scope:** Extend `ocx_model_validator/model/ir/` to cover all global `xs:element` objects in OCX schema 3.1.0

---

## Problem Statement

The current `model/ir.py` covers only the core structural parts (`Vessel`, `Panel`, `Plate`, `Bracket`, `Stiffener`, `Pillar`, `EdgeReinforcement`), catalogues (`Material`, section types), and arrangement (`Compartment`, `PhysicalSpace`). OCX schema 3.1.0 defines ~250 global element types; the IR covers roughly 30 of them. Downstream tools are forced to fall back to raw `dict` fields on `IrVessel` or bypass the IR entirely for geometry, metadata, design view, cargoes, features, and connections.

---

## Approach: Package split (Approach B)

Convert `model/ir.py` into a package `model/ir/` with domain-focused submodules. All existing `from ocx_model_validator.model.ir import X` imports remain valid — `__init__.py` re-exports the full public surface.

### Module layout

```
ocx_model_validator/model/ir/
├── __init__.py       ← re-exports every public type (backward-compatible)
├── base.py           ← Quantity, Ref, IrCog, IrUnit, ParentRef, ParentKind
├── structural.py     ← IrPlate, IrBracket, IrStiffener, IrPillar, IrEdgeReinforcement,
│                        IrSeam, IrMember, IrEndCut, IrFeatureCope, IrPanel, IrVessel,
│                        IrLimitedByRef
├── sections.py       ← IrSection base + all typed subclasses (moved from ir.py as-is)
├── geometry.py       ← IrPoint3D, IrVector3D, all IrCurve3D subclasses,
│                        all IrSurface3D subclasses, IrCoordinateSystem, IrRefPlane,
│                        IrSurface, IrSurfaceCollection
├── arrangement.py    ← IrCompartment, IrPhysicalSpace, IrLiquidCargo, IrGaseousCargo,
│                        IrBulkCargo, IrUnitCargo, IrDesignView, IrOccurrenceGroup,
│                        IrOccurrence
├── catalogues.py     ← IrHole2D, IrHoleShapeCatalogue
├── metadata.py       ← IrShipDesignation, IrPrincipalParticulars, IrStatutoryData,
│                        IrTonnageData, IrBuilderInformation
└── connections.py    ← IrConnectionConfiguration (placeholder), IrPenetration (placeholder)
```

---

## Detailed Design

### `base.py` — no changes

`Quantity`, `Ref`, `IrCog`, `IrUnit`, `ParentRef`, `ParentKind` move here unchanged.

---

### `geometry.py`

All geometry types are `frozen=True` dataclasses.

#### Primitive value types

```python
@dataclass(frozen=True)
class IrPoint3D:
    """A 3D point in model coordinates."""
    x: float
    y: float
    z: float
    unit: str   # OCX unit id, e.g. 'Um', 'Umm'

@dataclass(frozen=True)
class IrVector3D:
    """A dimensionless 3D direction vector."""
    x: float
    y: float
    z: float
```

#### Curve hierarchy

```python
@dataclass(frozen=True)
class IrCurve3D:
    """Abstract base for all 3D curve types.
    curve_length has no default — builders MUST pass it (None if absent in model).
    """
    curve_length: Quantity | None   # required positional field
    id: str | None = None

@dataclass(frozen=True)
class IrLine3D(IrCurve3D):
    start: IrPoint3D | None = None
    end: IrPoint3D | None = None

@dataclass(frozen=True)
class IrCircumArc3D(IrCurve3D):
    start: IrPoint3D | None = None
    middle: IrPoint3D | None = None
    end: IrPoint3D | None = None

@dataclass(frozen=True)
class IrCircle3D(IrCurve3D):
    center: IrPoint3D | None = None
    radius: Quantity | None = None
    normal: IrVector3D | None = None

@dataclass(frozen=True)
class IrPolyLine3D(IrCurve3D):
    vertices: list[IrPoint3D] = field(default_factory=list)

@dataclass(frozen=True)
class IrCompositeCurve3D(IrCurve3D):
    segments: list[IrCurve3D] = field(default_factory=list)

@dataclass(frozen=True)
class IrEllipse3D(IrCurve3D):
    center: IrPoint3D | None = None
    major_axis: IrVector3D | None = None
    minor_axis: IrVector3D | None = None

@dataclass(frozen=True)
class IrNurbs3D(IrCurve3D):
    degree: int | None = None
    knot_vector: list[float] = field(default_factory=list)
    control_points: list[IrPoint3D] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
```

#### Surface hierarchy

```python
@dataclass(frozen=True)
class IrSurface3D:        # abstract base
    id: str | None = None

@dataclass(frozen=True)
class IrPlane3D(IrSurface3D):
    origin: IrPoint3D | None = None
    normal: IrVector3D | None = None

@dataclass(frozen=True)
class IrSphere3D(IrSurface3D):
    center: IrPoint3D | None = None
    radius: Quantity | None = None

@dataclass(frozen=True)
class IrCone3D(IrSurface3D):
    origin: IrPoint3D | None = None
    axis: IrVector3D | None = None
    half_angle: Quantity | None = None

@dataclass(frozen=True)
class IrCylinder3D(IrSurface3D):
    origin: IrPoint3D | None = None
    axis: IrVector3D | None = None
    radius: Quantity | None = None

@dataclass(frozen=True)
class IrExtrudedSurface(IrSurface3D):
    base_curve: IrCurve3D | None = None
    direction: IrVector3D | None = None
    length: Quantity | None = None

@dataclass(frozen=True)
class IrNurbsSurface(IrSurface3D):
    u_degree: int | None = None
    v_degree: int | None = None
    control_points: list[list[IrPoint3D]] = field(default_factory=list)
```

#### Standalone reference geometry

```python
@dataclass(frozen=True)
class IrCoordinateSystem:
    id: str
    name: str | None = None
    origin: IrPoint3D | None = None
    primary_axis: IrVector3D | None = None
    secondary_axis: IrVector3D | None = None

@dataclass(frozen=True)
class IrRefPlane:
    id: str
    name: str | None = None
    reference_plane: IrPlane3D | None = None

@dataclass(frozen=True)
class IrSurface:
    id: str
    name: str | None = None
    guidref: str | None = None
    geometry: IrSurface3D | None = None

@dataclass(frozen=True)
class IrSurfaceCollection:
    id: str
    name: str | None = None
    surfaces: list[IrSurface] = field(default_factory=list)
```

---

### `structural.py` — additions to existing types

#### New types

```python
@dataclass
class IrSeam:
    """Weld/connection line that limits plates."""
    id: str
    name: str | None = None
    guidref: str | None = None
    plate_refs: list[Ref] = field(default_factory=list)
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    function_type: str | None = None

@dataclass
class IrMember:
    """Structural beam/column element."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    start_point: IrPoint3D | None = None
    end_point: IrPoint3D | None = None
    dry_weight: Quantity | None = None
    cog: IrPoint3D | None = None          # 3D point, not IrCog
    function_type: str | None = None

@dataclass(frozen=True)
class IrEndCut:
    """Stiffener end detailing (one instance per stiffener end)."""
    sniped: bool = False
    cope_height: Quantity | None = None
    cope_length: Quantity | None = None
    cope_radius: Quantity | None = None
    flange_cutback_angle: Quantity | None = None
    web_cutback_angle: Quantity | None = None

@dataclass(frozen=True)
class IrFeatureCope:
    """Cope feature on a structural element."""
    id: str
    name: str | None = None
    guidref: str | None = None
    cope_height: Quantity | None = None
    cope_length: Quantity | None = None
    cope_radius: Quantity | None = None
```

#### `IrStiffener` — new fields

```python
    end_cut_start: IrEndCut | None = None
    end_cut_end:   IrEndCut | None = None
    penetrations:  list[IrPenetration] = field(default_factory=list)
```

#### `IrPanel` — new fields

```python
    seam_ids:         list[str] = field(default_factory=list)
    member_ids:       list[str] = field(default_factory=list)
    hole_shape_refs:  list[Ref] = field(default_factory=list)
```

---

### `arrangement.py` — additions

#### Cargo types

```python
@dataclass
class IrLiquidCargo:
    id: str; name: str | None = None; guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    filling_height: Quantity | None = None
    permeability: Quantity | None = None

@dataclass
class IrGaseousCargo:
    id: str; name: str | None = None; guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    carriage_pressure: Quantity | None = None

@dataclass
class IrBulkCargo:
    id: str; name: str | None = None; guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    stowage_factor: Quantity | None = None
    stowage_height: Quantity | None = None
    angle_of_repose: Quantity | None = None

@dataclass
class IrUnitCargo:
    id: str; name: str | None = None; guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
```

#### Design view — recursive product tree

> **Note:** `IrOccurrenceGroup.children` is a recursive type. Modules using these types must include `from __future__ import annotations` at the top for the forward reference to resolve correctly.

```python
@dataclass
class IrOccurrence:
    id: str; name: str | None = None; guidref: str | None = None
    definition_ref: Ref | None = None
    transformation: dict | None = None   # raw geometry transform

@dataclass
class IrOccurrenceGroup:
    """Can nest IrOccurrenceGroup and IrOccurrence at any depth."""
    id: str; name: str | None = None; guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)

@dataclass
class IrDesignView:
    id: str; name: str | None = None; guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)
```

---

### `catalogues.py`

```python
@dataclass(frozen=True)
class IrHole2D:
    """Hole shape definition from HoleShapeCatalogue."""
    id: str; name: str | None = None; guidref: str | None = None
    contour: IrCurve3D | None = None

@dataclass
class IrHoleShapeCatalogue:
    id: str; name: str | None = None
    holes: dict[str, IrHole2D] = field(default_factory=dict)
```

---

### `metadata.py`

Replaces the raw `dict | None` fields on `IrVessel`.

```python
@dataclass(frozen=True)
class IrShipDesignation:
    vessel_name: str | None = None
    imo_number: str | None = None
    call_sign: str | None = None
    flag_state: str | None = None

@dataclass(frozen=True)
class IrTonnageData:
    gross_tonnage: Quantity | None = None
    net_tonnage: Quantity | None = None

@dataclass(frozen=True)
class IrPrincipalParticulars:
    lpp: Quantity | None = None
    moulded_breadth: Quantity | None = None
    moulded_depth: Quantity | None = None
    design_speed: Quantity | None = None
    displacement: Quantity | None = None
    deadweight: Quantity | None = None
    block_coefficient: Quantity | None = None
    scantling_draught: Quantity | None = None
    normal_ballast_draught: Quantity | None = None
    heavy_ballast_draught: Quantity | None = None

@dataclass(frozen=True)
class IrStatutoryData:
    freeboard_type: str | None = None
    freeboard_length: Quantity | None = None
    upper_deck_area: Quantity | None = None
    tonnage_data: IrTonnageData | None = None

@dataclass(frozen=True)
class IrBuilderInformation:
    builder_name: str | None = None
    yard_number: str | None = None
    delivery_date: str | None = None
```

---

### `connections.py` — placeholders

```python
@dataclass
class IrConnectionConfiguration:
    """Placeholder — full definition in a future design."""
    id: str
    name: str | None = None

@dataclass
class IrPenetration(IrConnectionConfiguration):
    """Stiffener penetration — subtype of IrConnectionConfiguration. Placeholder."""
    pass
```

---

### `IrVessel` — new fields summary

| Field | Type | Notes |
|---|---|---|
| `seams` | `dict[str, IrSeam]` | new |
| `members` | `dict[str, IrMember]` | new |
| `liquid_cargoes` | `dict[str, IrLiquidCargo]` | new |
| `gaseous_cargoes` | `dict[str, IrGaseousCargo]` | new |
| `bulk_cargoes` | `dict[str, IrBulkCargo]` | new |
| `unit_cargoes` | `dict[str, IrUnitCargo]` | new |
| `coordinate_systems` | `dict[str, IrCoordinateSystem]` | new |
| `ref_planes` | `dict[str, IrRefPlane]` | new |
| `surfaces` | `dict[str, IrSurface]` | new |
| `surface_collections` | `dict[str, IrSurfaceCollection]` | new |
| `hole_shape_catalogue` | `IrHoleShapeCatalogue \| None` | new |
| `design_views` | `dict[str, IrDesignView]` | new |
| `connection_configurations` | `dict[str, IrConnectionConfiguration]` | new (placeholder) |
| `ship_designation` | `IrShipDesignation \| None` | replaces `dict` |
| `principal_particulars` | `IrPrincipalParticulars \| None` | replaces `dict` |
| `statutory_data` | `IrStatutoryData \| None` | replaces `dict` |
| `builder_info` | `IrBuilderInformation \| None` | replaces `dict` |
| `classification` | `dict[str, Any] \| None` | unchanged (ClassificationData not in scope) |

---

## Builder impact

`OcxV3Builder` (`builders/v3_builder.py`) will need corresponding extraction methods for each new IR type. The builder design (method signatures, `_SECTION_TYPE_MAP` pattern, `getattr(obj, "field", None)` guards) is unchanged — only new `_build_*` private methods are added. This is covered in the implementation plan.

---

## Testing strategy

- All new IR dataclasses are pure Python — unit tests can construct them directly without OCX stubs.
- New builder methods follow the existing stub-based test pattern (`tests/stubs.py`).
- No test can import from the OCX package directly; use inline stub classes as per existing convention.
- `IrCurve3D` subclass tests must verify that omitting `curve_length` raises `TypeError` at construction.

---

## Backward compatibility

- All existing `from ocx_model_validator.model.ir import X` imports remain valid via `__init__.py` re-exports.
- The four raw `dict | None` metadata fields on `IrVessel` (`ship_designation`, `classification`, `builder_info`, `principal_particulars`) become typed; any existing code that accessed them as `dict` will need updating — but these fields were `None` in practice since the builder never populated them.
- `IrStiffener` gains nullable fields only — no existing constructor call breaks.
