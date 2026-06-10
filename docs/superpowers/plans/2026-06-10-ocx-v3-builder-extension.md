# OCX v3 Builder Extension + IR/OCX Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the IR dataclasses to the real OCX 3.1.0 structure (shallow, schema-neutral) and extend `OcxV3Builder` to populate the new IR collections (geometry, surfaces, coordinate systems, typed metadata, cargoes, seams, end-cuts, design-view, hole catalogue).

**Architecture:** Each domain is one phase: first realign the IR dataclasses + their unit tests, then add `getattr`-guarded `_build_*` methods to `OcxV3Builder` wired into `build()`, with stub-based builder tests mirroring `tests/test_ir_builder.py`. Full `uv run pytest` green and a commit conclude every phase.

**Tech Stack:** Python 3.11+, dataclasses (frozen for value types), xsdata OCX bindings (`ocx.ocx_310.ocx_310`), loguru, pytest, uv.

---

## Conventions used in all tasks

- Run tests with `uv run pytest` (whole suite) or `uv run pytest <path>::<test> -v` (single).
- Builder access is **always** `getattr(obj, "field", None)`; never direct attribute access.
- Reuse existing helpers in `v3_builder.py`: `_qty(elem)`, `_enum(elem)`, `_ref(elem)`, `_cog(elem)`, `_register(...)`.
- New stub classes in builder tests are plain classes with the OCX field names from the spec (snake_case), e.g. `class _Stub: pass; s = _Stub(); s.coordinates = [1,2,3]`.
- Commit message trailer on every commit:
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

---

## Phase 0: Builder helper primitives

### Task 0: Add `_pt` and `_vec` helpers + curve/surface dispatch maps

**Files:**
- Modify: `ocx_model_validator/builders/v3_builder.py`
- Test: `tests/test_builder_geometry.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_builder_geometry.py
from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D


class _Stub:
    pass


def _b():
    return OcxV3Builder()


def test_pt_unpacks_coordinates():
    p = _Stub(); p.coordinates = [1.0, 2.0, 3.0]; p.unit = "Umm"
    ir = _b()._pt(p)
    assert isinstance(ir, IrPoint3D)
    assert (ir.x, ir.y, ir.z, ir.unit) == (1.0, 2.0, 3.0, "Umm")


def test_pt_none_returns_none():
    assert _b()._pt(None) is None


def test_vec_unpacks_direction():
    v = _Stub(); v.direction = [0.0, 0.0, 1.0]
    ir = _b()._vec(v)
    assert isinstance(ir, IrVector3D)
    assert (ir.x, ir.y, ir.z) == (0.0, 0.0, 1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_builder_geometry.py -v`
Expected: FAIL (`OcxV3Builder` has no attribute `_pt`).

- [ ] **Step 3: Implement the helpers**

Add to `OcxV3Builder` (near the other `_*` helpers):

```python
@staticmethod
def _pt(elem):
    if elem is None:
        return None
    coords = getattr(elem, "coordinates", None) or []
    x, y, z = (list(coords) + [0.0, 0.0, 0.0])[:3]
    return IrPoint3D(x=float(x), y=float(y), z=float(z),
                     unit=getattr(elem, "unit", None) or "")

@staticmethod
def _vec(elem):
    if elem is None:
        return None
    d = getattr(elem, "direction", None) or []
    x, y, z = (list(d) + [0.0, 0.0, 0.0])[:3]
    return IrVector3D(x=float(x), y=float(y), z=float(z))
```

Add imports at top of `v3_builder.py`:

```python
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_builder_geometry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/builders/v3_builder.py tests/test_builder_geometry.py
git commit -m "feat(builder): add _pt/_vec geometry primitives"
```

---

## Phase 1: Geometry IR alignment + curve builder

### Task 1a: Realign geometry curve/surface dataclasses

**Files:**
- Modify: `ocx_model_validator/model/ir/geometry.py`
- Modify: `tests/test_ir_geometry.py`

- [ ] **Step 1: Update the failing IR tests first** — change `tests/test_ir_geometry.py` to assert the aligned fields:
  - `IrCircle3D(... diameter=Quantity(...))` instead of `radius=`
  - `IrCircumArc3D(... intermediate=...)` instead of `middle=`
  - `IrSphere3D(origin=...)` instead of `center=`
  - `IrCone3D(origin=..., tip=..., base_radius=..., tip_radius=...)`
  - `IrCylinder3D(... height=...)`
  - `IrPlane3D(... udirection=...)`
  - `IrEllipse3D(... major_diameter=..., minor_diameter=..., normal=...)`
  - `IrPolyLine3D(... is_closed=...)`
  - `IrExtrudedSurface(base_curve=..., sweep=..., sweep_curve=..., face_boundary_curve=...)`
  - `IrCoordinateSystem(is_global=..., local_origin=..., x_ref_plane_ids=[...], ...)`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ir_geometry.py -v`
Expected: FAIL (old field names / TypeError on unexpected kwargs).

- [ ] **Step 3: Apply the dataclass edits** per spec "geometry.py" table:

```python
@dataclass(frozen=True)
class IrCircle3D(IrCurve3D):
    center: IrPoint3D | None = None
    diameter: Quantity | None = None
    normal: IrVector3D | None = None


