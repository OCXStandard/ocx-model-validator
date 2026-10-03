# OCX 3.2.0 IR Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all IR and builder gaps against OCX schema 3.2.0 so 3.2.0 models build without data loss, while 3.0/3.1 models keep working.

**Architecture:** Adopt 3.2.0 shapes as the IR canon (`MassProperties`, `Steel`/`Aluminium` materials, renewal thicknesses, ref offsets). The single `OcxV3Builder` reads 3.2.0 element names first and falls back to 3.1.0 names via `getattr`. Stubs are regenerated from `models/` (incl. new `models/TR05` 3.2.0 files) and the existing version-parametrized test suite covers all versions.

**Tech Stack:** Python 3.12+, uv, pytest, xsdata OCX bindings (`ocx` package), loguru, typer CLI.

**Spec:** `docs/superpowers/specs/2026-10-03-ocx-320-ir-gap-closure-design.md`

**Baseline:** `uv run pytest` → 374 passed, 31 skipped (verified 2026-10-03). Every task must end green.

**Conventions (mandatory):**
- All raw OCX access: `getattr(obj, "field", None)`. Never direct attribute access in the builder.
- All new IR fields default to `None` or `[]`.
- Run commands from repo root. Use `uv run pytest ...`.
- Each commit message ends with the trailer:
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

**Verified 3.2.0 binding facts (from `ocx.ocx_320.ocx_320`) — trust these, do not re-derive:**
- `MassPropertiesT` fields: `moulded_dry_weight`, `moulded_center_of_gravity`, `physical_dry_weight`, `physical_center_of_gravity`. CoG elements have `coordinates: list[float]` + `unit: str`.
- `SteelT`: classic `yield_stress`, `ultimate_stress`, `grade` (+ density, youngs_modulus, poisson_ratio, thermal_expansion_coefficient).
- `AluminiumT`: `unwelded_yield_strength`, `welded_yield_strength`, `unwelded_tensile_strength`, `welded_tensile_strength`, `alloy_designation` (no grade/yield_stress).
- `MaterialCatalogueT`: `steel: list`, `aluminium: list` (3.1.0 had `material: list`).
- `PlateMaterialRefT`: + `renewal_thickness`, `voluntary_thickness_addition`.
- `SectionRefT`: + `web_renewal_thickness`, `flange_renewal_thickness`, `voluntary_web_thickness_addition`, `voluntary_flange_thickness_addition`.
- `OccurrenceT` 3.2.0 ref fields are **lists**: `str_stiffener_ref`, `str_seam_ref`, `str_edge_reinforcement_ref`, `plate_ref`, `bracket_ref`, `pillar_ref`, `hole_contour_ref`, `lug_plate_ref`, `connected_bracket_ref` (3.1.0 names: `stiffener_ref`, `seam_ref`, `edge_reinforcement_ref`).
- `UnboundedGeometryT` 3.2.0: `unbounded_grid_ref: list`, `unbounded_surface_ref: list` (3.1.0: `grid_ref`, `surface_ref` singles).
- `Plane3DT` 3.2.0: `point_on_surface` (3.1.0: `origin`), plus `normal`, `udirection`.
- `PlateT` 3.2.0: `outer_contour` is a **list**; + `mass_properties`, `point_on_surface`, `plate_cut_by`.
- `PlateCutByT` 3.2.0: `inner_contour: list` (3.1.0: `outer_contour`), plus `hole2_dcontour`, `slot_contour`.
- `TraceLineT` 3.2.0: + singles `edge_curve_ref`, `edge_reinforcement_ref`, `grid_ref`, `panel_ref`, `seam_ref`, `stiffener_ref`, `surface_ref`.
- `StiffenerT`/`EdgeReinforcementT` 3.2.0: + `orientation_rule` (enum `OrientationRuleValue`).
- `PenetrationT`/`ConnectionConfigurationT` 3.2.0: + single `bracket_ref`.
- `Hole2DT` 3.2.0: + parametric variants `ellipse`, `rectangular_mickey_mouse_ears`.
- `RoundBarT` 3.2.0: `diameter` (3.1.0: `height`). `BarSectionT`: + `catalogue_reference: str | None`.
- `PrincipalParticularsT` 3.2.0: + `minimum_ballast_draught`. `BulkCargoT` 3.2.0: + `density`.
- `BoundedRefT` (LimitedBy refs) 3.2.0: + `offset`, `offset_direction`; `contour_bounds` gains `contour_mid_point`. `OffsetDirection` has `direction: list[float]`.
- `tests/data/ocx_320_stubs/` already exists (170 files) and is auto-discovered by conftest; it will be regenerated in Task 9.

---

## File structure overview

| File | Change |
|---|---|
| `ocx_model_validator/model/ir/base.py` | + `IrVector3D` (moved from geometry), `IrMassProperties`; `Ref` gains offset fields |
| `ocx_model_validator/model/ir/geometry.py` | `IrVector3D` re-imported; `IrPlane3D.origin` → `point_on_surface`; surfaces gain `normal`/`point_on_surface` |
| `ocx_model_validator/model/ir/structural.py` | parts: `dry_weight`/`cog` → `mass_properties`; + `orientation_rule`, `point_on_surface`, scantling fields, `trace_refs`, `cut_by_contours`; `IrLimitedByRef` + offsets/`contour_mid_point` |
| `ocx_model_validator/model/ir/catalogues.py` | `IrMaterial` + type/strength fields; |
| `ocx_model_validator/model/ir/sections.py` | `IrSection.catalogue_reference` |
| `ocx_model_validator/model/ir/connections.py` | + `bracket_ref` field |
| `ocx_model_validator/model/ir/metadata.py` | + `minimum_ballast_draught` |
| `ocx_model_validator/model/ir/arrangement.py` | `IrBulkCargo` + `density` |
| `ocx_model_validator/model/ir/__init__.py` | export `IrMassProperties` |
| `ocx_model_validator/builders/v3_builder.py` | all extraction changes (new-name-first + fallback) |
| `ocx_model_validator/reporting/generators/bom.py` | `dry_weight` → `mass_properties.moulded_dry_weight` |
| `ocx_model_validator/reporting/generators/_compartment_data.py` | `plate.cog` → `plate.mass_properties.moulded_cog` |
| `tests/test_ir_320_gap.py` | NEW — IR-level tests for all new types/fields |
| `tests/test_builder_320_gap.py` | NEW — builder dual-path (3.1 vs 3.2) tests |
| `tests/test_builders.py`, `tests/test_reporting_bom.py`, `tests/test_ir_structural_additions.py` | migrate `dry_weight`/`cog` usages |
| `tests/data/ocx_320_stubs/` | regenerated via `validator generate-stubs --force` |
| `ocx_model_validator.md`, `.github/copilot-instructions.md` | doc updates |

---

### Task 1: `IrMassProperties` + `Ref` offsets (base.py)

**Files:**
- Modify: `ocx_model_validator/model/ir/base.py`
- Modify: `ocx_model_validator/model/ir/geometry.py` (move `IrVector3D` out, re-import)
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Test: `tests/test_ir_320_gap.py` (new)

`Ref.offset_direction` needs `IrVector3D`, but `geometry.py` imports from `base.py`. Resolve by **moving `IrVector3D` to `base.py`** and re-importing it in `geometry.py` so all existing imports keep working.

- [ ] **Step 1: Write failing tests**

Create `tests/test_ir_320_gap.py`:

```python
"""Tests for OCX 3.2.0 IR gap closure additions."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrCog,
    IrMassProperties,
    IrVector3D,
    Quantity,
    Ref,
)


def test_mass_properties_defaults():
    mp = IrMassProperties()
    assert mp.moulded_dry_weight is None
    assert mp.physical_dry_weight is None
    assert mp.moulded_cog is None
    assert mp.physical_cog is None


def test_mass_properties_populated():
    mp = IrMassProperties(
        moulded_dry_weight=Quantity(1000.0, "UKg"),
        moulded_cog=IrCog(1.0, 2.0, 3.0, "Um"),
    )
    assert mp.moulded_dry_weight.value == 1000.0
    assert mp.moulded_cog.z == 3.0


def test_ref_offset_defaults_and_population():
    r = Ref(local_ref="x1")
    assert r.offset is None and r.offset_direction is None
    r2 = Ref(local_ref="x2", offset=Quantity(5.0, "Umm"),
             offset_direction=IrVector3D(0.0, 0.0, 1.0))
    assert r2.offset.value == 5.0
    assert r2.offset_direction.z == 1.0


def test_vector3d_importable_from_base_and_geometry():
    from ocx_model_validator.model.ir.base import IrVector3D as V1
    from ocx_model_validator.model.ir.geometry import IrVector3D as V2
    assert V1 is V2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_320_gap.py -v`
