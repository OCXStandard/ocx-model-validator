# IR Model Extension (Dataclass Layer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `ocx_model_validator/model/ir.py` into a `model/ir/` package and add the full set of IR dataclasses (geometry, structural additions, arrangement, catalogues, metadata, connection placeholders) that cover OCX schema 3.1.0 global elements — pure-Python types with unit tests. Builder extraction is **out of scope** for this plan (deferred to a separate spec/plan).

**Architecture:** Convert the monolithic `ir.py` into a backward-compatible package whose `__init__.py` re-exports every public type, so all existing `from ocx_model_validator.model.ir import X` imports keep working. New types are added module-by-module (`base`, `sections`, `structural`, `arrangement`, `catalogues`, `geometry`, `metadata`, `connections`). Each new type is constructed and tested directly in pure Python — no OCX stubs needed.

**Tech Stack:** Python 3 dataclasses (`frozen=True` where specified), `uv` for environment/test running, `pytest`, `loguru` (existing). Spec: `docs/superpowers/specs/2026-06-10-ir-model-extension-design.md`.

---

## File Structure

Target package layout (created incrementally across tasks):

```
ocx_model_validator/model/ir/
├── __init__.py       ← re-exports every public type (backward-compatible)
├── base.py           ← IrCog, Quantity, IrUnit, Ref, ParentKind, ParentRef
├── catalogues.py     ← IrMaterial, IrHole2D, IrHoleShapeCatalogue
├── sections.py       ← IrSection + all typed section subclasses (moved as-is)
├── geometry.py       ← IrPoint3D, IrVector3D, IrCurve3D + subclasses,
│                        IrSurface3D + subclasses, IrCoordinateSystem,
│                        IrRefPlane, IrSurface, IrSurfaceCollection
├── connections.py    ← IrConnectionConfiguration, IrPenetration (placeholders)
├── structural.py     ← IrPlate, IrBracket, IrStiffener, IrPillar,
│                        IrEdgeReinforcement, IrLimitedByRef, IrSeam, IrMember,
│                        IrEndCut, IrFeatureCope, IrPanel, IrVessel
├── arrangement.py    ← IrCompartment, IrPhysicalSpace, IrLiquidCargo,
│                        IrGaseousCargo, IrBulkCargo, IrUnitCargo,
│                        IrDesignView, IrOccurrenceGroup, IrOccurrence
└── metadata.py       ← IrShipDesignation, IrTonnageData, IrPrincipalParticulars,
                         IrStatutoryData, IrBuilderInformation
```

**Module dependency order (no cycles):**
`base` → `catalogues`/`sections`/`geometry` → `connections` → `structural` (imports `connections`, `geometry`) → `arrangement`/`metadata` → `__init__`.

**Key constraint:** `connections.py` MUST NOT import from `structural.py` (structural imports `IrPenetration` from connections — one direction only).

---

## Notes on `tests/test_ir_builder.py::MISSING_IR_CLASSES`

`tests/test_ir_builder.py` contains a list `MISSING_IR_CLASSES` and a parametrized test `TestMissingIrClasses::test_ir_class_not_yet_implemented` that asserts each named `Ir<Name>` does **not** exist on the `ocx_model_validator.model.ir` package. **As each new type is added and re-exported, the matching entry MUST be removed from `MISSING_IR_CLASSES` in the same commit**, or that test will fail. Each task below lists exactly which entries to remove.

---

## Task 1: Split `ir.py` into a backward-compatible `model/ir/` package

Mechanical move only — no behavior change. All existing classes keep identical definitions; only their physical location changes. `__init__.py` re-exports them so every existing import path keeps working.

**Files:**
- Delete: `ocx_model_validator/model/ir.py` (content distributed below)
- Create: `ocx_model_validator/model/ir/__init__.py`
- Create: `ocx_model_validator/model/ir/base.py`
- Create: `ocx_model_validator/model/ir/catalogues.py`
- Create: `ocx_model_validator/model/ir/sections.py`
- Create: `ocx_model_validator/model/ir/structural.py`
- Create: `ocx_model_validator/model/ir/arrangement.py`
- Test: existing suite (`tests/`) is the regression check.

- [ ] **Step 1: Run the full suite to capture the green baseline**

Run: `uv run pytest -q`
Expected: PASS (record the count, e.g. "N passed"). This is the baseline the split must preserve.

- [ ] **Step 2: Create `base.py` with the shared primitive types**

Move these classes **verbatim** from the current `ir.py` (lines ~30–107): `IrCog`, `Quantity`, `IrUnit`, `Ref`, `ParentKind`, `ParentRef`.

File header for `ocx_model_validator/model/ir/base.py`:

```python
"""Shared primitive / value types for the schema-neutral IR."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
```

Then paste the six classes unchanged. (`Quantity`, `IrCog`, `IrUnit`, `Ref`, `ParentRef` are `@dataclass(frozen=True)`; `ParentKind` is a `str, Enum`.)

- [ ] **Step 3: Create `catalogues.py` with `IrMaterial`**

Move `IrMaterial` (current `ir.py` lines ~114–130) verbatim.

```python
"""Catalogue IR types — materials and (later) hole shapes."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity
```

Then paste the `IrMaterial` class unchanged. `IrMaterial` itself only needs `dataclass` and `Quantity`; `field` is imported here because Task 5 extends this module with `IrHoleShapeCatalogue` (which uses `field(default_factory=dict)`).

- [ ] **Step 4: Create `sections.py` with `IrSection` and all subclasses**

Move `IrSection` and every `Ir*Section*` subclass (current `ir.py` lines ~134–279) verbatim: `IrSection`, `IrRectangularTubeSection`, `IrOctagonSection`, `IrSquareSection`, `IrBulbFlatSection`, `IrFlatBarSection`, `IrUSection`, `IrISection`, `IrLSectionOvershootFlange`, `IrZSection`, `IrRoundSection`, `IrLSection`, `IrTSection`, `IrLSectionOvershootWeb`, `IrHalfRoundSection`, `IrHexagonSection`, `IrAngleSection`, `IrTubeSection`, `IrGenericSection`.