@dataclass(frozen=True)
class IrCircumArc3D(IrCurve3D):
    start: IrPoint3D | None = None
    intermediate: IrPoint3D | None = None
    end: IrPoint3D | None = None


@dataclass(frozen=True)
class IrEllipse3D(IrCurve3D):
    center: IrPoint3D | None = None
    major_diameter: Quantity | None = None
    minor_diameter: Quantity | None = None
    major_axis: IrVector3D | None = None
    minor_axis: IrVector3D | None = None
    normal: IrVector3D | None = None


@dataclass(frozen=True)
class IrPolyLine3D(IrCurve3D):
    vertices: list[IrPoint3D] = field(default_factory=list)
    is_closed: bool = False


@dataclass(frozen=True)
class IrNurbs3D(IrCurve3D):
    degree: int | None = None
    knot_vector: list[float] = field(default_factory=list)
    control_points: list[IrPoint3D] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    is_rational: bool = False
    form: str | None = None


@dataclass(frozen=True)
class IrPlane3D(IrSurface3D):
    origin: IrPoint3D | None = None
    normal: IrVector3D | None = None
    udirection: IrVector3D | None = None


@dataclass(frozen=True)
class IrSphere3D(IrSurface3D):
    origin: IrPoint3D | None = None
    radius: Quantity | None = None


@dataclass(frozen=True)
class IrCone3D(IrSurface3D):
    origin: IrPoint3D | None = None
    tip: IrPoint3D | None = None
    base_radius: Quantity | None = None
    tip_radius: Quantity | None = None


@dataclass(frozen=True)
class IrCylinder3D(IrSurface3D):
    origin: IrPoint3D | None = None
    axis: IrVector3D | None = None
    radius: Quantity | None = None
    height: Quantity | None = None


@dataclass(frozen=True)
class IrExtrudedSurface(IrSurface3D):
    base_curve: IrCurve3D | None = None
    sweep: IrVector3D | None = None
    sweep_curve: IrCurve3D | None = None
    face_boundary_curve: IrCurve3D | None = None


@dataclass(frozen=True)
class IrNurbsSurface(IrSurface3D):
    u_degree: int | None = None
    v_degree: int | None = None
    u_knot_vector: list[float] = field(default_factory=list)
    v_knot_vector: list[float] = field(default_factory=list)
    control_points: list[list[IrPoint3D]] = field(default_factory=list)


@dataclass(frozen=True)
class IrCoordinateSystem:
    id: str
    name: str | None = None
    is_global: bool = False
    local_origin: IrPoint3D | None = None
    x_ref_plane_ids: list[str] = field(default_factory=list)
    y_ref_plane_ids: list[str] = field(default_factory=list)
    z_ref_plane_ids: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ir_geometry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/model/ir/geometry.py tests/test_ir_geometry.py
git commit -m "refactor(ir): align geometry dataclasses to OCX 3.1.0 fields"
```

### Task 1b: `_build_curve` dispatch in the builder

**Files:**
- Modify: `ocx_model_validator/builders/v3_builder.py`
- Modify: `tests/test_builder_geometry.py`

- [ ] **Step 1: Write failing tests** for each curve kind:

```python
from ocx_model_validator.model.ir.geometry import (
    IrLine3D, IrCircle3D, IrCircumArc3D, IrPolyLine3D, IrEllipse3D,
    IrCompositeCurve3D,
)


def _pt_stub(x, y, z, unit="Umm"):
    s = _Stub(); s.coordinates = [x, y, z]; s.unit = unit
    return s


def test_build_line():
    ln = _Stub()
    ln.__class__.__name__ = "Line3D"  # see note
    ...
```

> **Note on dispatch:** stubs must report a class name. Create real named stub
> classes instead of mutating `__name__`:
>
> ```python
> class Line3D: pass
> class Circle3D: pass
> class CircumArc3D: pass
> class PolyLine3D: pass
> class Ellipse3D: pass
> class CompositeCurve3D: pass
> ```
>
> Then set the OCX field attributes the builder reads.

Concrete tests:

```python
def test_build_line():
    ln = Line3D()
    ln.start_point = _pt_stub(0, 0, 0)
    ln.end_point = _pt_stub(1, 0, 0)
    ln.curve_length = None
    ir = _b()._build_curve(ln)
    assert isinstance(ir, IrLine3D)
    assert ir.start.x == 0.0 and ir.end.x == 1.0


def test_build_circle_diameter():
    c = Circle3D()
    c.center = _pt_stub(0, 0, 0)
    c.diameter = _qstub(2.0, "Umm")
    c.normal = None
    c.curve_length = None
    ir = _b()._build_curve(c)
    assert isinstance(ir, IrCircle3D)
    assert ir.diameter.value == 2.0


def test_build_polyline_collects_points_and_closed():
    pl = PolyLine3D()
    pl.point3_d = [_pt_stub(0, 0, 0), _pt_stub(1, 1, 1)]
    pl.is_closed = True
    pl.curve_length = None
    ir = _b()._build_curve(pl)
    assert isinstance(ir, IrPolyLine3D)
    assert len(ir.vertices) == 2 and ir.is_closed is True