Expected: FAIL — `ImportError: cannot import name 'IrMassProperties'`

- [ ] **Step 3: Implement**

In `ocx_model_validator/model/ir/base.py`, insert after `Quantity` (before `IrUnit`):

```python
@dataclass(frozen=True)
class IrVector3D:
    """A dimensionless 3D direction vector."""
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class IrMassProperties:
    """Mass properties of a structural part (OCX 3.2.0 ``MassProperties``).

    For 3.0/3.1 models the builder maps the legacy ``PhysicalProperties``
    ``dry_weight``/``center_of_gravity`` onto the *moulded* fields; the
    physical fields stay ``None``.
    """
    moulded_dry_weight: Quantity | None = None
    physical_dry_weight: Quantity | None = None
    moulded_cog: IrCog | None = None
    physical_cog: IrCog | None = None
```

Replace the `Ref` dataclass body in `base.py` with:

```python
@dataclass(frozen=True)
class Ref:
    """A reference to another structural part by XML id and/or GUIDRef.

    ``offset``/``offset_direction`` carry the OCX 3.2.0 ref offset; ``None``
    for 3.0/3.1 models and refs without an offset.
    """
    local_ref: str
    guidref: str | None = None
    offset: Quantity | None = None
    offset_direction: IrVector3D | None = None

    def __repr__(self) -> str:
        if self.guidref:
            return f"Ref({self.local_ref!r}, guid={self.guidref!r})"
        return f"Ref({self.local_ref!r})"
```

In `ocx_model_validator/model/ir/geometry.py`:
1. Change the base import to `from ocx_model_validator.model.ir.base import IrVector3D, Quantity` (the re-import keeps `from ...geometry import IrVector3D` working).
2. Delete the `IrVector3D` class definition (the `@dataclass(frozen=True)` block defining it).

In `ocx_model_validator/model/ir/__init__.py`:
1. Add `IrMassProperties,` to the `from ocx_model_validator.model.ir.base import (...)` block (alphabetical: after `IrCog`).
2. Add `"IrMassProperties",` to `__all__` in the `# base` group.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_ir_320_gap.py tests/test_ir_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest -q` — expected: 378 passed (374 + 4 new), 31 skipped.

```bash
git add ocx_model_validator/model/ir/base.py ocx_model_validator/model/ir/geometry.py ocx_model_validator/model/ir/__init__.py tests/test_ir_320_gap.py
git commit -m "feat(ir): add IrMassProperties and Ref offsets; move IrVector3D to base"
```

---

### Task 2: Builder `_mass_properties` helper + additive `mass_properties` field on parts

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py` (add field to 7 classes — keep `dry_weight`/`cog` for now)
- Modify: `ocx_model_validator/builders/v3_builder.py`
- Test: `tests/test_builder_320_gap.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/test_builder_320_gap.py`:

```python
"""Builder dual-path tests: OCX 3.2.0 names first, 3.1.0 fallback."""
from __future__ import annotations

from types import SimpleNamespace as NS

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import ParentKind, ParentRef

PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _b() -> OcxV3Builder:
    return OcxV3Builder()


def _qty(value, unit):
    return NS(numericvalue=value, unit=unit)


def _cog(x, y, z, unit="Um"):
    return NS(coordinates=[x, y, z], unit=unit)


def test_mass_properties_from_320_element():
    raw = NS(mass_properties=NS(
        moulded_dry_weight=_qty(1200.0, "UKg"),
        physical_dry_weight=_qty(1250.0, "UKg"),
        moulded_center_of_gravity=_cog(1.0, 2.0, 3.0),
        physical_center_of_gravity=_cog(1.1, 2.1, 3.1),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 1200.0
    assert mp.physical_dry_weight.value == 1250.0
    assert mp.moulded_cog.x == 1.0
    assert mp.physical_cog.z == 3.1


def test_mass_properties_falls_back_to_physical_properties():
    raw = NS(physical_properties=NS(
        dry_weight=_qty(300.0, "UKg"),
        center_of_gravity=_cog(5.0, 6.0, 7.0),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 300.0
    assert mp.moulded_cog.y == 6.0
    assert mp.physical_dry_weight is None
    assert mp.physical_cog is None


def test_mass_properties_absent_returns_none():
    assert _b()._mass_properties(NS()) is None


def test_build_plate_populates_mass_properties():
    raw = NS(id="PL1", name="p", guidref=None, plate_material=None,
             net_area=None, function_type=None, outer_contour=None,
             mass_properties=NS(
                 moulded_dry_weight=_qty(42.0, "UKg"),
                 physical_dry_weight=None,
                 moulded_center_of_gravity=None,
                 physical_center_of_gravity=None))
    plate = _b()._build_plate(raw, PARENT)
    assert plate.mass_properties.moulded_dry_weight.value == 42.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: FAIL — `AttributeError: 'OcxV3Builder' object has no attribute '_mass_properties'`

- [ ] **Step 3: Implement — IR fields (additive)**

In `ocx_model_validator/model/ir/structural.py`:
1. Add `IrMassProperties,` to the `from ocx_model_validator.model.ir.base import (...)` block.
2. Add this field to each of `IrPlate`, `IrBracket`, `IrStiffener`, `IrPillar`, `IrEdgeReinforcement`, `IrMember`, `IrPanel`, directly after the existing `cog: IrCog | None = None` line (keep `dry_weight`/`cog` — removed in Task 3):

```python
    mass_properties: IrMassProperties | None = None
```

- [ ] **Step 4: Implement — builder helper**

In `ocx_model_validator/builders/v3_builder.py`:
1. Add `IrMassProperties,` to the big `from ocx_model_validator.model.ir import (...)` block, in alphabetical position (after `IrLSectionOvershootWeb`, before `IrMaterial`).
2. Refactor `_cog` by adding a point-level helper. Insert directly **above** the existing `_cog` method:

```python
    @staticmethod
    def _cog_point(cog_raw) -> IrCog | None:
        """Extract an IrCog from a CoG-style element (coordinates + unit)."""
        if cog_raw is None:
            return None
        coords = getattr(cog_raw, "coordinates", None)
        unit = getattr(cog_raw, "unit", None)
        if not coords or len(coords) < 3:
            return None
        try:
            return IrCog(
                x=float(coords[0]),
                y=float(coords[1]),
                z=float(coords[2]),
                unit=str(unit) if unit else "",
            )
        except (TypeError, ValueError):
            return None
```

3. Replace the body of the existing `_cog` method with:

```python
    @staticmethod
    def _cog(physical_properties) -> IrCog | None:
        """Extract centre of gravity from a legacy PhysicalPropertiesT."""
        if physical_properties is None:
            return None
        return OcxV3Builder._cog_point(
            getattr(physical_properties, "center_of_gravity", None))
```

4. Insert a new classmethod directly after `_cog`:

```python
    @classmethod
    def _mass_properties(cls, raw) -> IrMassProperties | None:
        """Extract IrMassProperties: 3.2.0 MassProperties first, legacy
        3.0/3.1 PhysicalProperties fallback (mapped onto moulded fields)."""
        mp = getattr(raw, "mass_properties", None)
        if mp is not None:
            return IrMassProperties(
                moulded_dry_weight=cls._qty(getattr(mp, "moulded_dry_weight", None)),
                physical_dry_weight=cls._qty(getattr(mp, "physical_dry_weight", None)),
                moulded_cog=cls._cog_point(getattr(mp, "moulded_center_of_gravity", None)),
                physical_cog=cls._cog_point(getattr(mp, "physical_center_of_gravity", None)),
            )
        pp = getattr(raw, "physical_properties", None)
        if pp is None:
            return None
        dw = cls._qty(getattr(pp, "dry_weight", None))
        cog = cls._cog(pp)
        if dw is None and cog is None:
            return None
        return IrMassProperties(moulded_dry_weight=dw, moulded_cog=cog)