```python
"""Section catalogue IR types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocx_model_validator.model.ir.base import Quantity
```

Paste the classes unchanged. (`IrBulbFlatSection` uses `Optional[Quantity]`; `IrGenericSection` uses `dict[str, Any]` and `field(default_factory=dict)` — hence the `typing` and `field` imports.)

- [ ] **Step 5: Create `arrangement.py` with `IrCompartment` and `IrPhysicalSpace`**

Move `IrCompartment` and `IrPhysicalSpace` (current `ir.py` lines ~472–490) verbatim.

```python
"""Arrangement IR types — compartments, spaces (cargoes/design-view added later)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity, Ref
```

Paste the two classes unchanged.

- [ ] **Step 6: Create `structural.py` with the structural parts, panel, and vessel**

Move verbatim (current `ir.py` lines ~282–605): `IrPlate`, `IrBracket`, `IrStiffener`, `IrPillar`, `IrEdgeReinforcement`, `IrLimitedByRef`, `IrPanel`, `IrVessel` (including all its `get_*` / `*_for_panel` helper methods).

```python
"""Structural IR types and the IrVessel root."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocx_model_validator.model.ir.base import (
    IrCog,
    ParentKind,
    ParentRef,
    Quantity,
    Ref,
)
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrSection
from ocx_model_validator.model.ir.arrangement import IrCompartment, IrPhysicalSpace
```

Paste the structural classes and `IrVessel` unchanged. `IrVessel`'s field annotations that reference `IrMaterial`, `IrSection`, `IrCompartment`, `IrPhysicalSpace` now resolve via the imports above.

- [ ] **Step 7: Create `__init__.py` re-exporting the full current public surface**

```python
"""Schema-neutral Intermediate Representation (IR) dataclasses for OCX models.

This package was split from the former monolithic ``ir.py``.  Every public
type is re-exported here so that ``from ocx_model_validator.model.ir import X``
continues to work unchanged.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import (
    IrCog,
    IrUnit,
    ParentKind,
    ParentRef,
    Quantity,
    Ref,
)
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import (
    IrAngleSection,
    IrBulbFlatSection,
    IrFlatBarSection,
    IrGenericSection,
    IrHalfRoundSection,
    IrHexagonSection,
    IrISection,
    IrLSection,
    IrLSectionOvershootFlange,
    IrLSectionOvershootWeb,
    IrOctagonSection,
    IrRectangularTubeSection,
    IrRoundSection,
    IrSection,
    IrSquareSection,
    IrTSection,
    IrTubeSection,
    IrUSection,
    IrZSection,
)
from ocx_model_validator.model.ir.arrangement import (
    IrCompartment,
    IrPhysicalSpace,
)
from ocx_model_validator.model.ir.structural import (
    IrBracket,
    IrEdgeReinforcement,
    IrLimitedByRef,
    IrPanel,
    IrPillar,
    IrPlate,
    IrStiffener,
    IrVessel,
)

__all__ = [
    # base
    "IrCog", "Quantity", "IrUnit", "Ref", "ParentKind", "ParentRef",
    # catalogues
    "IrMaterial",
    # sections
    "IrSection", "IrRectangularTubeSection", "IrOctagonSection",
    "IrSquareSection", "IrBulbFlatSection", "IrFlatBarSection", "IrUSection",
    "IrISection", "IrLSectionOvershootFlange", "IrZSection", "IrRoundSection",
    "IrLSection", "IrTSection", "IrLSectionOvershootWeb", "IrHalfRoundSection",
    "IrHexagonSection", "IrAngleSection", "IrTubeSection", "IrGenericSection",
    # structural
    "IrPlate", "IrBracket", "IrStiffener", "IrPillar", "IrEdgeReinforcement",
    "IrLimitedByRef", "IrPanel", "IrVessel",
    # arrangement
    "IrCompartment", "IrPhysicalSpace",
]
```

- [ ] **Step 8: Delete the old `ir.py`**

Run: `Remove-Item C:\PythonDev\ocx-model-validator\ocx_model_validator\model\ir.py`
Expected: file removed. (The package directory now shadows it.)

- [ ] **Step 9: Run the full suite — must match the baseline exactly**

Run: `uv run pytest -q`
Expected: PASS with the same count as Step 1. If any import error appears (e.g. `ImportError: cannot import name 'IrX'`), a class was missed in a submodule or `__init__.py` — fix the missing re-export/move.

- [ ] **Step 10: Commit**

```bash
git add ocx_model_validator/model/ir/ ocx_model_validator/model/ir.py
git commit -m "refactor: split model/ir.py into backward-compatible model/ir/ package

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Add `geometry.py` — points, vectors, curves, surfaces, reference geometry

**Files:**
- Create: `ocx_model_validator/model/ir/geometry.py`
- Modify: `ocx_model_validator/model/ir/__init__.py` (add re-exports)
- Modify: `tests/test_ir_builder.py` (remove implemented entries from `MISSING_IR_CLASSES`)
- Test: `tests/test_ir_geometry.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_geometry.py`:

```python
"""Unit tests for geometry IR dataclasses."""
from __future__ import annotations

import pytest

from ocx_model_validator.model.ir import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCone3D,
    IrCoordinateSystem,
    IrCurve3D,
    IrCylinder3D,
    IrEllipse3D,
    IrExtrudedSurface,
    IrLine3D,
    IrNurbs3D,
    IrNurbsSurface,
    IrPlane3D,
    IrPoint3D,
    IrPolyLine3D,
    IrRefPlane,
    IrSphere3D,
    IrSurface,
    IrSurface3D,
    IrSurfaceCollection,
    IrVector3D,
    Quantity,
)


def test_point3d_holds_coordinates_and_unit():
    p = IrPoint3D(x=1.0, y=2.0, z=3.0, unit="Umm")
    assert (p.x, p.y, p.z, p.unit) == (1.0, 2.0, 3.0, "Umm")


def test_vector3d_is_dimensionless():
    v = IrVector3D(x=0.0, y=0.0, z=1.0)
    assert (v.x, v.y, v.z) == (0.0, 0.0, 1.0)


def test_curve_length_is_required_positional():
    with pytest.raises(TypeError):
        IrLine3D()  # curve_length has no default