def test_build_composite_collects_all_typed_lists():
    cc = CompositeCurve3D()
    ln = Line3D(); ln.start_point = _pt_stub(0,0,0); ln.end_point = _pt_stub(1,0,0); ln.curve_length = None
    cc.line3_d = [ln]
    cc.poly_line3_d = []
    cc.nurbs3_d = []
    cc.circum_arc3_d = []
    cc.circle3_d = []
    cc.ellipse3_d = []
    cc.curve_length = None
    ir = _b()._build_curve(cc)
    assert isinstance(ir, IrCompositeCurve3D)
    assert len(ir.segments) == 1 and isinstance(ir.segments[0], IrLine3D)


def test_build_curve_unknown_returns_none():
    class Weird: pass
    assert _b()._build_curve(Weird()) is None
```

Add a `_qstub` helper to the test module:

```python
def _qstub(value, unit):
    q = _Stub(); q.numericvalue = value; q.unit = unit
    return q
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_builder_geometry.py -v`
Expected: FAIL (`_build_curve` missing).

- [ ] **Step 3: Implement `_build_curve`** in `v3_builder.py`:

```python
def _build_curve(self, elem):
    if elem is None:
        return None
    name = type(elem).__name__.lower()
    cl = self._qty(getattr(elem, "curve_length", None))
    cid = getattr(elem, "id", None)
    if "compositecurve" in name:
        segs = []
        for attr in ("line3_d", "poly_line3_d", "circum_arc3_d",
                     "circle3_d", "ellipse3_d", "nurbs3_d"):
            for seg in getattr(elem, attr, None) or []:
                built = self._build_curve(seg)
                if built is not None:
                    segs.append(built)
        return IrCompositeCurve3D(curve_length=cl, id=cid, segments=segs)
    if "polyline" in name:
        verts = [self._pt(p) for p in getattr(elem, "point3_d", None) or []]
        return IrPolyLine3D(curve_length=cl, id=cid, vertices=[v for v in verts if v],
                            is_closed=bool(getattr(elem, "is_closed", False)))
    if "circumarc" in name:
        return IrCircumArc3D(curve_length=cl, id=cid,
                             start=self._pt(getattr(elem, "start_point", None)),
                             intermediate=self._pt(getattr(elem, "intermediate_point", None)),
                             end=self._pt(getattr(elem, "end_point", None)))
    if "circle" in name:
        return IrCircle3D(curve_length=cl, id=cid,
                          center=self._pt(getattr(elem, "center", None)),
                          diameter=self._qty(getattr(elem, "diameter", None)),
                          normal=self._vec(getattr(elem, "normal", None)))
    if "ellipse" in name:
        return IrEllipse3D(curve_length=cl, id=cid,
                           center=self._pt(getattr(elem, "center", None)),
                           major_diameter=self._qty(getattr(elem, "major_diameter", None)),
                           minor_diameter=self._qty(getattr(elem, "minor_diameter", None)),
                           major_axis=self._vec(getattr(elem, "major_axis", None)),
                           minor_axis=self._vec(getattr(elem, "minor_axis", None)),
                           normal=self._vec(getattr(elem, "normal", None)))
    if "nurbs" in name:
        props = getattr(elem, "nurbsproperties", None)
        kv = getattr(elem, "knot_vector", None)
        cpl = getattr(elem, "control_pt_list", None)
        pts = []
        if cpl is not None:
            pts = [self._pt(p) for p in getattr(cpl, "control_point", None) or []]
        return IrNurbs3D(curve_length=cl, id=cid,
                         degree=getattr(props, "degree", None) if props else None,
                         knot_vector=list(getattr(kv, "value", None) or []) if kv else [],
                         control_points=[p for p in pts if p],
                         is_rational=bool(getattr(props, "is_rational", False)) if props else False,
                         form=getattr(getattr(props, "form", None), "value", None) if props else None)
    if "line3d" in name or name == "line3d":
        return IrLine3D(curve_length=cl, id=cid,
                        start=self._pt(getattr(elem, "start_point", None)),
                        end=self._pt(getattr(elem, "end_point", None)))
    logger.debug("Unknown curve type: {}", type(elem).__name__)
    return None