```

5. In each of `_build_plate`, `_build_bracket`, `_build_stiffener`, `_build_pillar`, `_build_edge_reinforcement`, and `_build_panel`, add this kwarg to the IR constructor call, directly after the `cog=self._cog(pp),` line:

```python
            mass_properties=self._mass_properties(raw),
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_builder_320_gap.py tests/test_builders.py -v`
Expected: PASS

- [ ] **Step 6: Full suite + commit**

Run: `uv run pytest -q` — expected green.

```bash
git add ocx_model_validator/model/ir/structural.py ocx_model_validator/builders/v3_builder.py tests/test_builder_320_gap.py
git commit -m "feat(builder): extract MassProperties with PhysicalProperties fallback"
```

---

### Task 3: Migrate consumers, remove `dry_weight`/`cog` from parts

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py` (remove old fields from 7 classes)
- Modify: `ocx_model_validator/builders/v3_builder.py` (remove old kwargs)
- Modify: `ocx_model_validator/reporting/generators/bom.py`
- Modify: `ocx_model_validator/reporting/generators/_compartment_data.py`
- Modify: `tests/test_builders.py`, `tests/test_reporting_bom.py`, `tests/test_ir_structural_additions.py`

Note: `IrCompartment.cog` is **not** part of this migration — compartments keep their `cog` field (OCX CompartmentProperties is unchanged).

- [ ] **Step 1: Migrate report generators**

In `ocx_model_validator/reporting/generators/bom.py`, replace `_weight_tonnes` with:

```python
def _weight_tonnes(part, vessel: IrVessel, notes: list[str]) -> float | None:
    mp = part.mass_properties
    dw = mp.moulded_dry_weight if mp is not None else None
    if dw is None:
        return None
    try:
        return to_si(dw, vessel.unit_registry) / 1000.0
    except GeometryError:
        notes.append(f"{part.id} dry_weight: unknown unit "
                     f"{dw.unit!r}; excluded from totals")
        return None
```

Also update the module docstring line `Items without dry_weight show N/A` to `Items without a moulded dry weight show N/A`.

In `ocx_model_validator/reporting/generators/_compartment_data.py`, inside `_panel_cog_points_mm`, replace the plate loop body:

```python
        for plate_id in panel.plate_ids:
            plate = vessel.plates.get(plate_id)
            cog = (plate.mass_properties.moulded_cog
                   if plate is not None and plate.mass_properties is not None
                   else None)
            if cog is None:
                continue
            try:
                points.append(point_mm(cog, vessel.unit_registry))  # type: ignore[arg-type]
            except GeometryError as exc:
                warnings.append(f"compartment {name}: plate {plate.name or plate.id}: {exc}")
```

- [ ] **Step 2: Migrate tests**

In `tests/test_reporting_bom.py`: every IR part constructed with `dry_weight=Quantity(X, U)` becomes `mass_properties=IrMassProperties(moulded_dry_weight=Quantity(X, U))`. Add `IrMassProperties` to the imports from `ocx_model_validator.model.ir`. (8 construction sites — lines ~23, 27, 34, 38, 41, 73, 86, 98.)

In `tests/test_builders.py`, `test_build_pillar_extracts_dry_weight` — keep the raw stub unchanged (it exercises the legacy fallback) and change the assertions to:

```python
    assert p.mass_properties.moulded_dry_weight.value == 300.0
    assert p.mass_properties.moulded_dry_weight.unit == "UKg"
```

In `tests/test_ir_structural_additions.py`, replace `test_member_uses_cog_and_external_geometry` with:

```python
def test_member_uses_mass_properties_and_external_geometry():
    parent = ParentRef(kind=ParentKind.VESSEL, id="v1")
    m = IrMember(id="m1", parent_ref=parent)
    assert m.parent_ref is parent
    assert m.mass_properties is None and m.external_geometry_ref is None
    m2 = IrMember(
        id="m2",
        parent_ref=parent,
        mass_properties=IrMassProperties(moulded_cog=IrCog(1.0, 2.0, 3.0, "Um")),
    )
    assert isinstance(m2.mass_properties.moulded_cog, IrCog)
```

Add `IrMassProperties` to that file's imports.

- [ ] **Step 3: Remove old fields**

In `ocx_model_validator/model/ir/structural.py`, delete the lines `dry_weight: Quantity | None = None` and `cog: IrCog | None = None` from `IrPlate`, `IrBracket`, `IrStiffener`, `IrPillar`, `IrEdgeReinforcement`, `IrMember`, and `IrPanel` (7 classes; `IrMember` has no `cog`-adjacent docstring issue — also update its docstring from "physical-properties + external geometry ref" to "mass properties + external geometry ref").

In `ocx_model_validator/builders/v3_builder.py`, in `_build_plate`, `_build_bracket`, `_build_stiffener`, `_build_pillar`, `_build_edge_reinforcement`, `_build_panel`: delete the `dry_weight=self._qty(...)` and `cog=self._cog(pp),` kwargs **and** the now-unused `pp = getattr(raw, "physical_properties", None)` lines.

- [ ] **Step 4: Full suite**