def test_line3d_construction():
    a = IrPoint3D(0.0, 0.0, 0.0, "Um")
    b = IrPoint3D(1.0, 0.0, 0.0, "Um")
    line = IrLine3D(curve_length=Quantity(1.0, "Um"), start=a, end=b)
    assert isinstance(line, IrCurve3D)
    assert line.curve_length == Quantity(1.0, "Um")
    assert line.start is a and line.end is b
    assert line.id is None


def test_circle3d_defaults():
    c = IrCircle3D(curve_length=None)
    assert c.center is None and c.radius is None and c.normal is None


def test_polyline_and_composite_default_to_empty_lists():
    pl = IrPolyLine3D(curve_length=None)
    cc = IrCompositeCurve3D(curve_length=None)
    assert pl.vertices == [] and cc.segments == []
    assert pl.vertices is not IrPolyLine3D(curve_length=None).vertices  # no shared default


def test_circumarc_ellipse_nurbs_curves_construct():
    assert IrCircumArc3D(curve_length=None).middle is None
    assert IrEllipse3D(curve_length=None).major_axis is None
    n = IrNurbs3D(curve_length=None, degree=2)
    assert n.degree == 2 and n.knot_vector == [] and n.control_points == []


def test_surface_subclasses_construct():
    assert isinstance(IrPlane3D(), IrSurface3D)
    assert IrPlane3D().id is None
    assert IrSphere3D().radius is None
    assert IrCone3D().half_angle is None
    assert IrCylinder3D().axis is None
    assert IrExtrudedSurface().base_curve is None
    assert IrNurbsSurface().control_points == []


def test_reference_geometry_construct():
    cs = IrCoordinateSystem(id="cs1")
    assert cs.name is None and cs.origin is None
    rp = IrRefPlane(id="rp1")
    assert rp.reference_plane is None
    surf = IrSurface(id="s1")
    assert surf.geometry is None and surf.guidref is None
    coll = IrSurfaceCollection(id="sc1")
    assert coll.surfaces == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_geometry.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrPoint3D'` (geometry module not created yet).

- [ ] **Step 3: Create `geometry.py`**

`ocx_model_validator/model/ir/geometry.py`:

```python
"""Geometry IR types — points, vectors, curves, surfaces, reference frames.

All geometry types are ``frozen=True`` dataclasses.  ``IrCurve3D.curve_length``
is a required positional field (no default) so builders cannot forget it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity


# --- primitive value types ---

@dataclass(frozen=True)
class IrPoint3D:
    """A 3D point in model coordinates."""
    x: float
    y: float
    z: float
    unit: str  # OCX unit id, e.g. 'Um', 'Umm'


@dataclass(frozen=True)
class IrVector3D:
    """A dimensionless 3D direction vector."""
    x: float
    y: float
    z: float


# --- curve hierarchy ---

@dataclass(frozen=True)
class IrCurve3D:
    """Abstract base for all 3D curve types.

    ``curve_length`` has no default — builders MUST pass it (``None`` if the
    length is absent in the model).
    """
    curve_length: Quantity | None  # required positional field
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


# --- surface hierarchy ---

@dataclass(frozen=True)
class IrSurface3D:
    """Abstract base for all 3D surface types."""
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


# --- standalone reference geometry ---

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

- [ ] **Step 4: Re-export the geometry types from `__init__.py`**

Add this import block to `ocx_model_validator/model/ir/__init__.py` (after the `sections` import block):

```python
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCone3D,
    IrCoordinateSystem,
    IrCurve3D,
    IrCylinder3D,
    IrEllipse3D,
    IrExtrudedSurface,
    IrLine3D,
    IrNurbs3D,
    IrNurbsSurface,
    IrPlane3D,
    IrPoint3D,
    IrPolyLine3D,
    IrRefPlane,
    IrSphere3D,
    IrSurface,
    IrSurface3D,
    IrSurfaceCollection,
    IrVector3D,
)
```

And add to `__all__` (insert a `# geometry` group):

```python
    # geometry
    "IrPoint3D", "IrVector3D", "IrCurve3D", "IrLine3D", "IrCircumArc3D",
    "IrCircle3D", "IrPolyLine3D", "IrCompositeCurve3D", "IrEllipse3D",
    "IrNurbs3D", "IrSurface3D", "IrPlane3D", "IrSphere3D", "IrCone3D",
    "IrCylinder3D", "IrExtrudedSurface", "IrNurbsSurface",
    "IrCoordinateSystem", "IrRefPlane", "IrSurface", "IrSurfaceCollection",
```

- [ ] **Step 5: Remove implemented entries from `MISSING_IR_CLASSES`**

In `tests/test_ir_builder.py`, delete these tuples from the `MISSING_IR_CLASSES` list (they now exist):
`("Point3D", ...)`, `("Cone3D", ...)`, `("Cylinder3D", ...)`, `("Ellipse3D", ...)`, `("Sphere3D", ...)`, `("PolyLine3D", ...)`, `("CoordinateSystem", ...)`, `("RefPlane", ...)`.

Leave `Positions`, `CircumCircle3D`, `XRefPlanes`, `YRefPlanes`, `ZRefPlanes` in place (no matching IR class created).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_geometry.py tests/test_ir_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add ocx_model_validator/model/ir/geometry.py ocx_model_validator/model/ir/__init__.py tests/test_ir_geometry.py tests/test_ir_builder.py
git commit -m "feat: add geometry IR dataclasses (points, curves, surfaces, reference frames)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Add `connections.py` — placeholder connection types

Created before structural additions because `structural.py` imports `IrPenetration` from here. This module MUST NOT import from `structural.py`.

**Files:**
- Create: `ocx_model_validator/model/ir/connections.py`
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Modify: `tests/test_ir_builder.py` (remove `ConnectionConfiguration`, `Penetration`)
- Test: `tests/test_ir_connections.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_connections.py`:

```python
"""Unit tests for connection placeholder IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrConnectionConfiguration,
    IrPenetration,
)


def test_connection_configuration_minimal():
    c = IrConnectionConfiguration(id="cc1")
    assert c.id == "cc1" and c.name is None


def test_penetration_is_connection_configuration_subtype():
    p = IrPenetration(id="p1", name="hole")
    assert isinstance(p, IrConnectionConfiguration)
    assert p.id == "p1" and p.name == "hole"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_connections.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrConnectionConfiguration'`.

- [ ] **Step 3: Create `connections.py`**

`ocx_model_validator/model/ir/connections.py`:

```python
"""Connection IR types.

These are intentionally minimal placeholders.  The full connection-
configuration model is deferred to a future design.  ``structural.py`` imports
``IrPenetration`` from here; this module must NOT import from ``structural.py``.
"""
from __future__ import annotations

from dataclasses import dataclass


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

- [ ] **Step 4: Re-export from `__init__.py`**

Add to `ocx_model_validator/model/ir/__init__.py`:

```python
from ocx_model_validator.model.ir.connections import (
    IrConnectionConfiguration,
    IrPenetration,
)
```

And to `__all__`:

```python
    # connections
    "IrConnectionConfiguration", "IrPenetration",
```

- [ ] **Step 5: Remove implemented entries from `MISSING_IR_CLASSES`**

In `tests/test_ir_builder.py`, delete `("ConnectionConfiguration", ...)` and `("Penetration", ...)`. Leave `WebStiffener`, `WebStiffenerWithSingleBracket`, `SlotParameters` in place.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_connections.py tests/test_ir_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/model/ir/connections.py ocx_model_validator/model/ir/__init__.py tests/test_ir_connections.py tests/test_ir_builder.py
git commit -m "feat: add placeholder connection IR dataclasses (ConnectionConfiguration, Penetration)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Extend `structural.py` — new types and new fields on `IrStiffener`/`IrPanel`

Adds `IrSeam`, `IrMember`, `IrEndCut`, `IrFeatureCope`, and new (nullable, defaulted) fields on `IrStiffener` and `IrPanel`. All additions are nullable/defaulted so no existing constructor call breaks.

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py`
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Modify: `tests/test_ir_builder.py` (remove `Seam`, `FeatureCope`)
- Test: `tests/test_ir_structural_additions.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_structural_additions.py`:

```python
"""Unit tests for new structural IR types and field additions."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrEndCut,
    IrFeatureCope,
    IrMember,
    IrPanel,
    IrPenetration,
    IrPoint3D,
    IrSeam,
    IrStiffener,
    ParentKind,
    ParentRef,
    Quantity,
)


def test_seam_defaults_and_plate_refs():
    s = IrSeam(id="seam1")
    assert s.name is None
    assert s.plate_refs == []
    assert s.cog is None and s.function_type is None


def test_member_uses_point3d_for_cog():
    parent = ParentRef(kind=ParentKind.VESSEL, id="v1")
    m = IrMember(id="m1", parent_ref=parent)
    assert m.parent_ref is parent
    assert m.start_point is None and m.end_point is None
    m2 = IrMember(
        id="m2",
        parent_ref=parent,
        cog=IrPoint3D(1.0, 2.0, 3.0, "Um"),
    )
    assert isinstance(m2.cog, IrPoint3D)


def test_end_cut_defaults():
    e = IrEndCut()
    assert e.sniped is False
    assert e.cope_height is None
    e2 = IrEndCut(sniped=True, cope_height=Quantity(50.0, "Umm"))
    assert e2.sniped is True and e2.cope_height == Quantity(50.0, "Umm")


def test_feature_cope_defaults():
    fc = IrFeatureCope(id="fc1")
    assert fc.cope_radius is None and fc.name is None


def test_stiffener_new_fields_default_empty():
    parent = ParentRef(kind=ParentKind.PANEL, id="p1")
    st = IrStiffener(id="st1", parent_ref=parent)
    assert st.end_cut_start is None and st.end_cut_end is None
    assert st.penetrations == []
    st2 = IrStiffener(
        id="st2",
        parent_ref=parent,
        end_cut_start=IrEndCut(sniped=True),
        penetrations=[IrPenetration(id="pen1")],
    )
    assert st2.end_cut_start.sniped is True
    assert st2.penetrations[0].id == "pen1"


def test_panel_new_ref_lists_default_empty():
    p = IrPanel(id="panel1")
    assert p.seam_ids == []
    assert p.member_ids == []
    assert p.hole_shape_refs == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_structural_additions.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrSeam'`.

- [ ] **Step 3: Add the new imports to `structural.py`**

In `ocx_model_validator/model/ir/structural.py`, extend the import section near the top to add `IrPoint3D` and `IrPenetration`:

```python
from ocx_model_validator.model.ir.geometry import IrPoint3D
from ocx_model_validator.model.ir.connections import IrPenetration
```

- [ ] **Step 4: Add the four new structural dataclasses**

Insert into `structural.py` (after `IrEdgeReinforcement`, before `IrLimitedByRef`):

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
    cog: IrPoint3D | None = None  # 3D point, not IrCog
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

- [ ] **Step 5: Add new fields to `IrStiffener`**

In the `IrStiffener` dataclass, append these fields after `function_type`:

```python
    end_cut_start: IrEndCut | None = None
    end_cut_end: IrEndCut | None = None
    penetrations: list[IrPenetration] = field(default_factory=list)
```

- [ ] **Step 6: Add new fields to `IrPanel`**

In the `IrPanel` dataclass, after the existing `edge_reinforcement_ids` line and before `limited_by`, add:

```python
    seam_ids: list[str] = field(default_factory=list)
    member_ids: list[str] = field(default_factory=list)
    hole_shape_refs: list[Ref] = field(default_factory=list)
```

(Order among defaulted fields does not matter for correctness; keep `limited_by` after these for readability.)

- [ ] **Step 7: Re-export the new structural types from `__init__.py`**

Update the `structural` import block in `ocx_model_validator/model/ir/__init__.py` to include the new names:

```python
from ocx_model_validator.model.ir.structural import (
    IrBracket,
    IrEdgeReinforcement,
    IrEndCut,
    IrFeatureCope,
    IrLimitedByRef,
    IrMember,
    IrPanel,
    IrPillar,
    IrPlate,
    IrSeam,
    IrStiffener,
    IrVessel,
)
```