```

Add imports:

```python
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D, IrCircumArc3D, IrCompositeCurve3D, IrEllipse3D,
    IrLine3D, IrNurbs3D, IrPolyLine3D,
)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_builder_geometry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/builders/v3_builder.py tests/test_builder_geometry.py
git commit -m "feat(builder): add _build_curve dispatch for all 3D curve types"
```

---

## Phase 2: Surfaces, reference surfaces, coordinate system

### Task 2a: `_build_surface` dispatch

**Files:** Modify `v3_builder.py`; Test `tests/test_builder_surfaces_coords.py` (create).

- [ ] **Step 1: Failing tests** — named stubs `Plane3D`, `Sphere3D`, `Cone3D`, `Cylinder3D`, `Nurbssurface`, `ExtrudedSurface` with their OCX fields; assert the IR surface types and key fields (`Sphere3D.origin`, `Cone3D.base_radius/tip_radius`, `Cylinder3D.height`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `_build_surface`:**

```python
def _build_surface(self, elem):
    if elem is None:
        return None
    name = type(elem).__name__.lower()
    sid = getattr(elem, "id", None)
    if "plane" in name:
        return IrPlane3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                         normal=self._vec(getattr(elem, "normal", None)),
                         udirection=self._vec(getattr(elem, "udirection", None)))
    if "sphere" in name:
        return IrSphere3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                          radius=self._qty(getattr(elem, "radius", None)))
    if "cone" in name:
        return IrCone3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                        tip=self._pt(getattr(elem, "tip", None)),
                        base_radius=self._qty(getattr(elem, "base_radius", None)),
                        tip_radius=self._qty(getattr(elem, "tip_radius", None)))
    if "cylinder" in name:
        return IrCylinder3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                            axis=self._vec(getattr(elem, "axis", None)),
                            radius=self._qty(getattr(elem, "radius", None)),
                            height=self._qty(getattr(elem, "height", None)))
    if "extruded" in name:
        return IrExtrudedSurface(id=sid,
                                 base_curve=self._build_curve(getattr(elem, "base_curve", None)),
                                 sweep=self._vec(getattr(elem, "sweep", None)),
                                 sweep_curve=self._build_curve(getattr(elem, "sweep_curve", None)),
                                 face_boundary_curve=self._build_curve(getattr(elem, "face_boundary_curve", None)))
    if "nurbssurface" in name or "nurbs" in name:
        return IrNurbsSurface(id=sid)  # control net left empty (shallow subset)
    logger.debug("Unknown surface type: {}", type(elem).__name__)
    return None
```

Add imports for the surface IR types.

- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `feat(builder): add _build_surface dispatch`.

### Task 2b: `_build_reference_surfaces` + `_build_coordinate_system`

**Files:** Modify `v3_builder.py`; extend `tests/test_builder_surfaces_coords.py`.

- [ ] **Step 1: Failing tests:**
  - A `ReferenceSurfaces` stub with `plane3_d=[...]`, `sphere3_d=[...]`, `surface_collection=[...]` → assert `vessel.surfaces` populated and each `IrSurface.geometry` is the right type; `vessel.surface_collections` populated.
  - A `CoordinateSystem` stub with `is_global=True`, `local_cartesian` (origin point), `xref_planes`/`yref_planes`/`zref_planes` each wrapping `ref_plane=[stub(id=...)]` → assert `vessel.coordinate_systems[id]` has `is_global`, `local_origin`, and `x_ref_plane_ids == ["RP1"]`; assert `vessel.ref_planes` populated.

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** (operate on a passed `vessel`):

```python
def _build_reference_surfaces(self, rs, vessel):
    if rs is None:
        return
    surf_attrs = ("plane3_d", "nurbssurface", "extruded_surface",
                  "sphere3_d", "cone3_d", "cylinder3_d")
    for attr in surf_attrs:
        for elem in getattr(rs, attr, None) or []:
            geom = self._build_surface(elem)
            sid = getattr(elem, "id", None) or getattr(elem, "guidref", None)
            if sid is None:
                continue
            self._register(vessel.surfaces, sid,
                           IrSurface(id=sid, name=getattr(elem, "name", None),
                                     guidref=getattr(elem, "guidref", None), geometry=geom),
                           vessel)
    for coll in getattr(rs, "surface_collection", None) or []:
        cid = getattr(coll, "id", None)
        if cid is None:
            continue
        members = []
        for attr in surf_attrs:
            for elem in getattr(coll, attr, None) or []:
                geom = self._build_surface(elem)
                sid = getattr(elem, "id", None)
                members.append(IrSurface(id=sid, geometry=geom))
        self._register(vessel.surface_collections, cid,
                       IrSurfaceCollection(id=cid, name=getattr(coll, "name", None),
                                           surfaces=members), vessel)


def _build_coordinate_system(self, cs, vessel):
    if cs is None:
        return
    cid = getattr(cs, "id", None) or "CoordinateSystem"

    def _plane_ids(group):
        ids = []
        for rp in getattr(group, "ref_plane", None) or []:
            rid = getattr(rp, "id", None)
            if rid:
                ids.append(rid)
                self._register(vessel.ref_planes, rid,
                               IrRefPlane(id=rid, name=getattr(rp, "name", None)), vessel)
        return ids

    local = getattr(cs, "local_cartesian", None)
    origin = self._pt(getattr(local, "origin", None)) if local else None
    self._register(vessel.coordinate_systems, cid, IrCoordinateSystem(
        id=cid, name=getattr(cs, "name", None),
        is_global=bool(getattr(cs, "is_global", False)),
        local_origin=origin,
        x_ref_plane_ids=_plane_ids(getattr(cs, "xref_planes", None)) if getattr(cs, "xref_planes", None) else [],
        y_ref_plane_ids=_plane_ids(getattr(cs, "yref_planes", None)) if getattr(cs, "yref_planes", None) else [],
        z_ref_plane_ids=_plane_ids(getattr(cs, "zref_planes", None)) if getattr(cs, "zref_planes", None) else [],
    ), vessel)