Run: `uv run pytest -q`
Expected: green. If any other test fails on a removed field, migrate it the same way (`dry_weight=` → `mass_properties=IrMassProperties(moulded_dry_weight=...)`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(ir)!: replace part dry_weight/cog with mass_properties"
```

---

### Task 4: Materials — Steel/Aluminium catalogue

**Files:**
- Modify: `ocx_model_validator/model/ir/catalogues.py`
- Modify: `ocx_model_validator/builders/v3_builder.py` (`_build_materials`)
- Test: `tests/test_builder_320_gap.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_builder_320_gap.py`:

```python
def _material_root(**mc_kwargs):
    defaults = {"material": [], "steel": [], "aluminium": []}
    defaults.update(mc_kwargs)
    return NS(class_catalogue=NS(material_catalogue=NS(**defaults)))


def test_build_materials_steel_and_aluminium_320():
    from ocx_model_validator.model.ir import IrVessel
    steel = NS(id="M1", name="NV A36", guidref=None, grade=NS(value="A36"),
               density=_qty(7850.0, "Ukgoverm3"),
               yield_stress=_qty(355.0, "UNOvermm2"),
               ultimate_stress=_qty(490.0, "UNOvermm2"),
               youngs_modulus=_qty(206000.0, "UNOvermm2"),
               poisson_ratio=_qty(0.3, "Unitless"),
               thermal_expansion_coefficient=None)
    alu = NS(id="M2", name="AW-5083", guidref=None,
             density=_qty(2660.0, "Ukgoverm3"),
             unwelded_yield_strength=_qty(125.0, "UNOvermm2"),
             welded_yield_strength=_qty(115.0, "UNOvermm2"),
             unwelded_tensile_strength=_qty(275.0, "UNOvermm2"),
             welded_tensile_strength=_qty(270.0, "UNOvermm2"),
             alloy_designation="5083",
             youngs_modulus=None, poisson_ratio=None,
             thermal_expansion_coefficient=None)
    root = _material_root(steel=[steel], aluminium=[alu])
    ir = IrVessel(id="v1")
    _b()._build_materials(root, ir)
    m1, m2 = ir.materials["M1"], ir.materials["M2"]
    assert m1.material_type == "steel"
    assert m1.grade == "A36" and m1.yield_stress.value == 355.0
    assert m2.material_type == "aluminium"
    assert m2.unwelded_yield_strength.value == 125.0
    assert m2.welded_tensile_strength.value == 270.0
    assert m2.alloy_designation == "5083"


def test_build_materials_legacy_material_fallback():
    from ocx_model_validator.model.ir import IrVessel
    legacy = NS(id="M9", name="steel", guidref=None, grade=None,
                density=_qty(7850.0, "Ukgoverm3"),
                yield_stress=_qty(235.0, "UNOvermm2"),
                ultimate_stress=None, youngs_modulus=None,
                poisson_ratio=None, thermal_expansion=None)
    root = _material_root(material=[legacy])
    ir = IrVessel(id="v1")
    _b()._build_materials(root, ir)
    m = ir.materials["M9"]
    assert m.material_type is None
    assert m.yield_stress.value == 235.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: FAIL — `TypeError`/`AttributeError` on `material_type`.

- [ ] **Step 3: Implement IR fields**

In `ocx_model_validator/model/ir/catalogues.py`, replace `IrMaterial` with:

```python
@dataclass
class IrMaterial:
    """Schema-neutral material record.

    ``material_type`` is ``"steel"`` / ``"aluminium"`` for OCX 3.2.0
    catalogues and ``None`` for legacy 3.0/3.1 ``Material`` entries.
    The welded/unwelded strength fields and ``alloy_designation`` are
    aluminium-specific (3.2.0); ``grade``/``yield_stress``/``ultimate_stress``
    are steel/legacy fields.
    """
    id: str
    name: str | None = None
    guidref: str | None = None
    material_type: str | None = None  # "steel" | "aluminium" | None
    grade: str | None = None
    density: Quantity | None = None
    yield_stress: Quantity | None = None
    ultimate_stress: Quantity | None = None
    youngs_modulus: Quantity | None = None
    poisson_ratio: Quantity | None = None
    thermal_expansion: Quantity | None = None
    unwelded_yield_strength: Quantity | None = None
    welded_yield_strength: Quantity | None = None
    unwelded_tensile_strength: Quantity | None = None
    welded_tensile_strength: Quantity | None = None
    alloy_designation: str | None = None
```

- [ ] **Step 4: Implement builder**

In `ocx_model_validator/builders/v3_builder.py`, replace `_build_materials` with:

```python
    def _build_materials(self, root, ir: IrVessel) -> None:
        cc = getattr(root, "class_catalogue", None)
        if cc is None:
            return
        mc = getattr(cc, "material_catalogue", None)
        if mc is None:
            return

        def _common(m, mid, material_type):
            return IrMaterial(
                id=mid,
                name=getattr(m, "name", None),
                guidref=getattr(m, "guidref", None),
                material_type=material_type,
                density=self._qty(getattr(m, "density", None)),
                youngs_modulus=self._qty(getattr(m, "youngs_modulus", None)),
                poisson_ratio=self._qty(getattr(m, "poisson_ratio", None)),
                thermal_expansion=self._qty(
                    getattr(m, "thermal_expansion", None)
                    or getattr(m, "thermal_expansion_coefficient", None)),
            )

        # --- 3.2.0: typed steel / aluminium lists ---
        for m in getattr(mc, "steel", None) or []:
            mid = getattr(m, "id", None) or getattr(m, "guidref", None)
            if not mid:
                continue
            ir_mat = _common(m, mid, "steel")
            ir_mat.grade = self._enum(getattr(m, "grade", None))
            ir_mat.yield_stress = self._qty(getattr(m, "yield_stress", None))
            ir_mat.ultimate_stress = self._qty(getattr(m, "ultimate_stress", None))
            self._register(ir.materials, mid, ir_mat, ir.duplicate_ids)
        for m in getattr(mc, "aluminium", None) or []:
            mid = getattr(m, "id", None) or getattr(m, "guidref", None)
            if not mid:
                continue
            ir_mat = _common(m, mid, "aluminium")
            ir_mat.unwelded_yield_strength = self._qty(getattr(m, "unwelded_yield_strength", None))
            ir_mat.welded_yield_strength = self._qty(getattr(m, "welded_yield_strength", None))
            ir_mat.unwelded_tensile_strength = self._qty(getattr(m, "unwelded_tensile_strength", None))
            ir_mat.welded_tensile_strength = self._qty(getattr(m, "welded_tensile_strength", None))
            ir_mat.alloy_designation = getattr(m, "alloy_designation", None)
            self._register(ir.materials, mid, ir_mat, ir.duplicate_ids)

        # --- 3.0/3.1 fallback: untyped Material list ---
        for m in getattr(mc, "material", None) or []:
            mid = getattr(m, "id", None) or getattr(m, "guidref", None)
            if not mid:
                continue
            ir_mat = _common(m, mid, None)
            ir_mat.grade = self._enum(getattr(m, "grade", None))
            ir_mat.yield_stress = self._qty(getattr(m, "yield_stress", None))
            ir_mat.ultimate_stress = self._qty(getattr(m, "ultimate_stress", None))
            self._register(ir.materials, mid, ir_mat, ir.duplicate_ids)
```

- [ ] **Step 5: Run tests, full suite, commit**

Run: `uv run pytest tests/test_builder_320_gap.py -v` then `uv run pytest -q` — expected green.

```bash
git add ocx_model_validator/model/ir/catalogues.py ocx_model_validator/builders/v3_builder.py tests/test_builder_320_gap.py
git commit -m "feat(materials): extract 3.2.0 Steel/Aluminium catalogues with legacy fallback"
```

---

### Task 5: Scantlings — renewal thicknesses, voluntary additions, section tweaks

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py`
- Modify: `ocx_model_validator/model/ir/sections.py`
- Modify: `ocx_model_validator/builders/v3_builder.py`
- Test: `tests/test_builder_320_gap.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_builder_320_gap.py`:

```python
def test_plate_material_renewal_thickness():
    raw = NS(id="PL2", name=None, guidref=None,
             plate_material=NS(local_ref="M1", guidref=None,
                               thickness=_qty(12.0, "Umm"),
                               renewal_thickness=_qty(10.5, "Umm"),
                               voluntary_thickness_addition=_qty(1.0, "Umm")),
             net_area=None, function_type=None, outer_contour=None)
    plate = _b()._build_plate(raw, PARENT)
    assert plate.thickness.value == 12.0
    assert plate.renewal_thickness.value == 10.5
    assert plate.voluntary_thickness_addition.value == 1.0


def test_stiffener_section_ref_scantlings():
    raw = NS(id="ST2", name=None, guidref=None, material_ref=None,
             function_type=None, end_cut_end1=None, end_cut_end2=None,
             trace_line=None, inclination=None,
             section_ref=NS(local_ref="SEC1", guidref=None,
                            web_renewal_thickness=_qty(6.0, "Umm"),
                            flange_renewal_thickness=_qty(7.0, "Umm"),
                            voluntary_web_thickness_addition=_qty(0.5, "Umm"),
                            voluntary_flange_thickness_addition=_qty(0.7, "Umm")))
    st = _b()._build_stiffener(raw, PARENT)
    assert st.section_ref.local_ref == "SEC1"
    assert st.web_renewal_thickness.value == 6.0
    assert st.flange_renewal_thickness.value == 7.0
    assert st.voluntary_web_thickness_addition.value == 0.5
    assert st.voluntary_flange_thickness_addition.value == 0.7


def test_round_bar_height_fallback():
    class RoundBar(NS):
        pass
    sec = RoundBar(id="S_RB", name=None, guidref=None,
                   height=_qty(30.0, "Umm"))
    ir_sec = _b()._build_section(sec)
    assert ir_sec.diameter.value == 30.0


def test_bar_section_catalogue_reference():
    class FlatBar(NS):
        pass
    class BarSection(NS):
        pass
    bar = BarSection(id="S_FB", name="FB100", guidref=None,
                     catalogue_reference="EN10058-FB100x10",
                     flat_bar=FlatBar(height=_qty(100.0, "Umm"),
                                      width=_qty(10.0, "Umm")))
    ir_sec = _b()._build_section(bar)
    assert ir_sec.catalogue_reference == "EN10058-FB100x10"
    assert ir_sec.height.value == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: FAIL on the four new tests.

- [ ] **Step 3: Implement IR fields**

`ocx_model_validator/model/ir/structural.py`:
- `IrPlate` and `IrBracket`: after `thickness: Quantity | None = None` add:

```python
    renewal_thickness: Quantity | None = None
    voluntary_thickness_addition: Quantity | None = None
```

- `IrStiffener`, `IrPillar`, `IrEdgeReinforcement`: after `section_ref: Ref | None = None` add:

```python
    web_renewal_thickness: Quantity | None = None
    flange_renewal_thickness: Quantity | None = None
    voluntary_web_thickness_addition: Quantity | None = None
    voluntary_flange_thickness_addition: Quantity | None = None
```

`ocx_model_validator/model/ir/sections.py` — in `IrSection` base, after `section_type`:

```python
    catalogue_reference: str | None = None  # BarSection catalogueReference (3.2.0)
```

- [ ] **Step 4: Implement builder**

In `ocx_model_validator/builders/v3_builder.py`:

1. Add a static helper after `_material_ref`:

```python
    @staticmethod
    def _section_scantlings(section_ref_obj) -> dict[str, Quantity | None]:
        """Extract 3.2.0 renewal/voluntary-addition quantities from a SectionRef."""
        q = OcxV3Builder._qty
        s = section_ref_obj
        return {
            "web_renewal_thickness": q(getattr(s, "web_renewal_thickness", None)) if s else None,
            "flange_renewal_thickness": q(getattr(s, "flange_renewal_thickness", None)) if s else None,
            "voluntary_web_thickness_addition": q(getattr(s, "voluntary_web_thickness_addition", None)) if s else None,
            "voluntary_flange_thickness_addition": q(getattr(s, "voluntary_flange_thickness_addition", None)) if s else None,
        }
```

2. In `_build_plate` and `_build_bracket`, after the `thickness=thickness,` kwarg add:

```python
            renewal_thickness=self._qty(getattr(pm, "renewal_thickness", None) if pm else None),
            voluntary_thickness_addition=self._qty(getattr(pm, "voluntary_thickness_addition", None) if pm else None),
```

3. In `_build_stiffener`, `_build_pillar`, `_build_edge_reinforcement`, capture the raw section ref once at the top (`raw_sec = getattr(raw, "section_ref", None)`), pass `section_ref=self._ref(raw_sec),` and add:

```python
            **self._section_scantlings(raw_sec),
```

4. In `_build_section`, the `RoundBar` branch becomes:

```python
        if stype == "RoundBar":
            return IrRoundSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                diameter=self._qty(getattr(data, "diameter", None)
                                   or getattr(data, "height", None)),
            )
```

5. In `_build_section`, extract `catalogue_reference` near the top (after `guid = ...`):

```python
        catalogue_reference = getattr(raw_section, "catalogue_reference", None)
```

and add `catalogue_reference=catalogue_reference,` to **every** `return Ir...Section(...)` call in `_build_section` (all 17 typed branches plus the final `IrGenericSection` return).

- [ ] **Step 5: Run tests, full suite, commit**

Run: `uv run pytest tests/test_builder_320_gap.py -q` then `uv run pytest -q` — expected green.

```bash
git add ocx_model_validator/model/ir/structural.py ocx_model_validator/model/ir/sections.py ocx_model_validator/builders/v3_builder.py tests/test_builder_320_gap.py
git commit -m "feat(scantlings): renewal thicknesses, voluntary additions, section catalogue refs"
```

---

### Task 6: Geometry — `Plane3D.point_on_surface`, surface normals

**Files:**
- Modify: `ocx_model_validator/model/ir/geometry.py`
- Modify: `ocx_model_validator/builders/v3_builder.py` (`_build_surface`)
- Modify: `tests/test_builder_extensions.py` (plane test keeps 3.1 stub; add fallback assert)
- Test: `tests/test_builder_320_gap.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_builder_320_gap.py`:

```python
def _pt3(x, y, z, unit="Um"):
    return NS(coordinates=[x, y, z], unit=unit)


def _dir3(x, y, z):
    return NS(direction=[x, y, z])


def test_plane3d_point_on_surface_320():
    class Plane3D(NS):
        pass
    p = Plane3D(id="P1", point_on_surface=_pt3(4.5, -5.7, 1.5),
                normal=_dir3(1.0, 0.0, 0.0), udirection=None)
    ir = _b()._build_surface(p)
    assert ir.point_on_surface.x == 4.5
    assert ir.normal.x == 1.0


def test_plane3d_origin_fallback_310():
    class Plane3D(NS):
        pass
    p = Plane3D(id="P2", origin=_pt3(0.0, 1.0, 2.0),
                normal=_dir3(0.0, 0.0, 1.0), udirection=None)
    ir = _b()._build_surface(p)
    assert ir.point_on_surface.y == 1.0


def test_surfaces_extract_normal_and_point_on_surface():
    class Cylinder3D(NS):
        pass
    c = Cylinder3D(id="C1", origin=_pt3(0, 0, 0), axis=_dir3(0, 0, 1),
                   radius=_qty(2.0, "Um"), height=_qty(10.0, "Um"),
                   normal=_dir3(1.0, 0.0, 0.0),
                   point_on_surface=_pt3(2.0, 0.0, 5.0))
    ir = _b()._build_surface(c)
    assert ir.normal.x == 1.0
    assert ir.point_on_surface.z == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: FAIL — `IrPlane3D` has no `point_on_surface`.

- [ ] **Step 3: Implement IR**

In `ocx_model_validator/model/ir/geometry.py`, replace the surface classes:

```python
@dataclass(frozen=True)
class IrPlane3D(IrSurface3D):
    point_on_surface: IrPoint3D | None = None  # 3.2.0 PointOnSurface / 3.1.0 Origin
    normal: IrVector3D | None = None
    udirection: IrVector3D | None = None


@dataclass(frozen=True)
class IrSphere3D(IrSurface3D):
    origin: IrPoint3D | None = None
    radius: Quantity | None = None
    normal: IrVector3D | None = None
    point_on_surface: IrPoint3D | None = None


@dataclass(frozen=True)
class IrCone3D(IrSurface3D):
    origin: IrPoint3D | None = None
    tip: IrPoint3D | None = None
    base_radius: Quantity | None = None
    tip_radius: Quantity | None = None
    normal: IrVector3D | None = None
    point_on_surface: IrPoint3D | None = None


@dataclass(frozen=True)
class IrCylinder3D(IrSurface3D):
    origin: IrPoint3D | None = None
    axis: IrVector3D | None = None
    radius: Quantity | None = None
    height: Quantity | None = None
    normal: IrVector3D | None = None
    point_on_surface: IrPoint3D | None = None


@dataclass(frozen=True)
class IrExtrudedSurface(IrSurface3D):
    base_curve: IrCurve3D | None = None
    sweep: IrVector3D | None = None
    sweep_curve: IrCurve3D | None = None
    face_boundary_curve: IrCurve3D | None = None
    normal: IrVector3D | None = None
    point_on_surface: IrPoint3D | None = None


@dataclass(frozen=True)
class IrNurbsSurface(IrSurface3D):
    u_degree: int | None = None
    v_degree: int | None = None
    u_knot_vector: list[float] = field(default_factory=list)
    v_knot_vector: list[float] = field(default_factory=list)
    control_points: list[list[IrPoint3D]] = field(default_factory=list)
    normal: IrVector3D | None = None
    point_on_surface: IrPoint3D | None = None
```

- [ ] **Step 4: Implement builder**

In `_build_surface` in `v3_builder.py`:

```python
    def _build_surface(self, elem):
        """Dispatch a raw OCX surface element to its IR surface type."""
        if elem is None:
            return None
        name = type(elem).__name__.lower()
        sid = getattr(elem, "id", None)
        # 3.2.0 PointOnSurface with 3.1.0 Origin fallback (Plane3D renamed it);
        # normal is new on most surfaces in 3.2.0.
        pos = self._pt(getattr(elem, "point_on_surface", None))
        normal = self._vec(getattr(elem, "normal", None))
        if "plane" in name:
            return IrPlane3D(id=sid,
                             point_on_surface=pos or self._pt(getattr(elem, "origin", None)),
                             normal=normal,
                             udirection=self._vec(getattr(elem, "udirection", None)))
        if "sphere" in name:
            return IrSphere3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                              radius=self._qty(getattr(elem, "radius", None)),
                              normal=normal, point_on_surface=pos)
        if "cone" in name:
            return IrCone3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                            tip=self._pt(getattr(elem, "tip", None)),
                            base_radius=self._qty(getattr(elem, "base_radius", None)),
                            tip_radius=self._qty(getattr(elem, "tip_radius", None)),
                            normal=normal, point_on_surface=pos)
        if "cylinder" in name:
            return IrCylinder3D(id=sid, origin=self._pt(getattr(elem, "origin", None)),
                                axis=self._vec(getattr(elem, "axis", None)),
                                radius=self._qty(getattr(elem, "radius", None)),
                                height=self._qty(getattr(elem, "height", None)),
                                normal=normal, point_on_surface=pos)
        if "extruded" in name:
            return IrExtrudedSurface(
                id=sid,
                base_curve=self._build_curve(getattr(elem, "base_curve", None)),
                sweep=self._vec(getattr(elem, "sweep", None)),
                sweep_curve=self._build_curve(getattr(elem, "sweep_curve", None)),
                face_boundary_curve=self._build_curve(getattr(elem, "face_boundary_curve", None)),
                normal=normal, point_on_surface=pos)
        if "nurbssurface" in name or "nurbs" in name:
            return IrNurbsSurface(id=sid, normal=normal, point_on_surface=pos)
        logger.debug("Unknown surface type: {}", type(elem).__name__)
        return None