And add the new names to the `# structural` group in `__all__`:

```python
    "IrSeam", "IrMember", "IrEndCut", "IrFeatureCope",
```

- [ ] **Step 8: Remove implemented entries from `MISSING_IR_CLASSES`**

In `tests/test_ir_builder.py`, delete `("Seam", ...)` and `("FeatureCope", ...)`.

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_structural_additions.py tests/test_ir_builder.py -q`
Expected: PASS.

- [ ] **Step 10: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add ocx_model_validator/model/ir/structural.py ocx_model_validator/model/ir/__init__.py tests/test_ir_structural_additions.py tests/test_ir_builder.py
git commit -m "feat: add IrSeam, IrMember, IrEndCut, IrFeatureCope and stiffener/panel fields

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Extend `catalogues.py` — hole shapes

Adds `IrHole2D` and `IrHoleShapeCatalogue`. Hole shapes are catalogue definitions; panels reference them via `hole_shape_refs` (added in Task 4).

**Files:**
- Modify: `ocx_model_validator/model/ir/catalogues.py`
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Test: `tests/test_ir_catalogues.py` (new)

(No `MISSING_IR_CLASSES` change — `Hole2D` is not an entry; `HoleContourRef` and `InnerContour` remain unimplemented.)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_catalogues.py`:

```python
"""Unit tests for hole-shape catalogue IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrCircle3D,
    IrHole2D,
    IrHoleShapeCatalogue,
    Quantity,
)


def test_hole2d_defaults():
    h = IrHole2D(id="h1")
    assert h.name is None and h.guidref is None and h.contour is None


def test_hole2d_holds_contour_curve():
    contour = IrCircle3D(curve_length=Quantity(1.0, "Um"))
    h = IrHole2D(id="h2", contour=contour)
    assert h.contour is contour


def test_hole_shape_catalogue_defaults_and_population():
    cat = IrHoleShapeCatalogue(id="cat1")
    assert cat.name is None and cat.holes == {}
    cat.holes["h1"] = IrHole2D(id="h1")
    assert cat.holes["h1"].id == "h1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_catalogues.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrHole2D'`.

- [ ] **Step 3: Add the hole types to `catalogues.py`**

In `ocx_model_validator/model/ir/catalogues.py`, add an import for `IrCurve3D` and append the two classes:

```python
from ocx_model_validator.model.ir.geometry import IrCurve3D


@dataclass(frozen=True)
class IrHole2D:
    """Hole shape definition from HoleShapeCatalogue."""
    id: str
    name: str | None = None
    guidref: str | None = None
    contour: IrCurve3D | None = None


@dataclass
class IrHoleShapeCatalogue:
    id: str
    name: str | None = None
    holes: dict[str, IrHole2D] = field(default_factory=dict)
```

(Ensure `from dataclasses import dataclass, field` is present at the top of `catalogues.py`.)

- [ ] **Step 4: Re-export from `__init__.py`**

Update the `catalogues` import block in `ocx_model_validator/model/ir/__init__.py`:

```python
from ocx_model_validator.model.ir.catalogues import (
    IrHole2D,
    IrHoleShapeCatalogue,
    IrMaterial,
)
```

And add to the `# catalogues` group in `__all__`:

```python
    "IrHole2D", "IrHoleShapeCatalogue",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_catalogues.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/model/ir/catalogues.py ocx_model_validator/model/ir/__init__.py tests/test_ir_catalogues.py
git commit -m "feat: add IrHole2D and IrHoleShapeCatalogue catalogue types

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Extend `arrangement.py` — cargo types and the design-view tree

Adds the four cargo types and the recursive occurrence tree (`IrDesignView`, `IrOccurrenceGroup`, `IrOccurrence`). `arrangement.py` already declares `from __future__ import annotations` (added in Task 1), which is required for the recursive forward reference in `IrOccurrenceGroup.children`.

**Files:**
- Modify: `ocx_model_validator/model/ir/arrangement.py`
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Modify: `tests/test_ir_builder.py` (remove `DesignView`, `OccurrenceGroup`, `Occurrence`)
- Test: `tests/test_ir_arrangement_additions.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_arrangement_additions.py`:

```python
"""Unit tests for cargo and design-view IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBulkCargo,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrOccurrence,
    IrOccurrenceGroup,
    IrUnitCargo,
    Quantity,
    Ref,
)


def test_liquid_cargo_fields():
    c = IrLiquidCargo(id="lc1", density=Quantity(1.025, "UKgOverm3"))
    assert c.compartment_ref is None
    assert c.density == Quantity(1.025, "UKgOverm3")
    assert c.cargo_type is None


def test_gaseous_bulk_unit_cargo_defaults():
    g = IrGaseousCargo(id="g1")
    assert g.carriage_pressure is None
    b = IrBulkCargo(id="b1", angle_of_repose=Quantity(30.0, "Udeg"))
    assert b.stowage_factor is None and b.angle_of_repose == Quantity(30.0, "Udeg")
    u = IrUnitCargo(id="u1", compartment_ref=Ref("comp1"))
    assert u.compartment_ref == Ref("comp1")


def test_occurrence_defaults():
    o = IrOccurrence(id="o1")
    assert o.definition_ref is None and o.transformation is None


def test_design_view_is_recursive_tree():
    leaf = IrOccurrence(id="o1", name="part-a")
    inner = IrOccurrenceGroup(id="g-inner", children=[leaf])
    outer = IrOccurrenceGroup(id="g-outer", children=[inner])
    view = IrDesignView(id="dv1", children=[outer])

    assert view.children[0].children[0].children[0] is leaf
    # group can hold both groups and occurrences at the same level
    mixed = IrOccurrenceGroup(id="g", children=[leaf, inner])
    assert mixed.children == [leaf, inner]


def test_design_view_children_default_empty():
    assert IrDesignView(id="dv2").children == []
    assert IrOccurrenceGroup(id="g2").children == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_arrangement_additions.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrLiquidCargo'`.

- [ ] **Step 3: Add cargo and design-view types to `arrangement.py`**

Append to `ocx_model_validator/model/ir/arrangement.py` (the file already has `from __future__ import annotations` and imports `Quantity`, `Ref`):

```python
@dataclass
class IrLiquidCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    filling_height: Quantity | None = None
    permeability: Quantity | None = None


@dataclass
class IrGaseousCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    carriage_pressure: Quantity | None = None


@dataclass
class IrBulkCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    stowage_factor: Quantity | None = None
    stowage_height: Quantity | None = None
    angle_of_repose: Quantity | None = None


@dataclass
class IrUnitCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None


@dataclass
class IrOccurrence:
    id: str
    name: str | None = None
    guidref: str | None = None
    definition_ref: Ref | None = None
    transformation: dict | None = None  # raw geometry transform


@dataclass
class IrOccurrenceGroup:
    """Can nest IrOccurrenceGroup and IrOccurrence at any depth."""
    id: str
    name: str | None = None
    guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)


@dataclass
class IrDesignView:
    id: str
    name: str | None = None
    guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)
```

- [ ] **Step 4: Re-export from `__init__.py`**

Update the `arrangement` import block in `ocx_model_validator/model/ir/__init__.py`:

```python
from ocx_model_validator.model.ir.arrangement import (
    IrBulkCargo,
    IrCompartment,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrOccurrence,
    IrOccurrenceGroup,
    IrPhysicalSpace,
    IrUnitCargo,
)
```

And add to the `# arrangement` group in `__all__`:

```python
    "IrLiquidCargo", "IrGaseousCargo", "IrBulkCargo", "IrUnitCargo",
    "IrDesignView", "IrOccurrenceGroup", "IrOccurrence",
```

- [ ] **Step 5: Remove implemented entries from `MISSING_IR_CLASSES`**

In `tests/test_ir_builder.py`, delete `("DesignView", ...)`, `("OccurrenceGroup", ...)`, `("Occurrence", ...)`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_arrangement_additions.py tests/test_ir_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/model/ir/arrangement.py ocx_model_validator/model/ir/__init__.py tests/test_ir_arrangement_additions.py tests/test_ir_builder.py
git commit -m "feat: add cargo IR types and recursive design-view occurrence tree

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Add `metadata.py` — typed vessel metadata

Adds the typed metadata dataclasses that will replace the raw `dict | None` fields on `IrVessel` in Task 8.

**Files:**
- Create: `ocx_model_validator/model/ir/metadata.py`
- Modify: `ocx_model_validator/model/ir/__init__.py`
- Modify: `tests/test_ir_builder.py` (remove `ShipDesignation`, `StatutoryData`, `TonnageData`)
- Test: `tests/test_ir_metadata.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_metadata.py`:

```python
"""Unit tests for vessel metadata IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBuilderInformation,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
    IrTonnageData,
    Quantity,
)