```

- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `feat(builder): build reference surfaces and coordinate system`.

---

## Phase 3: Typed metadata alignment

### Task 3a: Realign `metadata.py` + IR tests

**Files:** Modify `ocx_model_validator/model/ir/metadata.py`; Modify `tests/test_ir_metadata.py`.

- [ ] **Step 1:** Update `tests/test_ir_metadata.py` to the aligned fields (spec "metadata.py" table).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Apply dataclass edits:

```python
@dataclass(frozen=True)
class IrShipDesignation:
    ship_name: str | None = None
    call_sign: str | None = None
    number_imo: str | None = None
    ship_type: str | None = None


@dataclass(frozen=True)
class IrTonnageData:
    tonnage: Quantity | None = None
    dead_weight: Quantity | None = None


@dataclass(frozen=True)
class IrStatutoryData:
    port_registration: str | None = None
    flag_state: str | None = None


@dataclass(frozen=True)
class IrBuilderInformation:
    yard: str | None = None
    designer: str | None = None
    owner: str | None = None
    year_of_build: str | None = None


@dataclass(frozen=True)
class IrPrincipalParticulars:
    lpp: Quantity | None = None
    rule_length: Quantity | None = None
    block_coefficient: Quantity | None = None
    moulded_breadth: Quantity | None = None
    moulded_depth: Quantity | None = None
    scantling_draught: Quantity | None = None
    design_speed: Quantity | None = None
    freeboard_length: Quantity | None = None
    normal_ballast_draught: Quantity | None = None
    heavy_ballast_draught: Quantity | None = None
    length_of_waterline: Quantity | None = None
    upper_deck_area: Quantity | None = None
    freeboard_type: str | None = None
```

Remove the now-invalid `tonnage_data` field reference from `IrStatutoryData` (tonnage lives on the vessel directly).

- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `refactor(ir): align metadata dataclasses to OCX 3.1.0`.

### Task 3b: Replace dict metadata builder with typed `_build_metadata`

**Files:** Modify `v3_builder.py` (the ~736-786 dict block); Test `tests/test_builder_metadata.py` (create).

- [ ] **Step 1: Failing tests** — stubs for `ShipDesignation`, `TonnageData`, `StatutoryData`, `BuilderInformation`, `ClassificationData.principal_particulars`; assert typed IR objects on the vessel:
  - `vessel.ship_designation.ship_name == "MV Test"`
  - `vessel.tonnage_data.tonnage.value == 12000.0` *(field name on vessel: keep existing `tonnage_data`? IrVessel has no tonnage field — add one)*

> **IR addition:** add `tonnage_data: IrTonnageData | None = None` to `IrVessel` (it currently
> only has `statutory_data`). Update `MISSING_IR_CLASSES` if needed (Tonnage stays missing).

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `_build_metadata(self, root, vessel)` reading from the vessel element:

```python
def _build_metadata(self, vessel_elem, vessel):
    sd = getattr(vessel_elem, "ship_designation", None)
    if sd is not None:
        vessel.ship_designation = IrShipDesignation(
            ship_name=getattr(sd, "ship_name", None),
            call_sign=getattr(sd, "call_sign", None),
            number_imo=getattr(sd, "number_imo", None),
            ship_type=getattr(sd, "ship_type", None))
    td = getattr(vessel_elem, "tonnage_data", None)
    if td is not None:
        vessel.tonnage_data = IrTonnageData(
            tonnage=self._qty(getattr(td, "tonnage", None)),
            dead_weight=self._qty(getattr(td, "dead_weight", None)))
    st = getattr(vessel_elem, "statutory_data", None)
    if st is not None:
        vessel.statutory_data = IrStatutoryData(
            port_registration=getattr(st, "port_registration", None),
            flag_state=getattr(st, "flag_state", None))
    bi = getattr(vessel_elem, "builder_information", None)
    if bi is not None:
        yob = getattr(bi, "year_of_build", None)
        vessel.builder_info = IrBuilderInformation(
            yard=getattr(bi, "yard", None), designer=getattr(bi, "designer", None),
            owner=getattr(bi, "owner", None),
            year_of_build=str(yob) if yob is not None else None)
    cd = getattr(vessel_elem, "classification_data", None)
    pp = getattr(cd, "principal_particulars", None) if cd else None
    if pp is not None:
        vessel.principal_particulars = IrPrincipalParticulars(
            lpp=self._qty(getattr(pp, "lpp", None)),
            rule_length=self._qty(getattr(pp, "rule_length", None)),
            block_coefficient=self._qty(getattr(pp, "block_coefficient", None)),
            moulded_breadth=self._qty(getattr(pp, "moulded_breadth", None)),
            moulded_depth=self._qty(getattr(pp, "moulded_depth", None)),
            scantling_draught=self._qty(getattr(pp, "scantling_draught", None)),
            design_speed=self._qty(getattr(pp, "design_speed", None)),
            freeboard_length=self._qty(getattr(pp, "freeboard_length", None)),
            normal_ballast_draught=self._qty(getattr(pp, "normal_ballast_draught", None)),
            heavy_ballast_draught=self._qty(getattr(pp, "heavy_ballast_draught", None)),
            length_of_waterline=self._qty(getattr(pp, "length_of_waterline", None)),
            upper_deck_area=self._qty(getattr(pp, "upper_deck_area", None)),
            freeboard_type=getattr(getattr(pp, "freeboard_type", None), "value", None))
