# OCX Cross-Section Extraction + MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract frame table, cross-sections (plates + longitudinal stiffeners) and compartments from OCX 3D ship models into a lean JSON document, expose it via a new `ocx-mcp` MCP server, and verify the full pipeline by feeding nh-mcp for real Nauticus Hull rule checks.

**Architecture:** Extend the IR (`IrPlate.outer_contour`, `IrStiffener.trace`, `IrPanel.unbounded_geometry`, `IrRefPlane.location`, `IrCompartment.cog`) and `OcxV3Builder` to populate them. A new pure-function `ocx_model_validator/sections/` package does plane∩curve intersection math (pure Python + numpy, de Boor NURBS evaluation, bisection to 0.1 mm), frame-table derivation, section assembly and JSON document build. A thin FastMCP server (`ocx_model_validator/mcp/`) exposes 6 tools. A demo script + integration test in the sibling nh-mcp repo run the extracted data through real NH rule calculations.

**Tech Stack:** Python ≥3.12, uv, hatchling, dataclasses IR, xsdata OCX bindings (`ocx` package), numpy, `mcp>=1.0,<2` (FastMCP 1.x), pytest, loguru.

**Spec:** `docs/superpowers/specs/2026-09-13-ocx-cross-section-mcp-design.md`

**Repos:**
- Primary: `C:\PythonDev\ocx-model-validator` (all tasks except Task 10)
- Secondary: `C:\PythonDev\nh-mcp` (Task 10 only)
- Reference model: `C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx` (plain XML, schemaVersion 3.0.0, ~21 MB — NOT a zip)

**Commands:** always run from the repo root with `uv run`. Every commit message ends with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

**Verified codebase facts (do not re-derive):**
- Parse + build: `OcxParser().parse(path)` (from `ocx_model_validator.parsers.parser`) returns the raw root; `get_builder(getattr(root, "schema_version", "unknown")).build(root)` (from `ocx_model_validator.builders.factory`) returns `IrVessel`.
- xsdata raw fields (ocx 3.0.0 bindings): `Stiffener.trace_line` (TraceLine has only `composite_curve3_d`), `Plate.outer_contour` (OuterContour has `circum_arc3_d, nurbs3_d, composite_curve3_d, line3_d, poly_line3_d, circum_circle3_d, ellipse3_d, circle3_d`), `Panel.unbounded_geometry` (UnboundedGeometry has `plane3_d, nurbssurface, extruded_surface, sphere3_d, cone3_d, cylinder3_d, grid_ref, surface_ref`), `RefPlane.reference_location` (QuantityT: `numericvalue`, `unit`), `CompartmentProperties.center_of_gravity` (Point3D-like: `coordinates`, `unit`), `ControlPoint.weight`.
- `OcxV3Builder` helpers already exist: `_qty`, `_ref`, `_pt`, `_vec`, `_cog`, `_enum`, `_build_curve` (handles Line3D/PolyLine3D/CircumArc3D/Circle3D/Ellipse3D/Nurbs3D/CompositeCurve3D), `_build_surface`, `_register`.
- `IrNurbs3D` already has a `weights: list[float]` field — the builder just never populates it.
- `IrVessel.unit_registry: dict[str, IrUnit]` where `IrUnit.to_si_factor` converts raw value → SI (`si_value = raw * factor`). OCX unit ids look like `'Um'`, `'Umm'`.
- `IrCog(x, y, z, unit)`; `Quantity(value, unit)`; `Ref(local_ref, guidref)`; `ParentRef(kind, id)` with `ParentKind.PANEL/VESSEL`.
- `IrSection` subclasses (in `model/ir/sections.py`): `IrBulbFlatSection(height, web_thickness, flange_width, …)`, `IrFlatBarSection(height, width)`, `IrTSection(height, width, web_thickness, flange_thickness)`, `IrLSection(…)`, `IrLSectionOvershootWeb/Flange(…)`, all with `section_type: str`.
- `IrMaterial.yield_stress: Quantity | None` exists.
- nh-mcp contracts: `setup_frame_table(frame0_offset: float, entries: list[FrameEntry])` with `FrameEntry(frame_no: str, spacing: float)` — "from frame_no onwards the given spacing applies"; `create_compartment(name, tank_type, cog_x/y/z, min_y, max_y, min_z, max_z, volume, start_frame/end_frame OR min_x/max_x, …)` (mm, volume m³); `calculate_shell_plate(name, frame: str, y, z, position, slope, spacing, unsupported_length, tgr, compartment)`; `calculate_stiffener(mode, name, y, z, position1, reh, slope, spacing, unsupported_length, tgr, compartment_left, compartment_right, profile_type, profile_dimensions, profile_reh, profile_y, profile_z, profile_orientation, profile_web_angle, profile_spacing, lbdg, lshr, x=None, frame=None, position2=0)`. Profile strings: `profile_type` e.g. `"HpBulb"`, `"FlatBar"`; `profile_dimensions` space-separated e.g. `"300 x 11"`; `profile_orientation` ∈ {"Longitudinal", "Transverse"}.
- FastMCP 1.x: `@mcp.tool()` returns the original function → unit tests call tools as plain functions.
- ocx-model-validator tests live flat in `tests/`, use duck-typed stubs (`types.SimpleNamespace` works because the builder uses `getattr` everywhere).

## File Structure

ocx-model-validator (create unless marked modify):

```
ocx_model_validator/
  exeptions.py                     # modify: add GeometryError, SectionError
  model/ir/geometry.py             # modify: IrUnboundedGeometry; IrRefPlane.location
  model/ir/structural.py           # modify: IrPlate.outer_contour, IrStiffener.trace,
                                   #         IrPanel.unbounded_geometry
  model/ir/arrangement.py          # modify: IrCompartment.cog -> IrCog | None
  builders/v3_builder.py           # modify: populate all new fields
  sections/__init__.py             # public re-exports
  sections/units.py                # Quantity/point -> mm/MPa/m3 conversion helpers
  sections/geometry.py             # plane-curve intersection (numpy + de Boor)
  sections/frame_table.py          # FrameTable extraction + frame<->x helpers
  sections/section_builder.py      # CrossSection assembly (plates, stiffeners, profiles)
  sections/document.py             # lean JSON document build/save/load
  mcp/__init__.py
  mcp/state.py                     # module-level model holder
  mcp/server.py                    # FastMCP tools + main()
pyproject.toml                     # modify: numpy + mcp deps, ocx-mcp script, marker
tests/
  test_ir_sections_extension.py
  test_builder_sections_extension.py
  test_sections_units.py
  test_sections_geometry.py
  test_sections_frame_table.py
  test_sections_builder.py
  test_sections_document.py
  test_mcp_server.py
  test_sections_integration.py     # integration-marked, real VLCC model
```

nh-mcp:

```
pyproject.toml                     # modify: dev dep on ../ocx-model-validator (editable)
examples/demo_ocx_pipeline.py
tests/test_ocx_pipeline.py         # integration-marked, real NH run
```

---

### Task 1: IR extension

**Files:**
- Modify: `ocx_model_validator\model\ir\geometry.py`
- Modify: `ocx_model_validator\model\ir\structural.py`
- Modify: `ocx_model_validator\model\ir\arrangement.py`
- Test: `tests\test_ir_sections_extension.py`

- [ ] **Step 1: Write the failing tests**