def test_ship_designation_defaults():
    s = IrShipDesignation()
    assert s.vessel_name is None and s.imo_number is None
    s2 = IrShipDesignation(vessel_name="MV Test", imo_number="1234567")
    assert s2.vessel_name == "MV Test" and s2.imo_number == "1234567"


def test_tonnage_data_defaults():
    t = IrTonnageData()
    assert t.gross_tonnage is None and t.net_tonnage is None


def test_principal_particulars_fields():
    pp = IrPrincipalParticulars(lpp=Quantity(200.0, "Um"))
    assert pp.lpp == Quantity(200.0, "Um")
    assert pp.moulded_breadth is None
    assert pp.block_coefficient is None


def test_statutory_data_holds_tonnage():
    st = IrStatutoryData(tonnage_data=IrTonnageData(gross_tonnage=Quantity(50000.0, "")))
    assert st.tonnage_data.gross_tonnage == Quantity(50000.0, "")
    assert st.freeboard_type is None


def test_builder_information_defaults():
    b = IrBuilderInformation(builder_name="Yard X")
    assert b.builder_name == "Yard X"
    assert b.yard_number is None and b.delivery_date is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_metadata.py -q`
Expected: FAIL with `ImportError: cannot import name 'IrShipDesignation'`.

- [ ] **Step 3: Create `metadata.py`**

`ocx_model_validator/model/ir/metadata.py`:

```python
"""Typed vessel metadata IR types."""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.model.ir.base import Quantity


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

- [ ] **Step 4: Re-export from `__init__.py`**

Add to `ocx_model_validator/model/ir/__init__.py`:

```python
from ocx_model_validator.model.ir.metadata import (
    IrBuilderInformation,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
    IrTonnageData,
)
```

And add a `# metadata` group to `__all__`:

```python
    # metadata
    "IrShipDesignation", "IrTonnageData", "IrPrincipalParticulars",
    "IrStatutoryData", "IrBuilderInformation",
```

- [ ] **Step 5: Remove implemented entries from `MISSING_IR_CLASSES`**

In `tests/test_ir_builder.py`, delete `("ShipDesignation", ...)`, `("StatutoryData", ...)`, `("TonnageData", ...)`. Leave `ClassNotation` and `Tonnage` in place (no `IrClassNotation` / `IrTonnage` created).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_metadata.py tests/test_ir_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/model/ir/metadata.py ocx_model_validator/model/ir/__init__.py tests/test_ir_metadata.py tests/test_ir_builder.py
git commit -m "feat: add typed vessel metadata IR dataclasses

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Wire new collections and typed metadata into `IrVessel`

Adds the new flat dicts and typed-metadata fields to `IrVessel`, plus matching look-up helpers. The four metadata field annotations change from `dict | None` to typed IR classes; `classification` stays `dict[str, Any] | None`.