```

Delete the old dict-returning metadata block and call `self._build_metadata(vessel_elem, vessel)` from `build()`.

- [ ] **Step 4:** Run full suite → PASS. **Step 5:** Commit `feat(builder): typed metadata extraction`.

---

## Phase 4: Cargoes

### Task 4a: Realign `arrangement.py` cargo dataclasses + IR tests

**Files:** Modify `arrangement.py`; Modify `tests/test_ir_arrangement_additions.py`.

- [ ] Steps 1-2: update tests to aligned fields (spec table), run → FAIL.
- [ ] Step 3: apply edits:

```python
@dataclass
class IrLiquidCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    carriage_pressure: Quantity | None = None


@dataclass
class IrGaseousCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    carriage_pressure: Quantity | None = None
    liquid_state: bool = False


@dataclass
class IrBulkCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    stowage_factor: Quantity | None = None
    permeability: Quantity | None = None
    angle_of_repose: Quantity | None = None


@dataclass
class IrUnitCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
```

Also realign `IrOccurrence`, `IrOccurrenceGroup`, `IrDesignView` per spec (used in Phase 6 — do it here so the file changes land together):

```python
@dataclass
class IrOccurrence:
    id: str
    name: str | None = None
    type_value: str | None = None
    plate_ref: Ref | None = None
    stiffener_ref: Ref | None = None
    seam_ref: Ref | None = None
    bracket_ref: Ref | None = None
    pillar_ref: Ref | None = None
    hole_contour_ref: Ref | None = None
    edge_reinforcement_ref: Ref | None = None
    lug_plate_ref: Ref | None = None
    connected_bracket_ref: Ref | None = None


@dataclass
class IrOccurrenceGroup:
    id: str
    name: str | None = None
    type_value: str | None = None
    children: list = field(default_factory=list)


@dataclass
class IrDesignView:
    id: str
    name: str | None = None
    guidref: str | None = None
    vessel_ref: Ref | None = None
    children: list = field(default_factory=list)
```

- [ ] Step 4: run → PASS. Step 5: commit `refactor(ir): align arrangement dataclasses to OCX 3.1.0`.

### Task 4b: `_build_cargoes_for_compartment`

**Files:** Modify `v3_builder.py`; Test `tests/test_builder_cargoes.py` (create).

- [ ] Step 1: failing tests — `Compartment` stub with `liquid_cargo=[stub]`, `bulk_cargo=[stub]`, `unit_cargo=[stub]`; assert each lands in `vessel.liquid_cargoes` etc. with `compartment_ref.local_ref == compartment.id` and synthesized id (`{comp_id}/liquid/{i}`).
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement:

```python
def _build_cargoes_for_compartment(self, comp, vessel):
    cid = getattr(comp, "id", None)
    ref = Ref(local_ref=cid or "", guidref=getattr(comp, "guidref", None))
    for i, lc in enumerate(getattr(comp, "liquid_cargo", None) or []):
        cargo_id = f"{cid}/liquid/{i}"
        self._register(vessel.liquid_cargoes, cargo_id, IrLiquidCargo(
            id=cargo_id, compartment_ref=ref,
            cargo_type=getattr(getattr(lc, "liquid_cargo_type", None), "value", None),
            density=self._qty(getattr(lc, "density", None)),
            carriage_pressure=self._qty(getattr(lc, "carriage_pressure", None))), vessel)
    for i, bc in enumerate(getattr(comp, "bulk_cargo", None) or []):
        cargo_id = f"{cid}/bulk/{i}"
        self._register(vessel.bulk_cargoes, cargo_id, IrBulkCargo(
            id=cargo_id, compartment_ref=ref,
            cargo_type=getattr(getattr(bc, "bulk_cargo_type", None), "value", None),
            stowage_factor=self._qty(getattr(bc, "stowage_factor", None)),
            permeability=self._qty(getattr(bc, "permeability", None)),
            angle_of_repose=self._qty(getattr(bc, "angle_of_repose", None))), vessel)
    for i, uc in enumerate(getattr(comp, "unit_cargo", None) or []):
        cargo_id = f"{cid}/unit/{i}"
        self._register(vessel.unit_cargoes, cargo_id, IrUnitCargo(
            id=cargo_id, compartment_ref=ref,
            cargo_type=getattr(getattr(uc, "unit_cargo_type", None), "value", None)), vessel)
```

Call it from the compartment-building loop in `build()`.

- [ ] Step 4: run → PASS. Step 5: commit `feat(builder): extract compartment cargoes`.

---

## Phase 5: Seams + stiffener end-cuts

### Task 5a: Realign `IrSeam`, `IrEndCut`, stiffener end-cut fields + IR tests

**Files:** Modify `structural.py`; Modify `tests/test_ir_structural_additions.py`.

- [ ] Steps 1-2: update tests, run → FAIL.
- [ ] Step 3:

```python
@dataclass
class IrSeam:
    id: str
    name: str | None = None
    guidref: str | None = None
    trace_line: "IrCurve3D | None" = None