```python
"""IR extensions for cross-section extraction (spec §3)."""
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, ParentKind, ParentRef, Quantity
from ocx_model_validator.model.ir.geometry import (
    IrLine3D,
    IrPlane3D,
    IrRefPlane,
    IrUnboundedGeometry,
)
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener

PARENT = ParentRef(kind=ParentKind.PANEL, id="panel1")


def test_plate_outer_contour_defaults_none():
    plate = IrPlate(id="p1", parent_ref=PARENT)
    assert plate.outer_contour is None


def test_plate_outer_contour_holds_curve():
    curve = IrLine3D(curve_length=None)
    plate = IrPlate(id="p1", parent_ref=PARENT, outer_contour=curve)
    assert plate.outer_contour is curve


def test_stiffener_trace_defaults_none():
    stiff = IrStiffener(id="s1", parent_ref=PARENT)
    assert stiff.trace is None


def test_panel_unbounded_geometry():
    panel = IrPanel(id="pn1")
    assert panel.unbounded_geometry is None
    ug = IrUnboundedGeometry(surface=IrPlane3D(), grid_ref="X59")
    panel2 = IrPanel(id="pn2", unbounded_geometry=ug)
    assert panel2.unbounded_geometry.grid_ref == "X59"
    assert panel2.unbounded_geometry.surface_ref is None


def test_ref_plane_location():
    rp = IrRefPlane(id="X59", name="X59", location=Quantity(59.2, "Um"))
    assert rp.location.value == 59.2
    assert IrRefPlane(id="X0").location is None


def test_compartment_cog_is_ircog():
    c = IrCompartment(id="c1", cog=IrCog(100.0, 0.0, 5.0, "Um"))
    assert c.cog.x == 100.0
    assert IrCompartment(id="c2").cog is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_ir_sections_extension.py -v`
Expected: FAIL — `ImportError: cannot import name 'IrUnboundedGeometry'`

- [ ] **Step 3: Implement the IR fields**

In `ocx_model_validator\model\ir\geometry.py`, after the `IrNurbsSurface` class (before the "standalone reference geometry" section), add:

```python
@dataclass(frozen=True)
class IrUnboundedGeometry:
    """Panel UnboundedGeometry: exactly one of an inline surface, a
    SurfaceRef (local_ref) or a GridRef (ref-plane id) is normally set."""
    surface: IrSurface3D | None = None
    surface_ref: str | None = None
    grid_ref: str | None = None
```

In the same file, extend `IrRefPlane` with a location field:

```python
@dataclass(frozen=True)
class IrRefPlane:
    id: str
    name: str | None = None
    reference_plane: IrPlane3D | None = None
    location: Quantity | None = None  # ReferenceLocation (position along axis)
```

In `ocx_model_validator\model\ir\structural.py`:
- add `IrUnboundedGeometry` to the existing `from ocx_model_validator.model.ir.geometry import (...)` list,
- append to `IrPlate`: `outer_contour: IrCurve3D | None = None`
- append to `IrStiffener` (after `penetrations`): `trace: IrCurve3D | None = None`
- append to `IrPanel` (after `limited_by`, before the helper methods): `unbounded_geometry: IrUnboundedGeometry | None = None`

In `ocx_model_validator\model\ir\arrangement.py`:
- change the import line to `from ocx_model_validator.model.ir.base import IrCog, Quantity, Ref`
- change `IrCompartment.cog: Quantity | None = None` to `cog: IrCog | None = None` (the field was never populated by the builder, so no consumer breaks).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_ir_sections_extension.py -v`
Expected: 6 PASS

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `uv run pytest`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/model/ir tests/test_ir_sections_extension.py
git commit -m "feat: add geometry fields to IR for cross-section extraction"
```

---

### Task 2: Builder population of the new IR fields

**Files:**
- Modify: `ocx_model_validator\builders\v3_builder.py`
- Test: `tests\test_builder_sections_extension.py`

Stubs use `types.SimpleNamespace` — the builder reads everything with `getattr`. Class NAMES matter for `_build_curve`/`_build_surface` dispatch (matched with `in type(elem).__name__.lower()`), so curve stubs must be classes with the right names.

- [ ] **Step 1: Write the failing tests**

```python
"""Builder population of cross-section IR fields (spec §3)."""
from types import SimpleNamespace as NS

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir.base import ParentKind, ParentRef
from ocx_model_validator.model.ir.geometry import IrCompositeCurve3D, IrLine3D
from ocx_model_validator.model.ir.structural import IrVessel

PARENT = ParentRef(kind=ParentKind.PANEL, id="panel1")


class Line3D:  # class name drives _build_curve dispatch
    def __init__(self, start, end):
        self.id = None
        self.curve_length = None
        self.start_point = start
        self.end_point = end


class CompositeCurve3D:
    def __init__(self, lines):
        self.id = "cc1"
        self.curve_length = None
        self.line3_d = lines
        self.poly_line3_d = []
        self.circum_arc3_d = []
        self.circle3_d = []
        self.ellipse3_d = []
        self.nurbs3_d = []


def _pt(x, y, z):
    return NS(coordinates=[x, y, z], unit="Um")


def _line(x1, x2):
    return Line3D(_pt(x1, 0.0, 0.0), _pt(x2, 0.0, 0.0))


def test_stiffener_trace_populated():
    raw = NS(id="st1", name="L1", guidref=None, physical_properties=None,
             material_ref=None, section_ref=None, function_type=None,
             end_cut_end1=None, end_cut_end2=None,
             trace_line=NS(composite_curve3_d=CompositeCurve3D([_line(0.0, 10.0)])))
    stiff = OcxV3Builder()._build_stiffener(raw, PARENT)
    assert isinstance(stiff.trace, IrCompositeCurve3D)
    assert isinstance(stiff.trace.segments[0], IrLine3D)


def test_plate_outer_contour_single_curve():
    raw = NS(id="pl1", name=None, guidref=None, plate_material=None,
             physical_properties=None, net_area=None, function_type=None,
             outer_contour=NS(composite_curve3_d=CompositeCurve3D([_line(0.0, 1.0)]),
                              nurbs3_d=None, line3_d=None, poly_line3_d=None,
                              circum_arc3_d=None, ellipse3_d=None, circle3_d=None))
    plate = OcxV3Builder()._build_plate(raw, PARENT)
    assert isinstance(plate.outer_contour, IrCompositeCurve3D)


def test_plate_outer_contour_absent():
    raw = NS(id="pl2", name=None, guidref=None, plate_material=None,
             physical_properties=None, net_area=None, function_type=None,
             outer_contour=None)
    assert OcxV3Builder()._build_plate(raw, PARENT).outer_contour is None


def test_nurbs_weights_populated():
    raw = NS(id=None, curve_length=None,
             nurbsproperties=NS(degree=1, is_rational=True, form=None),
             knot_vector=NS(value=[0.0, 0.0, 1.0, 1.0]),
             control_pt_list=NS(control_point=[
                 NS(coordinates=[0.0, 0.0, 0.0], unit="Um", weight=1.0),
                 NS(coordinates=[1.0, 0.0, 0.0], unit="Um", weight=0.5)]))
    raw.__class__ = type("Nurbs3D", (), {})
    curve = OcxV3Builder()._build_curve(raw)
    assert curve.weights == [1.0, 0.5]


def test_ref_plane_location_populated():
    ir = IrVessel(id="v1")
    cs = NS(id="cs1", name=None, is_global=True, local_cartesian=None,
            xref_planes=NS(ref_plane=[
                NS(id="X0", name="X0",
                   reference_location=NS(numericvalue=0.0, unit="Um")),
                NS(id="X59", name="X59.2",
                   reference_location=NS(numericvalue=59.2, unit="Um"))]),
            yref_planes=None, zref_planes=None)
    OcxV3Builder()._build_coordinate_system(cs, ir)
    assert ir.ref_planes["X59"].location.value == 59.2
    assert ir.ref_planes["X59"].location.unit == "Um"


def test_panel_unbounded_geometry_grid_ref():
    builder = OcxV3Builder()
    ug = builder._build_unbounded(NS(
        plane3_d=None, nurbssurface=None, extruded_surface=None,
        sphere3_d=None, cone3_d=None, cylinder3_d=None,
        grid_ref=NS(local_ref="X59", guidref=None), surface_ref=None))
    assert ug.grid_ref == "X59"
    assert ug.surface is None


def test_compartment_cog_populated():
    ir = IrVessel(id="v1")
    arrangement = NS(compartment=[NS(
        id="c1", name="WB1", guidref=None, compartment_purpose=None,
        compartment_face=[],
        compartment_properties=NS(
            center_of_gravity=NS(coordinates=[100.0, 0.0, 5.0], unit="Um"),
            volume=NS(numericvalue=1000.0, unit="Um3"), filling_height=None),
        liquid_cargo=[], bulk_cargo=[], unit_cargo=[])])
    OcxV3Builder()._build_compartments(arrangement, ir)
    assert ir.compartments["c1"].cog.x == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_builder_sections_extension.py -v`