```

- [ ] **Step 5: Fix affected existing tests**

Run: `uv run pytest -q 2>&1 | Select-Object -Last 30` and check for failures referencing `IrPlane3D(origin=...)` or `.origin` on plane objects. Known candidates:
- `tests/test_builder_extensions.py::test_build_plane_udirection` — keeps its 3.1 stub (`origin=` kw on the raw stub). Add an assertion `assert ir.point_on_surface.x == 0.0`.
- Any test constructing `IrPlane3D(origin=...)` directly must switch the kwarg to `point_on_surface=`.

- [ ] **Step 6: Full suite + commit**

Run: `uv run pytest -q` — expected green.

```bash
git add -A
git commit -m "feat(geometry): Plane3D point_on_surface rename; normals on 3.2.0 surfaces"
```

---

### Task 7: Refs & structure — unbounded, occurrence, trace refs, limited-by, contours, holes, parts misc

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py` (`IrPlate`, `IrPanel`, `IrStiffener`, `IrEdgeReinforcement`, `IrSeam`, `IrLimitedByRef`)
- Modify: `ocx_model_validator/model/ir/connections.py`
- Modify: `ocx_model_validator/builders/v3_builder.py`
- Test: `tests/test_builder_320_gap.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_builder_320_gap.py`:

```python
def test_ref_extracts_offset_and_direction():
    raw = NS(local_ref="X1", guidref="g-1",
             offset=_qty(50.0, "Umm"), offset_direction=_dir3(0.0, 1.0, 0.0))
    ref = _b()._ref(raw)
    assert ref.offset.value == 50.0
    assert ref.offset_direction.y == 1.0


def test_unbounded_geometry_320_ref_names():
    ug = NS(plane3_d=None, nurbssurface=None, extruded_surface=None,
            sphere3_d=None, cone3_d=None, cylinder3_d=None,
            unbounded_grid_ref=[NS(local_ref="GR1", guidref=None)],
            unbounded_surface_ref=[NS(local_ref="SR1", guidref=None)])
    ir_ug = _b()._build_unbounded(ug)
    assert ir_ug.grid_ref == "GR1"
    assert ir_ug.surface_ref == "SR1"


def test_occurrence_320_str_refs_and_lists():
    occ = NS(id="O1", name="occ", type_value=None,
             plate_ref=[NS(local_ref="PL1", guidref=None)],
             str_stiffener_ref=[NS(local_ref="ST1", guidref=None)],
             str_seam_ref=[NS(local_ref="SM1", guidref=None)],
             str_edge_reinforcement_ref=[NS(local_ref="ER1", guidref=None)],
             bracket_ref=[], pillar_ref=[], hole_contour_ref=[],
             lug_plate_ref=[], connected_bracket_ref=[])
    ir_occ = _b()._build_occurrence(occ)
    assert ir_occ.plate_ref.local_ref == "PL1"
    assert ir_occ.stiffener_ref.local_ref == "ST1"
    assert ir_occ.seam_ref.local_ref == "SM1"
    assert ir_occ.edge_reinforcement_ref.local_ref == "ER1"


def test_stiffener_trace_refs_and_orientation_rule():
    tl = NS(composite_curve3_d=None, edge_curve_ref=None,
            stiffener_ref=None, panel_ref=NS(local_ref="PN1", guidref=None),
            seam_ref=None, surface_ref=None, grid_ref=None,
            edge_reinforcement_ref=None)
    raw = NS(id="ST3", name=None, guidref=None, material_ref=None,
             section_ref=None, function_type=None, end_cut_end1=None,
             end_cut_end2=None, inclination=None, trace_line=tl,
             orientation_rule=NS(value="PERPENDICULAR"))
    st = _b()._build_stiffener(raw, PARENT)
    assert st.orientation_rule == "PERPENDICULAR"
    assert st.trace_refs[0].local_ref == "PN1"


def test_plate_point_on_surface_and_outer_contour_list():
    contour = NS(line3_d=[NS(curve_length=None, id=None,
                             start_point=_pt3(0, 0, 0),
                             end_point=_pt3(1, 0, 0))],
                 composite_curve3_d=None, nurbs3_d=None, poly_line3_d=None,
                 circum_arc3_d=None, ellipse3_d=None, circle3_d=None,
                 circum_circle3_d=None)
    raw = NS(id="PL3", name=None, guidref=None, plate_material=None,
             net_area=None, function_type=None,
             outer_contour=[contour],
             point_on_surface=_pt3(0.5, 0.0, 0.0))
    plate = _b()._build_plate(raw, PARENT)
    assert plate.point_on_surface.x == 0.5
    assert plate.outer_contour is not None


def test_plate_cut_by_inner_contour():
    hole = NS(line3_d=[NS(curve_length=None, id=None,
                          start_point=_pt3(0, 0, 0),
                          end_point=_pt3(0, 1, 0))],
              composite_curve3_d=None, nurbs3_d=None, poly_line3_d=None,
              circum_arc3_d=None, ellipse3_d=None, circle3_d=None,
              circum_circle3_d=None)
    raw = NS(id="PL4", name=None, guidref=None, plate_material=None,
             net_area=None, function_type=None, outer_contour=None,
             plate_cut_by=NS(inner_contour=[hole], outer_contour=None,
                             hole2_dcontour=[], slot_contour=[]))
    plate = _b()._build_plate(raw, PARENT)
    assert len(plate.cut_by_contours) == 1


def test_limited_by_offset_and_contour_mid_point():
    from ocx_model_validator.model.ir import IrVessel
    lb_ref = NS(local_ref="PN9", guidref=None, ref_type="ocx:PanelRef",
                offset=_qty(10.0, "Umm"),
                offset_direction=_dir3(0.0, 0.0, 1.0),
                contour_bounds=NS(contour_start=None, contour_end=None,
                                  contour_mid_point=_pt3(1.0, 2.0, 3.0)))
    raw = NS(id="PN10", name=None, guidref=None, function_type=None,
             tightness=None, composed_of=None, stiffened_by=None,
             split_by=None, unbounded_geometry=None,
             limited_by=NS(panel_ref=[lb_ref], stiffener_ref=[],
                           seam_ref=[], surface_ref=[], edge_curve_ref=[],
                           grid_ref=[], edge_reinforcement_ref=[],
                           free_edge_curve3_d=[]))
    ir = IrVessel(id="v1")
    panel = _b()._build_panel(raw, ir, "v1")
    r = panel.limited_by[0]
    assert r.offset.value == 10.0
    assert r.offset_direction.z == 1.0
    assert r.contour_mid_point.y == 2.0


def test_hole2d_ellipse_parametric_variant():
    from ocx_model_validator.model.ir import IrVessel
    hole = NS(id="H1", name=None, guidref=None, contour=None,
              ellipse=NS(major_diameter=_qty(100.0, "Umm"),
                         minor_diameter=_qty(50.0, "Umm")),
              rectangular_mickey_mouse_ears=None, rectangular_hole=None,
              super_elliptical=None, symmetrical_hole=None,
              parametric_circle=None)
    cat = NS(id="HC1", name=None, hole2_d=[hole])
    ir = IrVessel(id="v1")
    _b()._build_hole_catalogue(cat, ir)
    assert ir.hole_shape_catalogue.holes["H1"].parametric == {"variant": "ellipse"}


def test_penetration_bracket_ref_field():
    from ocx_model_validator.model.ir import IrPenetration
    p = IrPenetration(id="PEN1", bracket_ref=Ref(local_ref="BR1"))
    assert p.bracket_ref.local_ref == "BR1"
```