@dataclass(frozen=True)
class IrEndCut:
    id: str | None = None
    name: str | None = None
    cutback_distance: Quantity | None = None
    web_cut_back_angle: Quantity | None = None
    web_nose_height: Quantity | None = None
    flange_cut_back_angle: Quantity | None = None
    flange_nose_height: Quantity | None = None
    symmetric_flange: bool = False
    sniped: bool = False
    feature_cope: IrFeatureCope | None = None
```

In `IrStiffener` rename `end_cut_start`/`end_cut_end` → `end_cut_end1`/`end_cut_end2`.
`IrMember` realign to `{id, parent_ref, name, guidref, dry_weight, cog: IrCog, external_geometry_ref: Ref}`.
Add `from ocx_model_validator.model.ir.geometry import IrCurve3D` import to `structural.py`.

- [ ] Step 4: run → PASS. Step 5: commit `refactor(ir): align seam/endcut/member to OCX 3.1.0`.

### Task 5b: `_build_seams_for_panel` + `_build_end_cut`, extend stiffener

**Files:** Modify `v3_builder.py`; Test `tests/test_builder_seams_endcuts.py` (create).

- [ ] Step 1: failing tests:
  - `Panel` stub with `split_by.seam=[seam_stub(id, trace_line=TraceLine(composite_curve3_d=...))]` → `vessel.seams[id].trace_line` is an `IrCompositeCurve3D`; `panel.seam_ids == [id]`.
  - `EndCutEnd1` stub → `_build_end_cut` returns `IrEndCut` with `sniped`, `cutback_distance`.
- [ ] Step 2: run → FAIL.
- [ ] Step 3:

```python
def _build_end_cut(self, ec):
    if ec is None:
        return None
    fc = getattr(ec, "feature_cope", None)
    cope = None
    if fc is not None:
        cope = IrFeatureCope(id=getattr(fc, "id", None) or "",
                             name=getattr(fc, "name", None))
    return IrEndCut(
        id=getattr(ec, "id", None), name=getattr(ec, "name", None),
        cutback_distance=self._qty(getattr(ec, "cutback_distance", None)),
        web_cut_back_angle=self._qty(getattr(ec, "web_cut_back_angle", None)),
        web_nose_height=self._qty(getattr(ec, "web_nose_height", None)),
        flange_cut_back_angle=self._qty(getattr(ec, "flange_cut_back_angle", None)),
        flange_nose_height=self._qty(getattr(ec, "flange_nose_height", None)),
        symmetric_flange=bool(getattr(ec, "symmetric_flange", False)),
        sniped=bool(getattr(ec, "sniped", False)),
        feature_cope=cope)


def _build_seams_for_panel(self, panel_elem, ir_panel, vessel):
    split = getattr(panel_elem, "split_by", None)
    if split is None:
        return
    for seam in getattr(split, "seam", None) or []:
        sid = getattr(seam, "id", None)
        if sid is None:
            continue
        tl = getattr(seam, "trace_line", None)
        curve = self._build_curve(getattr(tl, "composite_curve3_d", None)) if tl else None
        self._register(vessel.seams, sid, IrSeam(
            id=sid, name=getattr(seam, "name", None),
            guidref=getattr(seam, "guidref", None), trace_line=curve), vessel)
        ir_panel.seam_ids.append(sid)
```

In `_build_stiffener`, set
`end_cut_end1=self._build_end_cut(getattr(st, "end_cut_end1", None))` and `end_cut_end2` likewise.

- [ ] Step 4: run → PASS. Step 5: commit `feat(builder): extract seams and stiffener end-cuts`.

---

## Phase 6: Design-view / occurrence tree

### Task 6: `_build_design_view`

**Files:** Modify `v3_builder.py`; Test `tests/test_builder_design_view.py` (create).
(IR types already realigned in Task 4a.)

- [ ] Step 1: failing tests — `DesignView` stub with nested `occurrence_group=[grp]` where `grp.occurrence=[occ]`, `occ.plate_ref=ref_stub`; assert `vessel.design_views[id]` exists, its `children[0]` is an `IrOccurrenceGroup`, whose `children[0]` is an `IrOccurrence` with `plate_ref.local_ref` set.
- [ ] Step 2: run → FAIL.
- [ ] Step 3:

```python
_OCC_REF_ATTRS = ("plate_ref", "stiffener_ref", "seam_ref", "bracket_ref",
                  "pillar_ref", "hole_contour_ref", "edge_reinforcement_ref",
                  "lug_plate_ref", "connected_bracket_ref")

def _build_occurrence(self, occ):
    kwargs = {"id": getattr(occ, "id", None) or "",
              "name": getattr(occ, "name", None),
              "type_value": getattr(occ, "type_value", None)}
    for attr in self._OCC_REF_ATTRS:
        kwargs[attr] = self._ref(getattr(occ, attr, None))
    return IrOccurrence(**kwargs)

def _build_occurrence_group(self, grp):
    children = []
    for sub in getattr(grp, "occurrence_group", None) or []:
        children.append(self._build_occurrence_group(sub))
    for occ in getattr(grp, "occurrence", None) or []:
        children.append(self._build_occurrence(occ))
    return IrOccurrenceGroup(id=getattr(grp, "id", None) or "",
                             name=getattr(grp, "name", None),
                             type_value=getattr(grp, "type_value", None),
                             children=children)