Expected: FAIL — traces/contours are `None`, `_build_unbounded` missing, weights `[]`, `location`/`cog` `None`.

- [ ] **Step 3: Implement the builder changes**

All changes in `ocx_model_validator\builders\v3_builder.py`. Add imports `IrRefPlane` already imported; add `IrUnboundedGeometry` to the geometry import list and `IrCog` is already imported from base.

3a. New helper next to `_build_curve` (a contour/trace container has per-type curve fields that may be a single element or a list):

```python
    _CONTOUR_ATTRS = ("composite_curve3_d", "nurbs3_d", "line3_d",
                      "poly_line3_d", "circum_arc3_d", "ellipse3_d",
                      "circle3_d", "circum_circle3_d")

    def _build_contour(self, container):
        """Build one IR curve from a TraceLine/OuterContour container.

        Collects every curve child (fields may be single elements or lists).
        0 curves -> None, 1 -> the curve, >1 -> IrCompositeCurve3D wrapper.
        """
        if container is None:
            return None
        curves = []
        for attr in self._CONTOUR_ATTRS:
            val = getattr(container, attr, None)
            if val is None:
                continue
            elems = val if isinstance(val, (list, tuple)) else [val]
            for elem in elems:
                built = self._build_curve(elem)
                if built is not None:
                    curves.append(built)
        if not curves:
            return None
        if len(curves) == 1:
            return curves[0]
        return IrCompositeCurve3D(curve_length=None, segments=curves)
```

3b. In `_build_stiffener`, add to the `IrStiffener(...)` constructor call:

```python
            trace=self._build_contour(getattr(raw, "trace_line", None)),
```

3c. In `_build_plate`, add to the `IrPlate(...)` constructor call:

```python
            outer_contour=self._build_contour(getattr(raw, "outer_contour", None)),
```

3d. In `_build_curve`, nurbs branch: after `pts = [...]` extraction, build weights, and pass them:

```python
            weights = []
            if cpl is not None:
                for p in getattr(cpl, "control_point", None) or []:
                    w = getattr(p, "weight", None)
                    weights.append(float(w) if w is not None else 1.0)
```

and add `weights=weights,` to the `IrNurbs3D(...)` call.

3e. In `_build_coordinate_system._plane_ids`, populate the location:

```python
                    self._register(ir.ref_planes, rid,
                                   IrRefPlane(id=rid, name=getattr(rp, "name", None),
                                              location=self._qty(getattr(rp, "reference_location", None))),
                                   ir.duplicate_ids)
```

3f. New helper `_build_unbounded` (place after `_build_surface`), and wire it into `_build_panel`:

```python
    def _build_unbounded(self, ug):
        """Build IrUnboundedGeometry from a Panel/Plate UnboundedGeometry."""
        if ug is None:
            return None
        surface = None
        for attr in self._SURFACE_ATTRS:
            val = getattr(ug, attr, None)
            if val is None:
                continue
            elems = val if isinstance(val, (list, tuple)) else [val]
            for elem in elems:
                surface = self._build_surface(elem)
                if surface is not None:
                    break
            if surface is not None:
                break
        grid = getattr(ug, "grid_ref", None)
        sref = getattr(ug, "surface_ref", None)
        return IrUnboundedGeometry(
            surface=surface,
            surface_ref=(getattr(sref, "local_ref", None) or None) if sref else None,
            grid_ref=(getattr(grid, "local_ref", None) or None) if grid else None)
```

In `_build_panel`, add to the `IrPanel(...)` constructor call:

```python
            unbounded_geometry=self._build_unbounded(getattr(raw, "unbounded_geometry", None)),
```

3g. In `_build_compartments`, populate cog from `CompartmentProperties.center_of_gravity` (Point3D-like — reuse the same extraction shape as `_cog`):

```python
            cog_raw = getattr(cp, "center_of_gravity", None) if cp else None
            cog = None
            if cog_raw is not None:
                coords = getattr(cog_raw, "coordinates", None)
                if coords and len(coords) >= 3:
                    try:
                        cog = IrCog(x=float(coords[0]), y=float(coords[1]),
                                    z=float(coords[2]),
                                    unit=str(getattr(cog_raw, "unit", None) or ""))
                    except (TypeError, ValueError):
                        cog = None
```