> **Builder note:** `OcxV3Builder` still assigns plain `dict`s to `ir.ship_designation` / `builder_info` / `principal_particulars` at runtime. Python does not enforce dataclass annotations at runtime, so existing builder tests keep passing. Aligning the builder to emit typed metadata is explicitly deferred to the builder plan. Do not modify `v3_builder.py` in this task.

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py` (the `IrVessel` dataclass)
- Test: `tests/test_ir_vessel_fields.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ir_vessel_fields.py`:

```python
"""Unit tests for new IrVessel collection and metadata fields."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBuilderInformation,
    IrBulkCargo,
    IrCoordinateSystem,
    IrDesignView,
    IrGaseousCargo,
    IrHoleShapeCatalogue,
    IrLiquidCargo,
    IrMember,
    IrPrincipalParticulars,
    IrRefPlane,
    IrSeam,
    IrShipDesignation,
    IrStatutoryData,
    IrSurface,
    IrSurfaceCollection,
    IrUnitCargo,
    IrVessel,
    ParentKind,
    ParentRef,
)


def test_new_collection_dicts_default_empty():
    v = IrVessel(id="v1")
    for attr in (
        "seams", "members", "liquid_cargoes", "gaseous_cargoes",
        "bulk_cargoes", "unit_cargoes", "coordinate_systems", "ref_planes",
        "surfaces", "surface_collections", "design_views",
        "connection_configurations",
    ):
        assert getattr(v, attr) == {}, attr
    assert v.hole_shape_catalogue is None


def test_typed_metadata_fields_default_none():
    v = IrVessel(id="v1")
    assert v.ship_designation is None
    assert v.principal_particulars is None
    assert v.statutory_data is None
    assert v.builder_info is None
    assert v.classification is None


def test_typed_metadata_assignment():
    v = IrVessel(id="v1")
    v.ship_designation = IrShipDesignation(vessel_name="MV Test")
    v.principal_particulars = IrPrincipalParticulars()
    v.statutory_data = IrStatutoryData()
    v.builder_info = IrBuilderInformation(builder_name="Yard X")
    assert v.ship_designation.vessel_name == "MV Test"
    assert isinstance(v.builder_info, IrBuilderInformation)


def test_new_lookup_helpers():
    v = IrVessel(id="v1")
    parent = ParentRef(kind=ParentKind.VESSEL, id="v1")
    v.seams["s1"] = IrSeam(id="s1")
    v.members["m1"] = IrMember(id="m1", parent_ref=parent)
    assert v.get_seam("s1").id == "s1"
    assert v.get_member("m1").id == "m1"
    assert v.get_seam("missing") is None
    assert v.get_member("missing") is None


def test_collections_accept_their_types():
    v = IrVessel(id="v1")
    v.liquid_cargoes["lc"] = IrLiquidCargo(id="lc")
    v.gaseous_cargoes["gc"] = IrGaseousCargo(id="gc")
    v.bulk_cargoes["bc"] = IrBulkCargo(id="bc")
    v.unit_cargoes["uc"] = IrUnitCargo(id="uc")
    v.coordinate_systems["cs"] = IrCoordinateSystem(id="cs")
    v.ref_planes["rp"] = IrRefPlane(id="rp")
    v.surfaces["sf"] = IrSurface(id="sf")
    v.surface_collections["scoll"] = IrSurfaceCollection(id="scoll")
    v.design_views["dv"] = IrDesignView(id="dv")
    v.hole_shape_catalogue = IrHoleShapeCatalogue(id="cat")
    assert v.liquid_cargoes["lc"].id == "lc"
    assert v.hole_shape_catalogue.id == "cat"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ir_vessel_fields.py -q`
Expected: FAIL with `AttributeError`/`TypeError` (e.g. `IrVessel` has no field `seams`).

- [ ] **Step 3: Add imports needed by the new `IrVessel` field annotations**

At the top of `ocx_model_validator/model/ir/structural.py`, add imports for the new collection element types:

```python
from ocx_model_validator.model.ir.geometry import (
    IrCoordinateSystem,
    IrRefPlane,
    IrSurface,
    IrSurfaceCollection,
)
from ocx_model_validator.model.ir.catalogues import (
    IrHoleShapeCatalogue,
    IrMaterial,
)
from ocx_model_validator.model.ir.arrangement import (
    IrBulkCargo,
    IrCompartment,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrPhysicalSpace,
    IrUnitCargo,
)
from ocx_model_validator.model.ir.connections import (
    IrConnectionConfiguration,
    IrPenetration,
)
from ocx_model_validator.model.ir.metadata import (
    IrBuilderInformation,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
)
```

(Merge with the existing `IrPoint3D` geometry import and the existing `IrCompartment`/`IrPhysicalSpace`/`IrMaterial` imports already present — do not duplicate names. The combined imports must remain free of cycles: `connections`, `geometry`, `catalogues`, `arrangement`, `metadata` never import `structural`.)

- [ ] **Step 4: Add the new collection fields to `IrVessel`**

In the `IrVessel` dataclass, after the existing `edge_reinforcements` dict and within the structural/catalogue/arrangement groupings, add:

```python
    # --- new structural collections ---
    seams: dict[str, IrSeam] = field(default_factory=dict)
    members: dict[str, IrMember] = field(default_factory=dict)

    # --- cargo collections ---
    liquid_cargoes: dict[str, IrLiquidCargo] = field(default_factory=dict)
    gaseous_cargoes: dict[str, IrGaseousCargo] = field(default_factory=dict)
    bulk_cargoes: dict[str, IrBulkCargo] = field(default_factory=dict)
    unit_cargoes: dict[str, IrUnitCargo] = field(default_factory=dict)

    # --- geometry collections ---
    coordinate_systems: dict[str, IrCoordinateSystem] = field(default_factory=dict)
    ref_planes: dict[str, IrRefPlane] = field(default_factory=dict)
    surfaces: dict[str, IrSurface] = field(default_factory=dict)
    surface_collections: dict[str, IrSurfaceCollection] = field(default_factory=dict)

    # --- hole-shape catalogue (single, optional) ---
    hole_shape_catalogue: IrHoleShapeCatalogue | None = None

    # --- design views ---
    design_views: dict[str, IrDesignView] = field(default_factory=dict)

    # --- connection configurations (placeholder) ---
    connection_configurations: dict[str, IrConnectionConfiguration] = field(default_factory=dict)
```

`IrSeam` and `IrMember` are defined in the same module (`structural.py`) above `IrVessel`, so no import is needed for them.

- [ ] **Step 5: Change the four metadata field annotations on `IrVessel`**

Replace the existing block:

```python
    # --- vessel-level metadata ---
    ship_designation: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    builder_info: dict[str, Any] | None = None
    principal_particulars: dict[str, Any] | None = None
```

with:

```python
    # --- vessel-level metadata ---
    ship_designation: IrShipDesignation | None = None
    classification: dict[str, Any] | None = None  # ClassificationData not in scope
    builder_info: IrBuilderInformation | None = None
    principal_particulars: IrPrincipalParticulars | None = None
    statutory_data: IrStatutoryData | None = None
```

(`Any` is still imported and still used by `classification`.)

- [ ] **Step 6: Add `get_seam` and `get_member` look-up helpers**

In the convenience helpers section of `IrVessel` (next to `get_compartment`), add:

```python
    def get_seam(self, seam_id: str) -> IrSeam | None:
        return self.seams.get(seam_id)

    def get_member(self, member_id: str) -> IrMember | None:
        return self.members.get(member_id)
```

- [ ] **Step 7: Run the new tests**

Run: `uv run pytest tests/test_ir_vessel_fields.py -q`
Expected: PASS.

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS. In particular, existing builder tests in `tests/test_ir_builder.py` that assign/read `ir.ship_designation` as a dict still pass (runtime is dict-agnostic).

- [ ] **Step 9: Commit**

```bash
git add ocx_model_validator/model/ir/structural.py tests/test_ir_vessel_fields.py
git commit -m "feat: add new IrVessel collections, typed metadata fields, and look-up helpers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: Integration verification and docstring refresh

Final consistency pass: confirm the whole public surface imports cleanly, the package docstring reflects the new layout, and the full suite is green.

**Files:**
- Modify: `ocx_model_validator/model/ir/__init__.py` (docstring only, if needed)
- Test: `tests/test_ir_package_surface.py` (new)

- [ ] **Step 1: Write an import-surface smoke test**

Create `tests/test_ir_package_surface.py`:

```python
"""Smoke test: every name in ir.__all__ is importable and matches re-exports."""
from __future__ import annotations

import ocx_model_validator.model.ir as ir


def test_all_names_are_importable():
    for name in ir.__all__:
        assert hasattr(ir, name), f"{name} listed in __all__ but missing"


def test_representative_new_types_present():
    expected = [
        "IrPoint3D", "IrCurve3D", "IrLine3D", "IrSurface3D",
        "IrSeam", "IrMember", "IrEndCut", "IrFeatureCope",
        "IrLiquidCargo", "IrDesignView", "IrOccurrenceGroup",
        "IrHole2D", "IrHoleShapeCatalogue",
        "IrShipDesignation", "IrPrincipalParticulars", "IrStatutoryData",
        "IrConnectionConfiguration", "IrPenetration",
    ]
    for name in expected:
        assert hasattr(ir, name), name


def test_backward_compatible_core_imports_still_work():
    from ocx_model_validator.model.ir import (  # noqa: F401
        IrVessel,
        IrPanel,
        IrPlate,
        IrSection,
        IrMaterial,
        Quantity,
        Ref,
    )
```

- [ ] **Step 2: Run the smoke test**

Run: `uv run pytest tests/test_ir_package_surface.py -q`
Expected: PASS. If a name in `__all__` has no matching re-export (or vice versa), fix `__init__.py`.

- [ ] **Step 3: Refresh the package docstring (if stale)**

Confirm the module docstring at the top of `ocx_model_validator/model/ir/__init__.py` accurately summarizes the split package. If it still describes a single file, update the prose to mention the submodule layout (`base`, `sections`, `geometry`, `structural`, `arrangement`, `catalogues`, `metadata`, `connections`). No behavior change.

- [ ] **Step 4: Confirm no `MISSING_IR_CLASSES` regressions**

Run: `uv run pytest tests/test_ir_builder.py -q`
Expected: PASS. The remaining `MISSING_IR_CLASSES` entries should be exactly: `Positions`, `CircumCircle3D`, `XRefPlanes`, `YRefPlanes`, `ZRefPlanes`, `WebStiffener`, `WebStiffenerWithSingleBracket`, `SlotParameters`, `HoleContourRef`, `InnerContour`, `ClassNotation`, `Tonnage`. Verify none of these have a corresponding `Ir*` class.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all original tests plus the new IR test modules).

- [ ] **Step 6: Commit**

```bash
git add tests/test_ir_package_surface.py ocx_model_validator/model/ir/__init__.py
git commit -m "test: add IR package import-surface smoke test; refresh package docstring

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Checklist (completed by plan author)

**Spec coverage:**
- geometry.py (points, vectors, curves, surfaces, reference geometry) → Task 2 ✓
- structural.py additions (IrSeam, IrMember, IrEndCut, IrFeatureCope; IrStiffener/IrPanel fields) → Task 4 ✓
- catalogues.py (IrHole2D, IrHoleShapeCatalogue) → Task 5 ✓
- arrangement.py (cargoes, design-view tree) → Task 6 ✓
- metadata.py (5 metadata types) → Task 7 ✓
- connections.py (placeholders) → Task 3 ✓
- IrVessel new fields table (all dicts + typed metadata) → Task 8 ✓
- Package split + backward-compatible re-exports → Task 1, incremental re-exports Tasks 2–8, smoke test Task 9 ✓
- `IrCurve3D.curve_length` required-positional behavior tested → Task 2 Step 1 ✓
- `MISSING_IR_CLASSES` upkeep → Tasks 2, 3, 4, 6, 7 + verification Task 9 ✓

**Out of scope (deferred to builder plan):** all `OcxV3Builder._build_*` extraction methods; aligning builder metadata emission to the new typed classes. The spec's "Builder impact" section is satisfied by a future plan.

**Type consistency:** `IrPenetration` defined in `connections.py` (Task 3), referenced by `IrStiffener` (Task 4) and `IrVessel.connection_configurations` (Task 8). `IrPoint3D` defined in `geometry.py` (Task 2), used by `IrMember`/`IrEndCut`-adjacent types (Task 4) and geometry collections (Task 8). Module import direction is one-way (no cycles): `base → {geometry, sections, catalogues} → connections → structural`, with `arrangement`/`metadata` importing only `base`. `catalogues` imports `geometry` (for `IrHole2D.contour`) — still acyclic.