def _build_design_view(self, dv, vessel):
    if dv is None:
        return
    children = []
    for grp in getattr(dv, "occurrence_group", None) or []:
        children.append(self._build_occurrence_group(grp))
    for occ in getattr(dv, "occurrence", None) or []:
        children.append(self._build_occurrence(occ))
    did = getattr(dv, "id", None) or "DesignView"
    self._register(vessel.design_views, did, IrDesignView(
        id=did, name=getattr(dv, "name", None),
        vessel_ref=self._ref(getattr(dv, "vessel_ref", None)),
        children=children), vessel)
```

> `_ref` must tolerate `None` → `None`. Confirm existing `_ref` does; if not, guard.

- [ ] Step 4: run → PASS. Step 5: commit `feat(builder): extract design-view occurrence tree`.

---

## Phase 7: Hole-shape catalogue

### Task 7: `_build_hole_catalogue` + `IrHole2D` parametric field

**Files:** Modify `catalogues.py`, `v3_builder.py`; Modify `tests/test_ir_catalogues.py`; Test `tests/test_builder_holes.py` (create).

- [ ] Step 1a: add `parametric: dict | None = None` to `IrHole2D`; update `tests/test_ir_catalogues.py`. Run → FAIL → implement → PASS.
- [ ] Step 1b: failing builder test — `HoleShapeCatalogue` stub with `hole2_d=[hole_stub(id, contour=Contour(circle3_d=[...]))]`; assert `vessel.hole_shape_catalogue.holes[id].contour` is an `IrCircle3D`.
- [ ] Step 2: run → FAIL.
- [ ] Step 3:

```python
def _build_hole_catalogue(self, cat, vessel):
    if cat is None:
        return
    holes = {}
    for h in getattr(cat, "hole2_d", None) or []:
        hid = getattr(h, "id", None)
        if hid is None:
            continue
        contour = getattr(h, "contour", None)
        curve = None
        if contour is not None:
            for attr in ("composite_curve3_d", "poly_line3_d", "circle3_d",
                         "ellipse3_d", "circum_arc3_d", "line3_d", "nurbs3_d"):
                val = getattr(contour, attr, None)
                target = val[0] if isinstance(val, list) and val else val
                if target is not None:
                    curve = self._build_curve(target)
                    break
        parametric = None
        for attr in ("rectangular_hole", "super_elliptical",
                     "symmetrical_hole", "parametric_circle"):
            if getattr(h, attr, None) is not None:
                parametric = {"variant": attr}
                break
        holes[hid] = IrHole2D(id=hid, name=getattr(h, "name", None),
                              guidref=getattr(h, "guidref", None),
                              contour=curve, parametric=parametric)
    vessel.hole_shape_catalogue = IrHoleShapeCatalogue(
        id=getattr(cat, "id", None) or "HoleShapeCatalogue",
        name=getattr(cat, "name", None), holes=holes)
```

Locate the `HoleShapeCatalogue` source (root or vessel) and call from `build()`.

- [ ] Step 4: run → PASS. Step 5: commit `feat(builder): extract hole-shape catalogue`.

---

## Phase 8: Wire-up, regression, docs

### Task 8: Integrate all calls into `build()` and final regression

**Files:** Modify `v3_builder.py`; Modify `tests/test_ir_builder.py` (MISSING_IR_CLASSES if needed).

- [ ] Step 1: ensure `build()` calls, in order after the structural pass:
  `_build_coordinate_system`, `_build_reference_surfaces`, `_build_metadata`,
  `_build_design_view`, `_build_hole_catalogue`; per-panel `_build_seams_for_panel`;
  per-compartment `_build_cargoes_for_compartment`.
- [ ] Step 2: run the **whole** suite: `uv run pytest`
  Expected: all green (target ≥ prior 175 plus the new builder tests).
- [ ] Step 3: if any real-stub integration test exists (`tests/data/ocx_310_stubs`), run it and confirm the new collections populate without error.
- [ ] Step 4: update `.github/copilot-instructions.md` builder section only if a new public pattern was added (e.g. `_pt`/`_vec`/dispatch maps) — one or two lines.
- [ ] Step 5: Commit `feat(builder): wire new extractors into build() and finalize`.

---

## Self-Review

**Spec coverage:** geometry curves (T1), surfaces+coords (T2), metadata (T3), cargoes (T4),
seams+end-cuts (T5), design-view (T6), holes (T7), wire-up (T8). `IrMember` intentionally
not populated (spec "Out of scope"). Connection-config placeholders unchanged (spec).

**Placeholders:** none — every code step shows full code.

**Type consistency:** `_pt`/`_vec`/`_build_curve`/`_build_surface`/`_qty`/`_ref`/`_register`
used consistently; IR field names match the spec tables and the `IrVessel` collection names
(`surfaces`, `surface_collections`, `coordinate_systems`, `ref_planes`, `seams`,
`liquid/bulk/unit_cargoes`, `design_views`, `hole_shape_catalogue`). Added
`IrVessel.tonnage_data` in Task 3b. `IrHole2D.parametric` added in Task 7.