Also extend the module imports at the top of `tests/test_builder_320_gap.py` to include `Ref`:

```python
from ocx_model_validator.model.ir import ParentKind, ParentRef, Ref
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement IR fields**

`ocx_model_validator/model/ir/structural.py`:
- `IrPlate`: add

```python
    point_on_surface: IrPoint3D | None = None
    cut_by_contours: list[IrCurve3D] = field(default_factory=list)
```

- `IrPanel`: add `point_on_surface: IrPoint3D | None = None` after `tightness`.
- `IrStiffener`: add `orientation_rule: str | None = None` and `trace_refs: list[Ref] = field(default_factory=list)`.
- `IrEdgeReinforcement`: add `orientation_rule: str | None = None` and `trace_refs: list[Ref] = field(default_factory=list)`.
- `IrSeam`: add `trace_refs: list[Ref] = field(default_factory=list)`.
- `IrLimitedByRef`: add

```python
    offset: Quantity | None = None
    offset_direction: IrVector3D | None = None
    contour_mid_point: IrPoint3D | None = None
```

(structural.py already imports `IrPoint3D`, `IrVector3D`, `IrCurve3D`, `Quantity`, `Ref`, `field`.)

`ocx_model_validator/model/ir/connections.py` — replace content:

```python
"""Connection IR types.

These are intentionally minimal.  The full connection-configuration model is
deferred to a future design.  ``structural.py`` imports ``IrPenetration`` from
here; this module must NOT import from ``structural.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.model.ir.base import Ref


@dataclass
class IrConnectionConfiguration:
    """Minimal connection configuration (full definition in a future design)."""
    id: str
    name: str | None = None
    bracket_ref: Ref | None = None  # OCX 3.2.0 BracketRef


@dataclass
class IrPenetration(IrConnectionConfiguration):
    """Stiffener penetration — subtype of IrConnectionConfiguration."""
    pass
```

- [ ] **Step 4: Implement builder**

In `ocx_model_validator/builders/v3_builder.py`:

1. Replace `_ref`:

```python
    @staticmethod
    def _ref(obj) -> Ref | None:
        """Safely build a Ref from an OCX *Ref dataclass (incl. 3.2.0 offsets)."""
        if obj is None:
            return None
        local = getattr(obj, "local_ref", None) or ""
        guid = getattr(obj, "guidref", None)
        return Ref(
            local_ref=local,
            guidref=guid,
            offset=OcxV3Builder._qty(getattr(obj, "offset", None)),
            offset_direction=OcxV3Builder._vec(getattr(obj, "offset_direction", None)),
        )
```

Note: `_vec` is a `@staticmethod` on the class, so reference it as `OcxV3Builder._vec` inside the static `_ref`. Also note `_ref` is defined before `_vec` in the file — Python resolves at call time, so order is fine.

2. Add a first-element unwrap helper next to `_children` (module level):

```python
def _first(value: Any) -> Any:
    """Return the first element of a list/tuple, or the value itself."""
    if isinstance(value, list | tuple):
        return value[0] if value else None
    return value
```

3. In `_build_unbounded`, replace the grid/surface ref extraction:

```python
        grid = _first(getattr(ug, "unbounded_grid_ref", None)) or getattr(ug, "grid_ref", None)
        sref = _first(getattr(ug, "unbounded_surface_ref", None)) or getattr(ug, "surface_ref", None)
```

(keep the rest of the method — the `IrUnboundedGeometry(...)` construction — unchanged).

4. Replace `_build_occurrence` and its attr table:

```python
    # (3.2.0 attr, 3.1.0 fallback attr, IrOccurrence field)
    _OCC_REF_ATTRS = (
        ("plate_ref", None, "plate_ref"),
        ("str_stiffener_ref", "stiffener_ref", "stiffener_ref"),
        ("str_seam_ref", "seam_ref", "seam_ref"),
        ("bracket_ref", None, "bracket_ref"),
        ("pillar_ref", None, "pillar_ref"),
        ("hole_contour_ref", None, "hole_contour_ref"),
        ("str_edge_reinforcement_ref", "edge_reinforcement_ref", "edge_reinforcement_ref"),
        ("lug_plate_ref", None, "lug_plate_ref"),
        ("connected_bracket_ref", None, "connected_bracket_ref"),
    )

    def _build_occurrence(self, occ) -> IrOccurrence:
        kwargs = {}
        for new_attr, old_attr, field_name in self._OCC_REF_ATTRS:
            raw = _first(getattr(occ, new_attr, None))
            if raw is None and old_attr:
                raw = _first(getattr(occ, old_attr, None))
            kwargs[field_name] = self._ref(raw)
        return IrOccurrence(id=getattr(occ, "id", None) or "",
                            name=getattr(occ, "name", None),
                            type_value=getattr(occ, "type_value", None), **kwargs)
```

5. Add a trace-ref helper after `_build_contour`:

```python
    _TRACE_REF_ATTRS = ("edge_curve_ref", "edge_reinforcement_ref", "grid_ref",
                        "panel_ref", "seam_ref", "stiffener_ref", "surface_ref")

    def _trace_refs(self, trace_line) -> list[Ref]:
        """Extract 3.2.0 TraceLine child refs (empty for 3.0/3.1 models)."""
        refs: list[Ref] = []
        if trace_line is None:
            return refs
        for attr in self._TRACE_REF_ATTRS:
            r = self._ref(_first(getattr(trace_line, attr, None)))
            if r is not None and (r.local_ref or r.guidref):
                refs.append(r)
        return refs
```

6. Make `_build_contour` accept list containers (3.2.0 `outer_contour` is a list). Replace its first lines:

```python
    def _build_contour(self, container):
        """Build one IR curve from a TraceLine/OuterContour container.

        3.2.0 wraps some contours in lists (e.g. Plate.outer_contour) —
        accept both a single container and a list of containers.
        """
        if container is None:
            return None
        if isinstance(container, (list, tuple)):
            container = container[0] if container else None
            if container is None:
                return None
        curves = []
        ...  # rest unchanged
```

7. In `_build_plate`, add kwargs (after `outer_contour=...`):

```python
            point_on_surface=self._pt(getattr(raw, "point_on_surface", None)),
            cut_by_contours=self._cut_by_contours(getattr(raw, "plate_cut_by", None)),
```

and add the helper after `_trace_refs`:

```python
    def _cut_by_contours(self, pcb) -> list:
        """Extract cut-out contours from PlateCutBy (3.2.0 inner_contour,
        3.1.0 outer_contour)."""
        if pcb is None:
            return []
        contours = []
        raw_list = (getattr(pcb, "inner_contour", None)
                    or getattr(pcb, "outer_contour", None) or [])
        for c in _children(raw_list):
            built = self._build_contour(c)
            if built is not None:
                contours.append(built)
        return contours
```

8. In `_build_stiffener`, add kwargs:

```python
            orientation_rule=self._enum(getattr(raw, "orientation_rule", None)),
            trace_refs=self._trace_refs(getattr(raw, "trace_line", None)),
```

In `_build_edge_reinforcement`, add:

```python
            orientation_rule=self._enum(getattr(raw, "orientation_rule", None)),
            trace_refs=self._trace_refs(_first(getattr(raw, "trace_line", None))),
```

(EdgeReinforcement's `trace_line` is a list in 3.2.0.)

9. In `_build_seams_for_panel`, extend the `IrSeam(...)` construction:

```python
            self._register(ir.seams, sid, IrSeam(
                id=sid, name=getattr(seam, "name", None),
                guidref=getattr(seam, "guidref", None), trace_line=curve,
                trace_refs=self._trace_refs(tl)), ir.duplicate_ids)
```

10. In `_build_panel`:
- Add `point_on_surface=self._pt(getattr(raw, "point_on_surface", None)),` to the `IrPanel(...)` constructor (after `tightness=`).
- In the `_LB_ATTRS` loop, extend the `IrLimitedByRef(...)` construction:

```python
                    limited_by_refs.append(
                        IrLimitedByRef(
                            ref_type=ref_type,
                            local_ref=local,
                            guidref=guid,
                            ocx_ref_type=ocx_rt,
                            offset=self._qty(getattr(ref_raw, "offset", None)),
                            offset_direction=self._vec(getattr(ref_raw, "offset_direction", None)),
                            contour_mid_point=self._pt(
                                getattr(getattr(ref_raw, "contour_bounds", None),
                                        "contour_mid_point", None)),
                        )
                    )
```

11. In `_build_hole_catalogue`, extend the parametric variant tuple:

```python
            for attr in ("ellipse", "rectangular_mickey_mouse_ears",
                         "rectangular_hole", "super_elliptical",
                         "symmetrical_hole", "parametric_circle"):
```

- [ ] **Step 5: Run tests, full suite, commit**

Run: `uv run pytest tests/test_builder_320_gap.py -q` then `uv run pytest -q` — expected green. (The old `_OCC_REF_ATTRS` single-name behaviour is replaced; `tests/test_builder_extensions.py` occurrence tests use 3.1.0 names which now flow through the fallback path — if one constructs e.g. `stiffener_ref=NS(...)` as a scalar it still works via `_first`.)

```bash
git add -A
git commit -m "feat(builder): 3.2.0 refs, occurrences, trace refs, cut-by and hole variants"
```

---

### Task 8: Metadata & cargo additions

**Files:**
- Modify: `ocx_model_validator/model/ir/metadata.py` (`IrPrincipalParticulars`)
- Modify: `ocx_model_validator/model/ir/arrangement.py` (`IrBulkCargo`)
- Modify: `ocx_model_validator/builders/v3_builder.py` (`_build_metadata`, `_build_cargoes_for_compartment`)
- Test: `tests/test_builder_320_gap.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_builder_320_gap.py`:

```python
def test_principal_particulars_minimum_ballast_draught():
    from ocx_model_validator.model.ir import IrVessel
    pp = NS(lpp=None, rule_length=None, block_coefficient=None,
            moulded_breadth=None, moulded_depth=None, scantling_draught=None,
            design_speed=None, freeboard_length=None,
            normal_ballast_draught=None, heavy_ballast_draught=None,
            minimum_ballast_draught=_qty(5.2, "Um"),
            length_of_waterline=None, upper_deck_area=None,
            freeboard_type=None)
    vessel_raw = NS(ship_designation=None, tonnage_data=None,
                    statutory_data=None, builder_information=None,
                    classification_data=NS(society_name="DNV",
                                           principal_particulars=pp))
    ir = IrVessel(id="v1")
    _b()._build_metadata(vessel_raw, ir)
    assert ir.principal_particulars.minimum_ballast_draught.value == 5.2


def test_bulk_cargo_density():
    from ocx_model_validator.model.ir import IrVessel
    comp = NS(id="C1", guidref=None,
              liquid_cargo=None, gaseous_cargo=None, unit_cargo=None,
              bulk_cargo=NS(bulk_cargo_type=None,
                            density=_qty(1600.0, "Ukgoverm3"),
                            stowage_factor=None, permeability=None,
                            angle_of_repose=None))
    ir = IrVessel(id="v1")
    _b()._build_cargoes_for_compartment(comp, ir)
    assert ir.bulk_cargoes["C1/bulk/0"].density.value == 1600.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builder_320_gap.py -v`
Expected: the two new tests FAIL (`unexpected keyword` / `None`).

- [ ] **Step 3: Implement**

`metadata.py` — in `IrPrincipalParticulars`, after `heavy_ballast_draught`:

```python
    minimum_ballast_draught: Quantity | None = None
```

`arrangement.py` — in `IrBulkCargo`, after `cargo_type`:

```python
    density: Quantity | None = None
```

`v3_builder.py`:
- In `_build_metadata`, inside the `IrPrincipalParticulars(...)` call, after `heavy_ballast_draught=...` add:

```python
                minimum_ballast_draught=self._qty(getattr(pp, "minimum_ballast_draught", None)),
```

- In `_build_cargoes_for_compartment`, in the `IrBulkCargo(...)` call, after `cargo_type=...` add:

```python
                density=self._qty(getattr(bc, "density", None)),
```

- [ ] **Step 4: Run tests, full suite, commit**

Run: `uv run pytest tests/test_builder_320_gap.py -q` then `uv run pytest -q` — expected green.

```bash
git add ocx_model_validator/model/ir/metadata.py ocx_model_validator/model/ir/arrangement.py ocx_model_validator/builders/v3_builder.py tests/test_builder_320_gap.py
git commit -m "feat(ir): minimum ballast draught and bulk cargo density"
```

---

### Task 9: Regenerate stubs from models/ (incl. TR05 3.2.0) + integration verification

**Files:**
- Regenerate: `tests/data/ocx_320_stubs/` (and other stub dirs — `--force` wipes all)
- No code changes expected; fix any failures per conventions.

- [ ] **Step 1: Regenerate stubs**

Run: `uv run validator generate-stubs --force`
Expected: exit 0; `tests/data/ocx_320_stubs/` repopulated (≥170 files, now sourced from TR05 vendors too). Check: `git status --short tests/data | Select-Object -First 20`.

- [ ] **Step 2: Full suite over regenerated stubs**

Run: `uv run pytest -q`
Expected: green. Stub-driven parametrized tests now exercise 3.0.0, 3.1.0, and 3.2.0 content. If a test fails on regenerated stub content, inspect whether the stub changed shape (new source model) and fix the *test's tolerance* (fields asserted only when present), not the stub.

- [ ] **Step 3: Integration check on a real TR05 model**

Run this one-off verification (not committed):

```powershell
@'
from ocx_model_validator.parsers.parser import OcxParser
from ocx_model_validator.builders.factory import get_builder

root = OcxParser().parse("models/TR05/tr05_tc04a_mbrh.3docx")
ir = get_builder(root.schema_version).build(root)
assert ir.schema_version == "3.2.0", ir.schema_version
assert ir.materials, "materials empty"
typed = [m for m in ir.materials.values() if m.material_type]
assert typed, "no typed steel/aluminium materials"
with_mass = [p for p in ir.plates.values() if p.mass_properties]
print(f"OK: {len(ir.materials)} materials ({len(typed)} typed), "
      f"{len(ir.plates)} plates ({len(with_mass)} with mass_properties), "
      f"{len(ir.panels)} panels")
'@ | uv run python -
```

Expected: prints `OK: ...` with non-zero typed materials. (If `OcxParser().parse` has a different entry signature, check `ocx_model_validator/parsers/parser.py` and use the conftest `_build_session` pattern instead.) Note: plates carrying `MassProperties` depends on the exporter — if `with_mass` is 0 for this file, verify against `models/TR05/tr05_tc04a_cadhu.3docx` before concluding a bug.

- [ ] **Step 4: Report smoke test**

Run: `uv run validator report all models/TR05/tr05_tc04a_mbrh.3docx --destination tmp-tr05-report.md`
Expected: exit 0, report written. Then delete it: `Remove-Item tmp-tr05-report.md`.

- [ ] **Step 5: Commit stubs**

```bash
git add tests/data
git commit -m "test: regenerate schema stubs including OCX 3.2.0 TR05 sources"
```

---

### Task 10: Documentation updates

**Files:**
- Modify: `.github/copilot-instructions.md`
- Modify: `ocx_model_validator.md` (only if it references materials/physical properties — check first)

- [ ] **Step 1: Update copilot-instructions**

In `.github/copilot-instructions.md` line ~104, replace `` `PhysicalProperties` `` with `` `MassProperties` `` in the wrapper-element list, and append this bullet to the "Builder conventions" section:

```markdown
- OCX 3.2.0 renamed/restructured several elements (`PhysicalProperties`→`MassProperties`, `Material`→`Steel`/`Aluminium`, `Origin`→`PointOnSurface` on `Plane3D`, `Occurrence` `str_*Ref` names, `UnboundedGridRef`/`UnboundedSurfaceRef`). The builder always reads the 3.2.0 name first and falls back to the 3.1.0 name; the IR follows 3.2.0 shapes (`IrMassProperties`, `IrMaterial.material_type`, `IrPlane3D.point_on_surface`).
```

- [ ] **Step 2: Check and update ocx_model_validator.md**

Run: `uv run python -c "print(open('ocx_model_validator.md', encoding='utf-8').read())" | Select-String -Pattern "physical_properties|PhysicalProperties|dry_weight|Material" -SimpleMatch:$false`
Update any matches the same way (mass_properties / Steel+Aluminium). If no matches, skip.

- [ ] **Step 3: Final full suite + commit**

Run: `uv run pytest -q` — expected green.

```bash
git add .github/copilot-instructions.md ocx_model_validator.md
git commit -m "docs: document OCX 3.2.0 IR shapes and builder fallback conventions"
```

---

## Success criteria (from spec)

1. `uv run pytest` green with `ocx_310_stubs` and regenerated `ocx_320_stubs` discovered.
2. `models/TR05/tr05_tc04a_mbrh.3docx` builds with non-empty typed `materials` and populated `mass_properties` (Task 9 Step 3).
3. 3.1.0 stubs still yield weight/CoG via `mass_properties.moulded_*` (legacy fallback tests, Tasks 2–3).
4. `validator report all` succeeds on a TR05 model (Task 9 Step 4).