and add `cog=cog,` to the `IrCompartment(...)` call. Verify `IrCog` is importable in the builder module (it is imported from `model.ir.base` already for `_cog`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_builder_sections_extension.py -v`
Expected: 7 PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/builders/v3_builder.py tests/test_builder_sections_extension.py
git commit -m "feat: populate contour/trace/ref-plane/compartment geometry in v3 builder"
```

---

### Task 3: Exceptions + unit conversion helpers

**Files:**
- Modify: `ocx_model_validator\exeptions.py`
- Create: `ocx_model_validator\sections\__init__.py`, `ocx_model_validator\sections\units.py`
- Test: `tests\test_sections_units.py`

- [ ] **Step 1: Write the failing tests**

```python
"""sections.units: Quantity/point conversion to mm / MPa / m3."""
import pytest

from ocx_model_validator.exeptions import GeometryError, SectionError, OcxParserError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
from ocx_model_validator.model.ir.geometry import IrPoint3D
from ocx_model_validator.sections.units import point_mm, qty_m3, qty_mm, qty_mpa, to_si

REGISTRY = {
    "Um": IrUnit(id="Um", symbol="m", to_si_factor=1.0),
    "Umm": IrUnit(id="Umm", symbol="mm", to_si_factor=0.001),
}


def test_exceptions_subclass_parser_error():
    assert issubclass(GeometryError, OcxParserError)
    assert issubclass(SectionError, OcxParserError)


def test_to_si_uses_registry():
    assert to_si(Quantity(59.2, "Um"), REGISTRY) == pytest.approx(59.2)
    assert to_si(Quantity(500.0, "Umm"), REGISTRY) == pytest.approx(0.5)


def test_to_si_fallback_without_registry():
    assert to_si(Quantity(2.0, "Um"), {}) == pytest.approx(2.0)
    assert to_si(Quantity(15.0, "Umm"), {}) == pytest.approx(0.015)
    assert to_si(Quantity(3.0, ""), {}) == pytest.approx(3.0)  # blank = SI


def test_to_si_unknown_unit_raises():
    with pytest.raises(GeometryError):
        to_si(Quantity(1.0, "Ufurlong"), REGISTRY)


def test_qty_mm_mpa_m3():
    assert qty_mm(Quantity(59.2, "Um"), REGISTRY) == pytest.approx(59200.0)
    assert qty_mm(None, REGISTRY) is None
    assert qty_mpa(Quantity(315e6, "UPa"), {}) == pytest.approx(315.0)
    assert qty_m3(Quantity(1000.0, "Um3"), {}) == pytest.approx(1000.0)


def test_point_mm():
    p = IrPoint3D(x=1.0, y=2.0, z=3.0, unit="Um")
    assert point_mm(p, REGISTRY) == pytest.approx((1000.0, 2000.0, 3000.0))
```

Note: check `IrPoint3D`'s actual field signature in `model/ir/geometry.py` before writing the test — adapt the constructor call if it differs (e.g. positional coords).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_sections_units.py -v`
Expected: FAIL — ImportError (no GeometryError, no sections package)

- [ ] **Step 3: Implement**

Append to `ocx_model_validator\exeptions.py`:

```python
class GeometryError(OcxParserError):
    """Geometric evaluation failed (unsupported curve, bad units, degenerate input)."""


class SectionError(OcxParserError):
    """Cross-section assembly failed (no frame table, position outside hull, ...)."""
```

(Use the actual base-class name in `exeptions.py` — verify it is `OcxParserError`; if the module's root exception is named differently, subclass that and fix the test import accordingly.)

`ocx_model_validator\sections\__init__.py`:

```python
"""Cross-section extraction from OCX IR models."""
```

(Public re-exports are added in later tasks as the modules appear.)

`ocx_model_validator\sections\units.py`:

```python
"""Convert IR quantities/points to the target units: mm, MPa, m3.

The OCX unit_registry (IrUnit.to_si_factor) is authoritative; a small
fallback table covers models that omit the units section. A blank unit
string means the value is already SI.
"""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
from ocx_model_validator.model.ir.geometry import IrPoint3D

_FALLBACK_SI = {
    "": 1.0,
    "Um": 1.0,
    "Umm": 1e-3,
    "Ucm": 1e-2,
    "Um3": 1.0,
    "UPa": 1.0,
    "UMPa": 1e6,
    "Ukg": 1.0,
    "Ut": 1e3,
}


def to_si(qty: Quantity, registry: dict[str, IrUnit]) -> float:
    """Return the SI value of qty using registry, falling back to _FALLBACK_SI."""
    unit = qty.unit or ""
    entry = registry.get(unit)
    if entry is not None and entry.to_si_factor is not None:
        return qty.value * entry.to_si_factor
    if unit in _FALLBACK_SI:
        return qty.value * _FALLBACK_SI[unit]
    raise GeometryError(f"Unknown unit id {unit!r}; cannot convert to SI")


def qty_mm(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) * 1000.0


def qty_mpa(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) / 1e6


def qty_m3(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry)


def point_mm(p: IrPoint3D, registry: dict[str, IrUnit]) -> tuple[float, float, float]:
    """Convert an IrPoint3D to an (x, y, z) tuple in millimetres."""
    unit = getattr(p, "unit", "") or ""
    f = 1000.0 * to_si(Quantity(1.0, unit), registry)
    return (p.x * f, p.y * f, p.z * f)
```

(Adapt `p.x/p.y/p.z` access if `IrPoint3D` stores coordinates differently.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_sections_units.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/exeptions.py ocx_model_validator/sections tests/test_sections_units.py
git commit -m "feat: add sections package with unit conversion and new exceptions"
```

---

### Task 4: Plane–curve intersection engine

**Files:**
- Create: `ocx_model_validator\sections\geometry.py`
- Modify: `pyproject.toml` (add `numpy` to `[project] dependencies`)
- Test: `tests\test_sections_geometry.py`

The one public function:

```python
intersect_curve_plane(curve, x_mm, to_mm, tol=0.1) -> list[tuple[float, float]]
```

`to_mm` is a callable `IrPoint3D -> (x, y, z) in mm` (the caller binds `point_mm` with the vessel registry), which keeps this module pure and unit-agnostic. Returns the (y, z) points in mm where the curve crosses the transverse plane X = x_mm. Dispatch on IR type:
- `IrLine3D`: exact parametric solve between start/end points.
- `IrPolyLine3D`: exact per-segment solve.
- `IrCompositeCurve3D`: union of segment results, dedupe points closer than `tol`.
- `IrNurbs3D`: de Boor evaluation (homogeneous coordinates when weights are non-uniform / rational), dense sampling (max(200, 20·n_ctrl) parameters over the knot range) to find sign changes of `x(t) - x_mm`, then bisection to `tol` on x.
- `IrCircumArc3D` / `IrCircle3D`: circle through the 3 defining points (or center+radius), sample 360 points, sign-change + bisection like NURBS.
- Anything else non-None: raise `GeometryError` naming the type.
- Curves with missing point data (e.g. `IrLine3D` without start/end): raise `GeometryError`.

- [ ] **Step 1: Add numpy dependency**

In `pyproject.toml` (repo root), append `"numpy>=1.26"` to `[project] dependencies`, then run `uv sync --all-groups` (or `uv lock && uv sync`).

- [ ] **Step 2: Write the failing tests**

`tests\test_sections_geometry.py` — key cases (use `to_mm = lambda p: (p.x * 1000, p.y * 1000, p.z * 1000)` for metre-based test points):

```python
def test_line_crossing():        # line (0,0,0)->(10,2,4) m at x=5000mm -> [(1000, 2000)]
def test_line_parallel_no_hit(): # line at constant x != plane -> []
def test_line_in_plane():        # both endpoints at x_mm -> both endpoints returned
def test_polyline_multi_cross(): # zig-zag crossing plane twice -> 2 points
def test_composite_dedupes_shared_vertex():  # two lines sharing the crossing vertex -> 1 point
def test_nurbs_linear_exact():   # degree-1 nurbs = polyline; result within 0.1mm of exact
def test_nurbs_rational_quarter_circle():
    # standard rational quadratic quarter circle r=1m in the xz-plane,
    # weights [1, sqrt(2)/2, 1]; plane at x = r*cos(45deg): z within 0.1mm of r*sin(45deg)
def test_circumarc_crossing():   # arc through 3 known points; verify crossing z
def test_unknown_curve_raises_geometry_error()
def test_line_missing_points_raises()
```

Write these out fully with hand-computed expected values (quarter-circle: at `x_mm = 707.10678`, expect `z ≈ 707.10678` within 0.1 mm).

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests\test_sections_geometry.py -v`
Expected: FAIL — module missing

- [ ] **Step 4: Implement `sections\geometry.py`**

Structure:

```python
"""Pure plane-curve intersection: transverse plane X = x_mm vs IR curves."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D, IrCircumArc3D, IrCompositeCurve3D, IrLine3D,
    IrNurbs3D, IrPolyLine3D,
)

ToMm = Callable[[object], tuple[float, float, float]]


def intersect_curve_plane(curve, x_mm: float, to_mm: ToMm,
                          tol: float = 0.1) -> list[tuple[float, float]]:
    if curve is None:
        return []
    if isinstance(curve, IrCompositeCurve3D):
        pts: list[tuple[float, float]] = []
        for seg in curve.segments:
            pts.extend(intersect_curve_plane(seg, x_mm, to_mm, tol))
        return _dedupe(pts, tol)
    if isinstance(curve, IrLine3D):
        return _segments_hits(_line_points(curve, to_mm), x_mm)
    if isinstance(curve, IrPolyLine3D):
        return _segments_hits([to_mm(p) for p in curve.points], x_mm)
    if isinstance(curve, IrNurbs3D):
        return _sampled_hits(_nurbs_evaluator(curve, to_mm), *_nurbs_domain(curve),
                             x_mm, tol, n=max(200, 20 * len(curve.control_points)))
    if isinstance(curve, (IrCircumArc3D, IrCircle3D)):
        return _sampled_hits(_circle_evaluator(curve, to_mm), 0.0, 1.0, x_mm, tol, n=360)
    raise GeometryError(f"Unsupported curve type for sectioning: {type(curve).__name__}")
```

Implementation notes (write real code for each — no placeholders):
- `_line_points`: raise `GeometryError` if start/end is None.
- `_segments_hits(points, x_mm)`: for each consecutive pair `(p0, p1)`: if both on plane (|dx| < 1e-9 for both) append both; elif `(x0 - x_mm)` and `(x1 - x_mm)` have opposite signs or one is 0, linear-interpolate t and append `(y, z)`. Dedupe at the end.
- `_dedupe(pts, tol)`: keep first of any pair within Euclidean distance `tol`.
- `_nurbs_evaluator`: convert control points via `to_mm` to an `(n,3)` array; weights default to all-1.0 when `curve.weights` is empty; de Boor on homogeneous coords `[w*x, w*y, w*z, w]`, divide by w after. Degree from `curve.degree`, knots `np.asarray(curve.knots)`. Domain = `(knots[degree], knots[-degree-1])`.
- `_sampled_hits(f, t0, t1, x_mm, tol, n)`: sample `x(t) - x_mm` at `n+1` params; for each sign change (or exact zero) bisect until `|x - x_mm| <= tol` (cap 100 iterations); collect `(y, z)`; dedupe.
- `_circle_evaluator`: for `IrCircumArc3D` use its 3 points (start/intermediate/end — check the IR field names in `geometry.py`) to compute center+radius via perpendicular-bisector solve in 3D (numpy lstsq on the plane of the 3 points); parametrize the arc from start to end through intermediate. For `IrCircle3D` use center/radius/normal if present, else its 3-point form. If the defining data is missing, raise `GeometryError`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests\test_sections_geometry.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/sections/geometry.py pyproject.toml uv.lock tests/test_sections_geometry.py
git commit -m "feat: plane-curve intersection engine (lines, polylines, NURBS, arcs)"
```

---

### Task 5: Frame table extraction

**Files:**
- Create: `ocx_model_validator\sections\frame_table.py`
- Test: `tests\test_sections_frame_table.py`

Semantics (must match nh-mcp `setup_frame_table`): labels are **strings**; VLCC X-plane names are metre positions ("X0", "X0.8", …). Label = ref-plane name (fallback id) minus a leading `X` when the remainder parses as a number; otherwise the name verbatim. Positions come from `IrRefPlane.location` (via `qty_mm`), planes without a location are skipped with a warning. `entries` lists `(label, spacing_mm)` at the first frame and wherever the forward spacing changes — the label where the new spacing STARTS. `frame0_offset_mm` = x of the label `"0"` if present, else the lowest x.

- [ ] **Step 1: Write the failing tests**

```python
"""FrameTable extraction from IR ref planes."""
import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.geometry import IrRefPlane
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table


def _vessel(planes, x_ids=None):
    ir = IrVessel(id="v1")
    for p in planes:
        ir.ref_planes[p.id] = p
    ir.x_ref_plane_ids = x_ids if x_ids is not None else [p.id for p in planes]
    return ir


def _plane(pid, name, x_m):
    return IrRefPlane(id=pid, name=name, location=Quantity(x_m, "Um"))


def test_positions_sorted_and_labeled():
    ir = _vessel([_plane("b", "X4", 4.0), _plane("a", "X0", 0.0),
                  _plane("c", "X8.8", 8.8)])
    ft = build_frame_table(ir)
    assert ft.positions == [("0", 0.0), ("4", pytest.approx(4000.0)),
                            ("8.8", pytest.approx(8800.0))]


def test_entries_emitted_on_spacing_change():
    # 0, 4, 8 (spacing 4000) then 8.8, 9.6 (spacing 800)
    ir = _vessel([_plane(f"p{i}", n, x) for i, (n, x) in enumerate(
        [("X0", 0.0), ("X4", 4.0), ("X8", 8.0), ("X8.8", 8.8), ("X9.6", 9.6)])])
    ft = build_frame_table(ir)
    assert ft.entries == [("0", pytest.approx(4000.0)),
                          ("8", pytest.approx(800.0))]
    assert ft.frame0_offset_mm == pytest.approx(0.0)


def test_frame0_offset_falls_back_to_lowest():
    ir = _vessel([_plane("a", "X-2", -2.0), _plane("b", "X2", 2.0)])
    assert build_frame_table(ir).frame0_offset_mm == pytest.approx(-2000.0)


def test_non_numeric_names_kept_verbatim():
    ir = _vessel([_plane("a", "AP", 0.0), _plane("b", "X10", 10.0)])
    ft = build_frame_table(ir)
    assert ft.positions[0][0] == "AP"


def test_planes_without_location_skipped_with_warning():
    ir = _vessel([_plane("a", "X0", 0.0),
                  IrRefPlane(id="b", name="X5"), _plane("c", "X10", 10.0)])
    ft = build_frame_table(ir)
    assert len(ft.positions) == 2
    assert any("X5" in w or "b" in w for w in ft.warnings)


def test_no_x_planes_raises():
    with pytest.raises(SectionError):
        build_frame_table(_vessel([]))


def test_frame_to_x_and_nearest():
    ir = _vessel([_plane("a", "X0", 0.0), _plane("b", "X4", 4.0)])
    ft = build_frame_table(ir)
    assert ft.frame_to_x("4") == pytest.approx(4000.0)
    with pytest.raises(SectionError):
        ft.frame_to_x("99")
    assert ft.nearest_frame(3900.0) == ("4", pytest.approx(4000.0))
```

Note: confirm `IrVessel` field names for the plane registry / x-plane id list (`ref_planes`, `x_ref_plane_ids`) in `model/ir/structural.py` before writing — adjust to actuals.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_sections_frame_table.py -v`

- [ ] **Step 3: Implement `sections\frame_table.py`**

```python
"""Derive the Nauticus frame table from OCX X reference planes."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.sections.units import qty_mm

_SPACING_TOL_MM = 1.0


def _label(name: str | None, pid: str) -> str:
    raw = (name or pid).strip()
    if raw[:1].upper() == "X":
        rest = raw[1:]
        try:
            float(rest)
            return rest
        except ValueError:
            pass
    return raw


@dataclass(frozen=True)
class FrameTable:
    frame0_offset_mm: float
    positions: list[tuple[str, float]]      # (label, x_mm), sorted by x
    entries: list[tuple[str, float]]        # (label, spacing_mm) at spacing changes
    warnings: list[str] = field(default_factory=list)

    def frame_to_x(self, frame: str) -> float:
        for label, x in self.positions:
            if label == frame:
                return x
        raise SectionError(f"Unknown frame label {frame!r}")

    def nearest_frame(self, x_mm: float) -> tuple[str, float]:
        return min(self.positions, key=lambda lx: abs(lx[1] - x_mm))


def build_frame_table(vessel: IrVessel) -> FrameTable:
    warnings: list[str] = []
    pos: list[tuple[str, float]] = []
    ids = vessel.x_ref_plane_ids or list(vessel.ref_planes)
    for pid in ids:
        rp = vessel.ref_planes.get(pid)
        if rp is None:
            warnings.append(f"X ref plane id {pid!r} not found")
            continue
        x = qty_mm(rp.location, vessel.unit_registry)
        if x is None:
            warnings.append(f"Ref plane {rp.name or pid!r} has no location; skipped")
            continue
        pos.append((_label(rp.name, pid), x))
    if not pos:
        raise SectionError("Model has no X reference planes with locations")
    pos.sort(key=lambda lx: lx[1])

    entries: list[tuple[str, float]] = []
    prev_spacing = None
    for i in range(len(pos) - 1):
        spacing = pos[i + 1][1] - pos[i][1]
        if prev_spacing is None or abs(spacing - prev_spacing) > _SPACING_TOL_MM:
            entries.append((pos[i][0], spacing))
            prev_spacing = spacing

    by_label = dict(pos)
    frame0 = by_label.get("0", pos[0][1])
    return FrameTable(frame0_offset_mm=frame0, positions=pos,
                      entries=entries, warnings=warnings)
```

Adjust `vessel.x_ref_plane_ids` / `vessel.ref_planes` / `vessel.unit_registry` attribute names to the actual `IrVessel` fields.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_sections_frame_table.py -v`

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/frame_table.py tests/test_sections_frame_table.py
git commit -m "feat: frame table derivation from X reference planes"
```

---

### Task 6: Cross-section assembly

**Files:**
- Create: `ocx_model_validator\sections\section_builder.py`
- Test: `tests\test_sections_builder.py`

Output dataclasses (frozen):

```python
@dataclass(frozen=True)
class SectionStiffener:
    name: str
    y_mm: float
    z_mm: float
    panel: str | None
    profile_type: str | None       # HpBulb / FlatBar / TBar / AngleBar
    profile_dimensions: str | None # "300 x 11" style, mm
    material_reh_mpa: float | None
    spacing_mm: float | None       # nearest neighbour on same panel, None if alone
    orientation: str = "Longitudinal"
    web_angle_deg: float = 90.0

@dataclass(frozen=True)
class SectionPlate:
    name: str
    y1_mm: float; z1_mm: float; y2_mm: float; z2_mm: float
    thickness_mm: float | None
    material_reh_mpa: float | None
    panel: str | None

@dataclass(frozen=True)
class CrossSection:
    x_mm: float
    frame: str | None
    stiffeners: list[SectionStiffener]
    plates: list[SectionPlate]
    warnings: list[str]
```

Public API: `build_cross_section(vessel, x_mm, frame=None, tol=0.1) -> CrossSection`.

Rules:
- Walk all panels; for each stiffener with a `trace`, intersect with the plane; every hit becomes a `SectionStiffener` (orientation fixed "Longitudinal", web_angle 90.0 per spec).
- Profile mapping from resolved `IrSection` (via `section_ref` → `vessel.sections` catalogue; dims via `qty_mm`, rounded to 1 decimal, formatted `" x ".join(...)` with integers rendered without `.0`):
  - `IrBulbFlatSection` → `("HpBulb", f"{h} x {tw}")`
  - `IrFlatBarSection` → `("FlatBar", f"{h} x {w}")`
  - `IrTSection` → `("TBar", f"{h} x {w} x {tw} x {tf}")`
  - `IrLSection` (and overshoot variants) → `("AngleBar", f"{h} x {w} x {tw} x {tf}")`
  - unknown/missing → both None + warning (stiffener still emitted).
- Material Reh via `material_ref` → `vessel.materials` → `qty_mpa(yield_stress)`; None + no warning if absent.
- `spacing_mm`: per panel, Euclidean nearest-neighbour distance in (y, z) among that panel's section stiffeners; None + warning when the panel has a single stiffener.
- Plates: intersect `outer_contour`; sort hit points by (z, y); pair consecutive points `(p0,p1), (p2,p3), …`; odd leftover point → warning, dropped; each pair → `SectionPlate` (thickness = plate thickness via `qty_mm` — check the actual `IrPlate` thickness field name in `structural.py`).
- Per-item `GeometryError` → warning `f"{kind} {name}: {exc}"`, item skipped; never abort the section.
- Empty result (no plates and no stiffeners) → raise `SectionError`.

- [ ] **Step 1: Write the failing tests**

Build a small synthetic `IrVessel` fixture in the test: 1 panel, 2 plates with rectangular polyline contours crossing x=5000 mm, 3 stiffeners with straight line traces (two on the panel 800 mm apart → spacing check; one on another panel alone → spacing None + warning), one stiffener with a `IrBulbFlatSection` (h 300 mm, tw 11 mm) → `("HpBulb", "300 x 11")`, one with no section_ref → None profile + warning, one stiffener whose trace lies outside the plane → excluded. Also: `test_unknown_curve_becomes_warning` (stub curve type inside a trace → warning, not raise), `test_empty_section_raises` (x far outside → `SectionError`), `test_plate_odd_hits_warning`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_sections_builder.py -v`

- [ ] **Step 3: Implement `sections\section_builder.py`** per the rules above. Bind `to_mm = lambda p: point_mm(p, vessel.unit_registry)` once. Stiffener/plate names: `name or id`. Resolve refs with both `local_ref` and guid lookups if the catalogue is keyed by id (check how existing code resolves `section_ref`/`material_ref` — follow the same pattern).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_sections_builder.py -v`

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/section_builder.py tests/test_sections_builder.py
git commit -m "feat: cross-section assembly with profiles, spacing and plate pairing"
```

---

### Task 7: JSON document build / save / load

**Files:**
- Create: `ocx_model_validator\sections\document.py`
- Modify: `ocx_model_validator\sections\__init__.py` (re-export the public API)
- Test: `tests\test_sections_document.py`

JSON schema (spec §5 — units mm / MPa / m³):

```json
{
  "schema": "nh-cross-section/1",
  "source": {"file": "...", "vessel_id": "...", "generated": "ISO-8601"},
  "frame_table": {
    "frame0_offset_mm": 0.0,
    "entries": [{"frame_no": "0", "spacing_mm": 4000.0}],
    "positions": [{"frame_no": "0", "x_mm": 0.0}]
  },
  "cross_section": {
    "x_mm": 59200.0, "frame": "59.2",
    "stiffeners": [{"name": "...", "y_mm": 0, "z_mm": 0, "panel": null,
      "profile_type": null, "profile_dimensions": null, "material_reh_mpa": null,
      "spacing_mm": null, "orientation": "Longitudinal", "web_angle_deg": 90.0}],
    "plates": [{"name": "...", "y1_mm": 0, "z1_mm": 0, "y2_mm": 0, "z2_mm": 0,
      "thickness_mm": null, "material_reh_mpa": null, "panel": null}]
  },
  "compartments": [{"name": "...", "tank_type": "BALLASTWATERTANK",
    "cog_mm": [0, 0, 0], "volume_m3": null,
    "extent_mm": {"min_x": null, "max_x": null, "min_y": null, "max_y": null,
                  "min_z": null, "max_z": null}}],
  "warnings": ["..."]
}
```

Public API:
- `build_document(vessel, source_file, x_mm=None, frame=None) -> dict` — exactly one of x_mm/frame (raise `SectionError` otherwise); frame resolved through the frame table; when called with x_mm, `frame` in the output is the nearest label only if within 1 mm, else null.
- `save_document(doc, path)` / `load_document(path) -> dict` — load validates required top-level keys (`schema`, `frame_table`, `cross_section`, `compartments`) and the schema string, raising `SectionError` on mismatch.
- Compartments: tank type mapped from `IrCompartment` purpose/function string, case-insensitive substring: void→VOIDSPACE, ballast→BALLASTWATERTANK, fuel/hfo/mdo→FUELTANK, fresh→FRESHWATERTANK, cargo→CARGOHOLD; fallback = verbatim uppercase (or "VOIDSPACE" when absent, + warning). `cog_mm` from `IrCompartment.cog` (convert with the cog's own unit through the registry). `extent_mm` = bounding box of the COGs of plates belonging to panels referenced by the compartment's face refs (match refs against panel guid and id); all-null + warning when unresolvable.
- All floats rounded to 2 decimals in the document.

- [ ] **Step 1: Write the failing tests** — reuse the Task 6 synthetic vessel fixture (move it to a `tests\section_fixtures.py` helper module and import from both test files). Cases: document has all top-level keys + schema string; exclusive x/frame arg validation raises; frame→x resolution works; compartment tank-type mapping table (parametrized); save→load round-trip; load rejects a JSON missing `cross_section`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests\test_sections_document.py -v`

- [ ] **Step 3: Implement `sections\document.py`**, and set `sections\__init__.py` to:

```python
"""Cross-section extraction from OCX IR models."""
from ocx_model_validator.sections.document import (
    build_document, load_document, save_document,
)
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table
from ocx_model_validator.sections.section_builder import (
    CrossSection, SectionPlate, SectionStiffener, build_cross_section,
)

__all__ = [
    "FrameTable", "build_frame_table",
    "CrossSection", "SectionPlate", "SectionStiffener", "build_cross_section",
    "build_document", "save_document", "load_document",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests\test_sections_document.py -v`

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/sections tests/test_sections_document.py tests/section_fixtures.py
git commit -m "feat: lean JSON cross-section document with compartments"
```

---

### Task 8: ocx-mcp FastMCP server

**Files:**
- Create: `ocx_model_validator\mcp\__init__.py`, `ocx_model_validator\mcp\state.py`, `ocx_model_validator\mcp\server.py`
- Modify: `pyproject.toml` (repo root)
- Test: `tests\test_mcp_server.py`

- [ ] **Step 1: pyproject changes**

- `[project] dependencies`: add `"mcp>=1.0,<2"`.
- `[project.scripts]`: add `ocx-mcp = "ocx_model_validator.mcp.server:main"`.
- `[tool.pytest.ini_options]`: add `markers = ["integration: requires the real OCX reference model"]` and append `-m "not integration"` to `addopts` (keep existing flags).
- Run `uv sync --all-groups`.

- [ ] **Step 2: Write the failing tests**

FastMCP 1.x `@mcp.tool()` returns the original function, so tests call the tools directly. Tool listing via `asyncio.run(mcp.list_tools())`.

```python
"""ocx-mcp server tools (unit level, synthetic vessel via monkeypatched loader)."""
import asyncio

import pytest

from ocx_model_validator.mcp import server, state
from tests.section_fixtures import make_synthetic_vessel  # from Task 7


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()
    yield
    state.reset()


def test_six_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {
        "load_model", "get_model_info", "get_frame_table",
        "get_compartments", "build_cross_section", "save_cross_section"}


def test_tools_require_loaded_model():
    for fn in (server.get_model_info, server.get_frame_table,
               server.get_compartments):
        out = fn()
        assert out["ok"] is False and "load_model" in out["error"]


def test_load_model_missing_file():
    out = server.load_model(r"C:\nope\missing.ocx")
    assert out["ok"] is False


def test_pipeline_with_synthetic_model(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_load_vessel",
                        lambda path: make_synthetic_vessel())
    assert server.load_model("fake.ocx")["ok"] is True
    info = server.get_model_info()
    assert info["ok"] and info["counts"]["stiffeners"] >= 1
    ft = server.get_frame_table()
    assert ft["ok"] and ft["frame_table"]["positions"]
    cs = server.build_cross_section(x_mm=5000.0)
    assert cs["ok"] and cs["document"]["cross_section"]["plates"]
    assert server.build_cross_section()["ok"] is False          # neither arg
    assert server.build_cross_section(x_mm=1.0, frame="0")["ok"] is False  # both
    out = tmp_path / "sec.json"
    saved = server.save_cross_section(str(out), x_mm=5000.0)
    assert saved["ok"] and out.exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests\test_mcp_server.py -v`

- [ ] **Step 4: Implement**

`mcp\__init__.py`: `"""ocx-mcp: MCP server exposing OCX cross-section extraction."""`

`mcp\state.py`:

```python
"""Process-wide model state for the ocx-mcp server."""
from __future__ import annotations

from ocx_model_validator.model.ir.structural import IrVessel

vessel: IrVessel | None = None
source_file: str | None = None


def set_model(v: IrVessel, path: str) -> None:
    global vessel, source_file
    vessel, source_file = v, path


def reset() -> None:
    global vessel, source_file
    vessel = source_file = None
```

`mcp\server.py` — every tool returns a JSON-safe dict with `ok: bool`; all exceptions caught and returned as `{"ok": False, "error": str(exc)}`:

```python
"""ocx-mcp: FastMCP server for OCX cross-section extraction."""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.mcp import state
from ocx_model_validator.parsers.parser import OcxParser
from ocx_model_validator.sections import build_document, save_document
from ocx_model_validator.sections.frame_table import build_frame_table

mcp = FastMCP("ocx-mcp")


def _load_vessel(path: str):
    root = OcxParser().parse(Path(path))
    return get_builder(getattr(root, "schema_version", "unknown")).build(root)


def _require_model():
    if state.vessel is None:
        raise RuntimeError("No model loaded; call load_model first")
    return state.vessel
```

Tools (each wrapped in try/except returning the error dict):
- `load_model(path: str)` — check file exists; `_load_vessel`; `state.set_model`; return `{"ok": True, "vessel_id", counts}`.
- `get_model_info()` — vessel id/name + counts of panels, plates, stiffeners, compartments, ref planes, materials, sections.
- `get_frame_table()` — `build_frame_table` → same dict shape as the document's `frame_table` block + warnings.
- `get_compartments()` — the document's `compartments` block (factor the compartment-block builder in `document.py` so both call it — expose it as `build_compartments_block(vessel)`).
- `build_cross_section(x_mm: float | None = None, frame: str | None = None)` — full document via `build_document(vessel, state.source_file, x_mm=x_mm, frame=frame)`.
- `save_cross_section(path: str, x_mm: float | None = None, frame: str | None = None)` — build + `save_document`; return `{"ok": True, "path": path}`.

`main()`:

```python
def main() -> None:
    mcp.run()
```

- [ ] **Step 5: Run tests, then full suite**

Run: `uv run pytest tests\test_mcp_server.py -v` then `uv run pytest`

- [ ] **Step 6: Smoke-test the console script**

Run: `uv run ocx-mcp --help` is not supported by FastMCP; instead verify import: `uv run python -c "from ocx_model_validator.mcp.server import main; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/mcp pyproject.toml uv.lock tests/test_mcp_server.py
git commit -m "feat: ocx-mcp FastMCP server with six cross-section tools"
```

---

### Task 9: Integration test against the real VLCC model

**Files:**
- Create: `tests\test_sections_integration.py`

Model path: `C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx`. Runs only with `-m integration` (excluded by default addopts). Parsing the 21 MB model takes a while — use a module-scoped fixture.

- [ ] **Step 1: Write the test**

```python
"""Integration: real VLCC model end-to-end (parse -> frame table -> section -> JSON)."""
from pathlib import Path

import pytest

MODEL = Path(r"C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODEL.exists(), reason="VLCC reference model not present"),
]


@pytest.fixture(scope="module")
def vessel():
    from ocx_model_validator.builders.factory import get_builder
    from ocx_model_validator.parsers.parser import OcxParser
    root = OcxParser().parse(MODEL)
    return get_builder(getattr(root, "schema_version", "unknown")).build(root)


def test_frame_table(vessel):
    from ocx_model_validator.sections.frame_table import build_frame_table
    ft = build_frame_table(vessel)
    assert len(ft.positions) > 100          # ~402 X planes in the model
    assert ft.entries                        # at least one spacing entry
    xs = [x for _, x in ft.positions]
    assert xs == sorted(xs)


def test_midship_cross_section(vessel):
    from ocx_model_validator.sections.frame_table import build_frame_table
    from ocx_model_validator.sections.section_builder import build_cross_section
    ft = build_frame_table(vessel)
    mid_x = (ft.positions[0][1] + ft.positions[-1][1]) / 2.0
    label, x = ft.nearest_frame(mid_x)
    cs = build_cross_section(vessel, x_mm=x)
    assert len(cs.stiffeners) > 50
    assert len(cs.plates) > 10
    assert all(s.orientation == "Longitudinal" for s in cs.stiffeners)


def test_document_round_trip(vessel, tmp_path):
    from ocx_model_validator.sections import (
        build_document, load_document, save_document)
    from ocx_model_validator.sections.frame_table import build_frame_table
    ft = build_frame_table(vessel)
    label, x = ft.nearest_frame(
        (ft.positions[0][1] + ft.positions[-1][1]) / 2.0)
    doc = build_document(vessel, str(MODEL), x_mm=x)
    assert doc["schema"] == "nh-cross-section/1"
    assert doc["compartments"]
    p = tmp_path / "section.json"
    save_document(doc, p)
    assert load_document(p)["cross_section"]["stiffeners"]
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests\test_sections_integration.py -m integration -v` (allow several minutes)
Expected: 3 PASS. If assertions on counts fail, print the actual counts, inspect warnings on the CrossSection, and fix the extraction (not the thresholds) unless the real model genuinely has fewer items at that x — in that case pick the documented midship frame and justify the threshold change in the commit message.

- [ ] **Step 3: Verify default run still excludes integration**

Run: `uv run pytest` — integration tests must show as deselected.

- [ ] **Step 4: Commit**

```bash
git add tests/test_sections_integration.py
git commit -m "test: end-to-end integration against VLCC reference model"
```

---

### Task 10: nh-mcp demo + pipeline integration test

**Repo: `C:\PythonDev\nh-mcp`** (run all commands from there).

**Files:**
- Modify: `pyproject.toml`
- Create: `examples\demo_ocx_pipeline.py`
- Create: `tests\test_ocx_pipeline.py`

- [ ] **Step 1: Add the editable dev dependency**

In `C:\PythonDev\nh-mcp\pyproject.toml`: add `"ocx-model-validator"` to the `dev` dependency group and:

```toml
[tool.uv.sources]
ocx-model-validator = { path = "../ocx-model-validator", editable = true }
```

Run: `uv sync --all-groups` then `uv run python -c "import ocx_model_validator; print('ok')"`

- [ ] **Step 2: Write `examples\demo_ocx_pipeline.py`**

Follow the structure/UNITS/table conventions of `examples\demo_tanker_tutorial.py`. Flow:
1. Parse the OCX model (`examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx`) via ocx-model-validator, build the document at the midship frame (`build_frame_table` → `nearest_frame` at mid-x → `build_document`), print frame-table and section summaries with units (mm, MPa, m³).
2. `initialize_api()`, open the Tanker Tutorial workspace as scratch (same pattern as demo_tanker_tutorial.py).
3. `setup_frame_table(frame0_offset=doc["frame_table"]["frame0_offset_mm"], entries=[FrameEntry(e["frame_no"], e["spacing_mm"]) for e in entries])`.
4. Create the document's compartments via `create_compartment` (skip + note any with null cog/extent; volume may be None → pass 0.0 is NOT acceptable — skip instead with a printed note).
5. Helper `adjacent_compartment(doc, y_mm, z_mm) -> str`: compartment whose extent box (with 500 mm slack) contains (y, z); else nearest by COG distance — always returns a real created-compartment name.
6. Pick up to 3 plates and 3 stiffeners from the section (prefer ones with thickness/profile data); run `calculate_shell_plate` / `calculate_stiffener` with document values (frame label from doc, spacing from stiffener/frame table, compartment from the helper; sensible constants where the doc has no value: `unsupported_length=frame spacing*4`, `tgr=0.0`, `position="L"`, `slope=0`).
7. Print one input+result table for plates and one for stiffeners (columns with units, like demo_tanker_tutorial.py).

- [ ] **Step 3: Run the demo**

Run: `uv run python examples\demo_ocx_pipeline.py`
Expected: frame table + section summary printed, ≥1 plate and ≥1 stiffener NH result rows without errors. Debug data-quality issues via the document's `warnings` list.

- [ ] **Step 4: Write `tests\test_ocx_pipeline.py`**

Integration-marked (add the same `markers`/`-m "not integration"` pytest config to nh-mcp's pyproject if not present), `skipif` when the OCX model or the NH backend is unavailable (follow the guard pattern of existing nh-mcp integration tests). Import the demo's building blocks (refactor the demo so its steps are functions importable without running `__main__`) and assert: frame table set up ok, ≥1 compartment created, ≥1 `calculate_shell_plate` and ≥1 `calculate_stiffener` return successful results.

Run: `uv run pytest tests\test_ocx_pipeline.py -m integration -v`

- [ ] **Step 5: Verify default nh-mcp suite unaffected**

Run: `uv run pytest`

- [ ] **Step 6: Commit (nh-mcp repo)**

```bash
git add pyproject.toml uv.lock examples/demo_ocx_pipeline.py tests/test_ocx_pipeline.py
git commit -m "feat: OCX-to-Nauticus pipeline demo and integration test"
```

---

## Verification checklist (after all tasks)

- [ ] `uv run pytest` green in ocx-model-validator (integration deselected)
- [ ] `uv run pytest -m integration` green in ocx-model-validator
- [ ] `uv run python examples\demo_ocx_pipeline.py` succeeds in nh-mcp
- [ ] `uv run pytest -m integration` green in nh-mcp
- [ ] `ocx-mcp` console script importable
- [ ] Spec §1–§8 all covered (IR, builder, sections math, frame table, section, document, MCP, nh-mcp demo)

