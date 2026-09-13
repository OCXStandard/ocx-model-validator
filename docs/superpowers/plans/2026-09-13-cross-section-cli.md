# Cross-Section CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `validator section create` (cross-section JSON at a frame/x-position) and `validator section plot` (SVG plot with thickness-colored plates and inclined, numbered stiffener stubs).

**Architecture:** Extend the existing IR → section pipeline with stiffener `Inclination` data (OCX → `IrStiffener.inclinations` → `SectionStiffener.web_dir_y/web_dir_z` → JSON), add a stdlib-only SVG renderer `sections/svg_plot.py` that consumes the `nh-cross-section/1` JSON, and wire both into a new `section` typer sub-app in `cli.py`. All JSON building/saving/loading already exists in `sections/document.py`.

**Tech Stack:** Python ≥3.12, typer, loguru, stdlib SVG string generation (no new dependencies). All commands run from the repo root with `uv run`.

**Spec:** `docs/superpowers/specs/2026-09-13-cross-section-cli-design.md`

---

## Existing APIs you will use (do not reinvent)

- `ocx_model_validator/sections/document.py`:
  - `build_document(vessel, source_file, x_mm=None, frame=None) -> dict` — raises `SectionError` if both/neither of x_mm/frame, if the frame label is unknown, or if nothing intersects.
  - `save_document(doc, path)`, `load_document(path)` (validates schema `"nh-cross-section/1"`, raises `SectionError`).
- `ocx_model_validator/cli.py`: `_load_vessel(model: Path)` (parse+build IR, `typer.Exit(1)` on failure), `app` (root typer app). Pattern for sub-apps: `report_app = typer.Typer(...); app.add_typer(report_app, name="report")`.
- `ocx_model_validator/exeptions.py`: `SectionError`, `GeometryError` (module name typo is intentional).
- Test fixture `stub_dir_310` (session-scoped, in `tests/conftest.py`) → `tests/data/ocx_310_stubs/`; `vessel.3docx` exists there but contains no intersectable geometry.
- Logging: loguru only (`from loguru import logger`). Never `print()`.
- Every commit message gets the trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

---

### Task 1: `IrInclination` in the IR

**Files:**
- Modify: `ocx_model_validator/model/ir/structural.py` (IrStiffener is at ~line 87)
- Test: `tests/test_ir_inclination.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_ir_inclination.py`:

```python
"""IR: stiffener inclination records."""
from ocx_model_validator.model.ir.base import ParentKind, ParentRef
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
from ocx_model_validator.model.ir.structural import IrInclination, IrStiffener


def test_inclination_fields():
    inc = IrInclination(
        web_direction=IrVector3D(0.0, 0.0, 1.0),
        flange_direction=None,
        position=IrPoint3D(1.0, 2.0, 3.0, "Um"),
    )
    assert inc.web_direction.z == 1.0
    assert inc.flange_direction is None
    assert inc.position.unit == "Um"


def test_stiffener_inclinations_default_empty():
    s = IrStiffener(id="S1", parent_ref=ParentRef(kind=ParentKind.VESSEL, ref="V1"))
    assert s.inclinations == []
```

Note: check the actual `ParentRef` constructor signature in
`ocx_model_validator/model/ir/base.py` first (field may be named `ref` or `id`)
and adapt the test to match existing usage in `tests/`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ir_inclination.py -v`
Expected: FAIL — `ImportError: cannot import name 'IrInclination'`

- [ ] **Step 3: Implement**

In `ocx_model_validator/model/ir/structural.py`, add above `class IrStiffener`
(import `IrPoint3D`, `IrVector3D` from `.geometry` if not already imported):

```python
@dataclass(frozen=True)
class IrInclination:
    """Local web/flange orientation of a stiffener at a position on its trace."""
    web_direction: IrVector3D | None = None
    flange_direction: IrVector3D | None = None
    position: IrPoint3D | None = None
```

And add to `IrStiffener` (after `trace`):

```python
    inclinations: list[IrInclination] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ir_inclination.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/model/ir/structural.py tests/test_ir_inclination.py
git commit -m "feat(ir): add IrInclination and IrStiffener.inclinations"
```

---

### Task 2: Builder extracts `Inclination`

**Files:**
- Modify: `ocx_model_validator/builders/v3_builder.py` (`_build_stiffener`, ~line 1030)
- Test: `tests/test_builders.py` (append)

The raw OCX `Stiffener` has field `inclination` (a **list** of `Inclination`
objects, each with `web_direction`, `flange_direction`, `position`). OCX
`Vector3D` carries a `direction` list; `Point3D` carries a `coordinates` list
plus `unit` — the existing `OcxV3Builder._pt` / `_vec` static helpers already
unpack those.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_builders.py`, following its existing inline-stub-class
conventions (read the top of the file first for how stub OCX objects and the
builder are instantiated there — reuse the same pattern):

```python
class _StubVector3D:
    def __init__(self, direction):
        self.direction = direction


class _StubPoint3D:
    def __init__(self, coordinates, unit="Um"):
        self.coordinates = coordinates
        self.unit = unit


class _StubInclination:
    def __init__(self, web_direction=None, flange_direction=None, position=None):
        self.web_direction = web_direction
        self.flange_direction = flange_direction
        self.position = position


class _StubStiffenerWithInclination:
    id = "S1"
    name = "L1"
    guidref = None
    physical_properties = None
    material_ref = None
    section_ref = None
    function_type = None
    end_cut_end1 = None
    end_cut_end2 = None
    trace_line = None
    inclination = [
        _StubInclination(
            web_direction=_StubVector3D([0.0, 0.0, 1.0]),
            position=_StubPoint3D([10.0, 0.0, 5.0]),
        )
    ]


def test_build_stiffener_extracts_inclinations():
    builder = OcxV3Builder()
    parent = ParentRef(kind=ParentKind.VESSEL, ref="V1")
    s = builder._build_stiffener(_StubStiffenerWithInclination(), parent)
    assert len(s.inclinations) == 1
    inc = s.inclinations[0]
    assert inc.web_direction.z == 1.0
    assert inc.flange_direction is None
    assert inc.position.x == 10.0


def test_build_stiffener_without_inclination_defaults_empty():
    class _Bare(_StubStiffenerWithInclination):
        inclination = None

    builder = OcxV3Builder()
    parent = ParentRef(kind=ParentKind.VESSEL, ref="V1")
    s = builder._build_stiffener(_Bare(), parent)
    assert s.inclinations == []
```

Adapt names (`OcxV3Builder` import, `ParentRef` construction) to what
`tests/test_builders.py` already uses.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_builders.py -v -k inclination`
Expected: FAIL — `IrStiffener` built without `inclinations` content /
`AssertionError: assert 0 == 1`

- [ ] **Step 3: Implement**

In `v3_builder.py`, add a helper method next to `_build_end_cut`:

```python
    def _build_inclinations(self, raw_list) -> list[IrInclination]:
        result: list[IrInclination] = []
        for raw in raw_list or []:
            result.append(IrInclination(
                web_direction=self._vec(getattr(raw, "web_direction", None)),
                flange_direction=self._vec(getattr(raw, "flange_direction", None)),
                position=self._pt(getattr(raw, "position", None)),
            ))
        return result
```

Import `IrInclination` alongside the other `structural` imports. Then in
`_build_stiffener`, add to the `IrStiffener(...)` call after `trace=...`:

```python
            inclinations=self._build_inclinations(getattr(raw, "inclination", None)),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_builders.py -v`
Expected: all PASS (including the 2 new tests)

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/builders/v3_builder.py tests/test_builders.py
git commit -m "feat(builder): extract stiffener Inclination into IR"
```

---

### Task 3: Web direction in `SectionStiffener` and the JSON

**Files:**
- Modify: `ocx_model_validator/sections/section_builder.py`
- Test: `tests/test_section_web_dir.py` (create)

`SectionStiffener` (frozen dataclass, top of `section_builder.py`) gains two
nullable fields. `_build_stiffeners` computes them per stiffener from
`IrStiffener.inclinations`: pick the inclination whose `position.x` (converted
to mm with the existing `to_mm` closure) is nearest the section `x_mm` (first
inclination if no positions), project its `web_direction` onto the (y, z)
plane, and normalize. Degenerate projection (length < 1e-9) or no inclination
→ `None` + warning. JSON serialization is automatic (`_dataclass_dict` in
`document.py` uses `asdict`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_section_web_dir.py`:

```python
"""Section builder: projected stiffener web direction."""
import math

from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
from ocx_model_validator.model.ir.structural import IrInclination
from ocx_model_validator.sections.section_builder import SectionStiffener, _web_dir


def _mk_stiffener(inclinations):
    class _S:
        name = "L1"
    s = _S()
    s.inclinations = inclinations
    return s


def _to_mm(p: IrPoint3D):
    factor = 1000.0 if p.unit == "Um" else 1.0
    return (p.x * factor, p.y * factor, p.z * factor)


def test_web_dir_projects_and_normalizes():
    inc = IrInclination(web_direction=IrVector3D(0.0, 3.0, 4.0))
    warnings: list[str] = []
    y, z = _web_dir(_mk_stiffener([inc]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert math.isclose(y, 0.6)
    assert math.isclose(z, 0.8)
    assert warnings == []


def test_web_dir_picks_nearest_position():
    inc_a = IrInclination(web_direction=IrVector3D(0.0, 0.0, 1.0),
                          position=IrPoint3D(0.0, 0.0, 0.0, "Um"))
    inc_b = IrInclination(web_direction=IrVector3D(0.0, 1.0, 0.0),
                          position=IrPoint3D(50.0, 0.0, 0.0, "Um"))
    warnings: list[str] = []
    y, z = _web_dir(_mk_stiffener([inc_a, inc_b]), x_mm=49_000.0,
                    to_mm=_to_mm, warnings=warnings)
    assert (y, z) == (1.0, 0.0)


def test_web_dir_missing_inclination_returns_none_and_warns():
    warnings: list[str] = []
    result = _web_dir(_mk_stiffener([]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert result == (None, None)
    assert any("no inclination" in w for w in warnings)


def test_web_dir_x_only_vector_is_degenerate():
    inc = IrInclination(web_direction=IrVector3D(1.0, 0.0, 0.0))
    warnings: list[str] = []
    result = _web_dir(_mk_stiffener([inc]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert result == (None, None)
    assert warnings


def test_section_stiffener_has_web_dir_fields():
    s = SectionStiffener(name="L1", y_mm=0.0, z_mm=0.0, panel=None,
                         profile_type=None, profile_dimensions=None,
                         material_reh_mpa=None, spacing_mm=None)
    assert s.web_dir_y is None
    assert s.web_dir_z is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_section_web_dir.py -v`
Expected: FAIL — `ImportError: cannot import name '_web_dir'`

- [ ] **Step 3: Implement**

In `section_builder.py`:

1. Add to `SectionStiffener` (after `web_angle_deg: float = 90.0`):

```python
    web_dir_y: float | None = None
    web_dir_z: float | None = None
```

2. Add a module-level function (near `_profile`):

```python
def _web_dir(
    stiffener,
    x_mm: float,
    to_mm,
    warnings: list[str],
) -> tuple[float | None, float | None]:
    """Project the stiffener web direction onto the section (y, z) plane."""
    inclinations = getattr(stiffener, "inclinations", None) or []
    candidates = [inc for inc in inclinations if inc.web_direction is not None]
    if not candidates:
        warnings.append(f"stiffener {_name(stiffener)}: no inclination; web direction unknown")
        return None, None

    def _distance(inc) -> float:
        if inc.position is None:
            return float("inf")
        px, _, _ = to_mm(inc.position)
        return abs(px - x_mm)

    with_pos = [inc for inc in candidates if inc.position is not None]
    chosen = min(with_pos, key=_distance) if with_pos else candidates[0]
    wd = chosen.web_direction
    length = hypot(wd.y, wd.z)
    if length < 1e-9:
        warnings.append(
            f"stiffener {_name(stiffener)}: web direction has no in-plane component"
        )
        return None, None
    return wd.y / length, wd.z / length
```

(`hypot` is already imported from `math` for `_with_spacing`; `_name` exists.
Note `_name` expects an object with `.name`/`.id` — the test stub provides
`.name`; check `_name`'s implementation and keep the test stub compatible.)

3. In `_build_stiffeners`, before the `for y_mm, z_mm in hits:` loop, compute
once per stiffener:

```python
            web_dir_y, web_dir_z = _web_dir(stiffener, x_mm, to_mm, warnings)
```

and pass into the `SectionStiffener(...)` constructor:

```python
                            web_dir_y=web_dir_y,
                            web_dir_z=web_dir_z,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_section_web_dir.py tests/test_sections* -v`
Expected: all PASS (existing section tests must not regress — `SectionStiffener`
gained only defaulted fields)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/sections/section_builder.py tests/test_section_web_dir.py
git commit -m "feat(sections): project stiffener web direction into section plane"
```

---

### Task 4: SVG renderer

**Files:**
- Create: `ocx_model_validator/sections/svg_plot.py`
- Test: `tests/test_svg_plot.py` (create)

Pure-stdlib SVG string generation. Layout: title at top; plot area on the
left (y horizontal → SVG x, z up → SVG y inverted, uniform scale); legend
column on the right with a numbered stiffener list and thickness swatches.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_svg_plot.py`:

```python
"""SVG renderer for cross-section documents."""
import xml.etree.ElementTree as ET

from ocx_model_validator.sections.svg_plot import _PALETTE, _UNKNOWN_COLOR, render_svg


def _doc(plates=None, stiffeners=None, x_mm=50_000.0, frame="FR20"):
    return {
        "schema": "nh-cross-section/1",
        "source": {"file": "ship.3docx", "vessel_id": "V1", "generated": "t"},
        "frame_table": {"frame0_offset_mm": 0.0, "entries": [], "positions": []},
        "cross_section": {
            "x_mm": x_mm,
            "frame": frame,
            "stiffeners": stiffeners or [],
            "plates": plates or [],
        },
        "compartments": [],
        "warnings": [],
    }


def _plate(name="P1", thickness=12.5, y1=0.0, z1=0.0, y2=10_000.0, z2=0.0):
    return {"name": name, "y1_mm": y1, "z1_mm": z1, "y2_mm": y2, "z2_mm": z2,
            "thickness_mm": thickness, "material_reh_mpa": None, "panel": None}


def _stiffener(name="L1", y=2_000.0, z=0.0, wdy=0.0, wdz=1.0,
               profile_type="FlatBar", profile_dimensions="200 x 20"):
    return {"name": name, "y_mm": y, "z_mm": z, "panel": None,
            "profile_type": profile_type, "profile_dimensions": profile_dimensions,
            "material_reh_mpa": None, "spacing_mm": None,
            "orientation": "Longitudinal", "web_angle_deg": 90.0,
            "web_dir_y": wdy, "web_dir_z": wdz}


def test_svg_is_well_formed_xml_with_title():
    svg = render_svg(_doc(plates=[_plate()]))
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "Cross section at x=50000.0 mm (frame FR20)" in svg
    assert "ship.3docx" in svg


def test_plate_lines_color_coded_by_thickness():
    svg = render_svg(_doc(plates=[
        _plate(name="A", thickness=10.0, z1=0.0, z2=0.0),
        _plate(name="B", thickness=15.0, y1=0.0, z1=0.0, y2=0.0, z2=8_000.0),
        _plate(name="C", thickness=10.0, z1=2_000.0, z2=2_000.0),
    ]))
    # sorted unique thicknesses: 10.0 -> palette[0], 15.0 -> palette[1]
    assert svg.count(f'stroke="{_PALETTE[0]}"') >= 3  # 2 plate lines + 1 swatch
    assert svg.count(f'stroke="{_PALETTE[1]}"') >= 2  # 1 plate line + 1 swatch
    assert "10.0 mm" in svg and "15.0 mm" in svg


def test_unknown_thickness_dashed_grey():
    svg = render_svg(_doc(plates=[_plate(thickness=None)]))
    assert _UNKNOWN_COLOR in svg
    assert "stroke-dasharray" in svg


def test_stiffener_stub_direction_and_number():
    svg = render_svg(_doc(plates=[_plate()],
                          stiffeners=[_stiffener(wdy=0.0, wdz=1.0)]))
    root = ET.fromstring(svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    stubs = [l for l in root.iter("{http://www.w3.org/2000/svg}line")
             if l.get("class") == "stiffener"]
    assert len(stubs) == 1
    stub = stubs[0]
    # web dir (0, +1): stub goes up => SVG y decreases, x constant
    assert float(stub.get("x1")) == float(stub.get("x2"))
    assert float(stub.get("y2")) < float(stub.get("y1"))
    # numbered label "1" exists
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    assert "1" in texts


def test_stiffener_unknown_direction_dashed_vertical():
    svg = render_svg(_doc(plates=[_plate()],
                          stiffeners=[_stiffener(wdy=None, wdz=None)]))
    root = ET.fromstring(svg)
    stubs = [l for l in root.iter("{http://www.w3.org/2000/svg}line")
             if l.get("class") == "stiffener"]
    assert stubs[0].get("stroke-dasharray")
    assert float(stubs[0].get("x1")) == float(stubs[0].get("x2"))


def test_stiffener_legend_rows_in_json_order():
    svg = render_svg(_doc(plates=[_plate()], stiffeners=[
        _stiffener(name="HP-A", profile_type="BulbFlat",
                   profile_dimensions="240 x 10"),
        _stiffener(name="FB-B", y=4_000.0),
    ]))
    assert "1  HP-A — BulbFlat 240 x 10" in svg
    assert "2  FB-B — FlatBar 200 x 20" in svg
    assert svg.index("HP-A") < svg.index("FB-B")


def test_user_strings_are_escaped():
    svg = render_svg(_doc(plates=[_plate(name="A<&>B")],
                          stiffeners=[_stiffener(name="L<1>")]))
    assert "A<&>B" not in svg
    assert "L<1>" not in svg
    ET.fromstring(svg)  # must stay well-formed


def test_empty_geometry_renders_note():
    svg = render_svg(_doc())
    assert "no geometry" in svg.lower()
    ET.fromstring(svg)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_svg_plot.py -v`
Expected: FAIL — `ModuleNotFoundError: ocx_model_validator.sections.svg_plot`

- [ ] **Step 3: Implement**

Create `ocx_model_validator/sections/svg_plot.py`:

```python
"""Render an nh-cross-section/1 JSON document as an SVG plot (stdlib only).

Layout: title on top, plot area left (y → right, z → up), legend column right
with the numbered stiffener list and plate-thickness swatches.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
    "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]
_UNKNOWN_COLOR = "#999999"

_PLOT_W = 1200.0
_PLOT_H = 900.0
_LEGEND_W = 360.0
_MARGIN = 40.0
_TITLE_H = 60.0
_ROW_H = 18.0
_STUB_DEFAULT_MM = 250.0
_SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'


def render_svg(doc: dict) -> str:
    """Render the cross-section document as an SVG string."""
    cs = doc["cross_section"]
    plates: list[dict] = cs.get("plates") or []
    stiffeners: list[dict] = cs.get("stiffeners") or []
    source = (doc.get("source") or {}).get("file", "")

    parts: list[str] = []
    title = f"Cross section at x={cs.get('x_mm')} mm"
    if cs.get("frame"):
        title += f" (frame {cs['frame']})"
    parts.append(
        f'<text x="{_MARGIN}" y="28" font-size="18" font-weight="bold" '
        f'font-family="sans-serif">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{_MARGIN}" y="48" font-size="12" fill="#555" '
        f'font-family="sans-serif">{escape(str(source))}</text>'
    )

    color_of = _thickness_colors(plates)
    to_px = _fit(plates, stiffeners)

    if to_px is None:
        parts.append(
            f'<text x="{_MARGIN}" y="{_TITLE_H + 40}" font-size="14" '
            f'font-family="sans-serif">(no geometry to plot)</text>'
        )
    else:
        parts.extend(_plate_lines(plates, color_of, to_px))
        parts.extend(_stiffener_stubs(stiffeners, to_px))

    legend_x = _MARGIN + _PLOT_W + 40.0
    legend_parts, legend_h = _legend(stiffeners, color_of, legend_x)
    parts.extend(legend_parts)

    width = _MARGIN * 2 + _PLOT_W + _LEGEND_W
    height = max(_TITLE_H + _PLOT_H + _MARGIN * 2, _TITLE_H + legend_h + _MARGIN)
    body = "\n".join(parts)
    return (
        f'<svg {_SVG_NS} width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">\n'
        f'<rect width="100%" height="100%" fill="white"/>\n{body}\n</svg>\n'
    )


def _thickness_colors(plates: list[dict]) -> dict[float, str]:
    values = sorted({p["thickness_mm"] for p in plates
                     if p.get("thickness_mm") is not None})
    return {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(values)}


def _fit(plates: list[dict], stiffeners: list[dict]):
    """Return a (y_mm, z_mm) -> (px, py) mapper, or None if no geometry."""
    ys: list[float] = []
    zs: list[float] = []
    for p in plates:
        ys += [p["y1_mm"], p["y2_mm"]]
        zs += [p["z1_mm"], p["z2_mm"]]
    for s in stiffeners:
        ys.append(s["y_mm"])
        zs.append(s["z_mm"])
    if not ys:
        return None
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    span_y = max(max_y - min_y, 1.0)
    span_z = max(max_z - min_z, 1.0)
    pad_y, pad_z = span_y * 0.05, span_z * 0.05
    min_y, max_y = min_y - pad_y, max_y + pad_y
    min_z, max_z = min_z - pad_z, max_z + pad_z
    scale = min(_PLOT_W / (max_y - min_y), _PLOT_H / (max_z - min_z))

    def to_px(y_mm: float, z_mm: float) -> tuple[float, float]:
        return (_MARGIN + (y_mm - min_y) * scale,
                _TITLE_H + (max_z - z_mm) * scale)

    to_px.scale = scale  # px per mm, used for stub lengths
    return to_px


def _plate_lines(plates, color_of, to_px) -> list[str]:
    out = []
    for p in plates:
        x1, y1 = to_px(p["y1_mm"], p["z1_mm"])
        x2, y2 = to_px(p["y2_mm"], p["z2_mm"])
        t = p.get("thickness_mm")
        if t is None:
            style = f'stroke="{_UNKNOWN_COLOR}" stroke-dasharray="6 4"'
        else:
            style = f'stroke="{color_of[t]}"'
        out.append(
            f'<line class="plate" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}" {style} stroke-width="3">'
            f'<title>{escape(str(p.get("name") or ""))}</title></line>'
        )
    return out


def _stub_len_mm(profile_dimensions: str | None) -> float:
    if profile_dimensions:
        m = re.search(r"\d+(?:\.\d+)?", profile_dimensions)
        if m:
            return float(m.group())
    return _STUB_DEFAULT_MM


def _stiffener_stubs(stiffeners, to_px) -> list[str]:
    out = []
    for n, s in enumerate(stiffeners, start=1):
        x0, y0 = to_px(s["y_mm"], s["z_mm"])
        wdy, wdz = s.get("web_dir_y"), s.get("web_dir_z")
        length_px = _stub_len_mm(s.get("profile_dimensions")) * to_px.scale
        length_px = max(length_px, 8.0)
        if wdy is None or wdz is None:
            dx, dy, dash = 0.0, -length_px, ' stroke-dasharray="4 3"'
        else:
            dx, dy, dash = wdy * length_px, -wdz * length_px, ""
        x1, y1 = x0 + dx, y0 + dy
        out.append(
            f'<line class="stiffener" x1="{x0:.1f}" y1="{y0:.1f}" '
            f'x2="{x1:.1f}" y2="{y1:.1f}" stroke="black" stroke-width="1.5"{dash}/>'
        )
        lx, ly = x1 + dx * 0.15 + 3.0, y1 + dy * 0.15
        out.append(
            f'<text class="stiffener-no" x="{lx:.1f}" y="{ly:.1f}" '
            f'font-size="11" font-family="sans-serif">{n}</text>'
        )
    return out


def _legend(stiffeners, color_of, x: float) -> tuple[list[str], float]:
    out: list[str] = []
    y = _TITLE_H + 20.0
    out.append(f'<text x="{x}" y="{y}" font-size="14" font-weight="bold" '
               f'font-family="sans-serif">Stiffeners</text>')
    y += _ROW_H
    for n, s in enumerate(stiffeners, start=1):
        label = f"{n}  {s.get('name') or '?'}"
        profile = " ".join(str(v) for v in
                           (s.get("profile_type"), s.get("profile_dimensions")) if v)
        if profile:
            label += f" — {profile}"
        out.append(f'<text x="{x}" y="{y:.1f}" font-size="11" '
                   f'font-family="sans-serif">{escape(label)}</text>')
        y += _ROW_H
    y += _ROW_H
    out.append(f'<text x="{x}" y="{y:.1f}" font-size="14" font-weight="bold" '
               f'font-family="sans-serif">Plate thickness</text>')
    y += _ROW_H
    for t, color in color_of.items():
        out.append(f'<line x1="{x}" y1="{y - 4:.1f}" x2="{x + 30}" '
                   f'y2="{y - 4:.1f}" stroke="{color}" stroke-width="3"/>')
        out.append(f'<text x="{x + 38}" y="{y:.1f}" font-size="11" '
                   f'font-family="sans-serif">{t} mm</text>')
        y += _ROW_H
    out.append(f'<line x1="{x}" y1="{y - 4:.1f}" x2="{x + 30}" y2="{y - 4:.1f}" '
               f'stroke="{_UNKNOWN_COLOR}" stroke-width="3" stroke-dasharray="6 4"/>')
    out.append(f'<text x="{x + 38}" y="{y:.1f}" font-size="11" '
               f'font-family="sans-serif">unknown</text>')
    y += _ROW_H
    return out, y - _TITLE_H
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_svg_plot.py -v`
Expected: 9 PASSED. Iterate on small mismatches (e.g. exact title formatting)
by fixing the implementation, not weakening the tests, unless a test asserted
an implementation detail the spec doesn't require.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/svg_plot.py tests/test_svg_plot.py
git commit -m "feat(sections): stdlib SVG renderer for cross-section documents"
```

---

### Task 5: CLI `section create`

**Files:**
- Modify: `ocx_model_validator/cli.py`
- Test: `tests/test_cli_section.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_section.py`:

```python
"""CLI tests for the section subcommands."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

runner = CliRunner()


@pytest.fixture()
def model_310(stub_dir_310: Path) -> Path:
    return stub_dir_310 / "vessel.3docx"


def test_section_create_requires_exactly_one_position(model_310: Path):
    both = runner.invoke(app, ["section", "create", str(model_310),
                               "--frame", "FR20", "--x", "1000"])
    neither = runner.invoke(app, ["section", "create", str(model_310)])
    assert both.exit_code != 0
    assert neither.exit_code != 0


def test_section_create_no_geometry_exits_1(model_310: Path, tmp_path: Path):
    # the vessel stub has no intersectable geometry -> SectionError -> exit 1
    result = runner.invoke(app, ["section", "create", str(model_310),
                                 "--x", "1000",
                                 "--output", str(tmp_path / "s.json")])
    assert result.exit_code == 1


def test_section_create_missing_model_exits_nonzero():
    result = runner.invoke(app, ["section", "create", "no_such.3docx",
                                 "--x", "1000"])
    assert result.exit_code != 0


def test_default_output_name():
    from ocx_model_validator.cli import _default_section_output

    assert _default_section_output(Path("a/ship.3docx"), frame="FR20", x_mm=None) \
        == Path("ship-FR20.json")
    assert _default_section_output(Path("ship.3docx"), frame=None, x_mm=50_000.0) \
        == Path("ship-x50000.json")
    assert _default_section_output(Path("s.3docx"), frame="FR 2/b", x_mm=None) \
        == Path("s-FR_2_b.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_section.py -v`
Expected: FAIL — no `section` command / no `_default_section_output`

- [ ] **Step 3: Implement**

In `cli.py`, after the `report_app` registration add:

```python
section_app = typer.Typer(help="Create and plot cross sections.",
                          no_args_is_help=True)
app.add_typer(section_app, name="section")
```

Add helpers and the command (near the other commands; `re` is already
imported in `cli.py`):

```python
def _default_section_output(model: Path, frame: str | None,
                            x_mm: float | None) -> Path:
    tag = re.sub(r"[^\w.-]", "_", frame) if frame is not None else f"x{x_mm:g}"
    return Path(f"{model.stem}-{tag}.json")


@section_app.command("create")
def section_create_cmd(
    model: Path = _MODEL_ARG,
    frame: str | None = typer.Option(None, "--frame",
                                     help="Frame label, e.g. FR20."),
    x_mm: float | None = typer.Option(None, "--x",
                                      help="Section x-position in mm."),
    output: Path | None = typer.Option(None, "--output", "-o",
                                       help="Output JSON file."),
) -> None:
    """Build a transverse cross-section and write the JSON document."""
    from ocx_model_validator.exeptions import GeometryError, SectionError
    from ocx_model_validator.sections.document import build_document, save_document

    if (frame is None) == (x_mm is None):
        raise typer.BadParameter("Provide exactly one of --frame or --x")
    vessel = _load_vessel(model)
    try:
        doc = build_document(vessel, str(model), x_mm=x_mm, frame=frame)
    except (GeometryError, SectionError) as exc:
        logger.error("Cannot build section for {}: {}", model, exc)
        raise typer.Exit(code=1) from exc
    out = output or _default_section_output(model, frame, x_mm)
    try:
        save_document(doc, out)
    except OSError as exc:
        logger.error("Cannot write {}: {}", out, exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Section written to {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_section.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/cli.py tests/test_cli_section.py
git commit -m "feat(cli): add section create command"
```

---

### Task 6: CLI `section plot` + docs

**Files:**
- Modify: `ocx_model_validator/cli.py`, `README.md`,
  `.github/copilot-instructions.md`
- Test: `tests/test_cli_section.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_section.py`:

```python
import json


@pytest.fixture()
def section_json(tmp_path: Path) -> Path:
    doc = {
        "schema": "nh-cross-section/1",
        "source": {"file": "ship.3docx", "vessel_id": "V1", "generated": "t"},
        "frame_table": {"frame0_offset_mm": 0.0, "entries": [], "positions": []},
        "cross_section": {
            "x_mm": 50_000.0,
            "frame": "FR20",
            "stiffeners": [{
                "name": "L1", "y_mm": 2_000.0, "z_mm": 0.0, "panel": None,
                "profile_type": "FlatBar", "profile_dimensions": "200 x 20",
                "material_reh_mpa": None, "spacing_mm": None,
                "orientation": "Longitudinal", "web_angle_deg": 90.0,
                "web_dir_y": 0.0, "web_dir_z": 1.0,
            }],
            "plates": [{
                "name": "P1", "y1_mm": 0.0, "z1_mm": 0.0,
                "y2_mm": 10_000.0, "z2_mm": 0.0, "thickness_mm": 12.5,
                "material_reh_mpa": None, "panel": None,
            }],
        },
        "compartments": [],
        "warnings": [],
    }
    path = tmp_path / "section.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_section_plot_writes_svg(section_json: Path, tmp_path: Path):
    dest = tmp_path / "out.svg"
    result = runner.invoke(app, ["section", "plot", str(section_json),
                                 "--output", str(dest)])
    assert result.exit_code == 0
    svg = dest.read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert "Cross section at x=50000.0 mm (frame FR20)" in svg


def test_section_plot_default_output_is_svg_suffix(section_json: Path):
    result = runner.invoke(app, ["section", "plot", str(section_json)])
    assert result.exit_code == 0
    assert section_json.with_suffix(".svg").exists()


def test_section_plot_invalid_document_exits_1(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "wrong"}', encoding="utf-8")
    result = runner.invoke(app, ["section", "plot", str(bad)])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_section.py -v`
Expected: 3 new FAIL — no `plot` command

- [ ] **Step 3: Implement**

Add to `cli.py` below `section_create_cmd`:

```python
@section_app.command("plot")
def section_plot_cmd(
    section: Path = typer.Argument(..., exists=True, readable=True,
                                   help="Cross-section JSON document."),
    output: Path | None = typer.Option(None, "--output", "-o",
                                       help="Output SVG file."),
) -> None:
    """Plot a cross-section JSON document as an SVG."""
    from ocx_model_validator.exeptions import SectionError
    from ocx_model_validator.sections.document import load_document
    from ocx_model_validator.sections.svg_plot import render_svg

    try:
        doc = load_document(section)
    except (SectionError, ValueError) as exc:
        logger.error("Cannot load {}: {}", section, exc)
        raise typer.Exit(code=1) from exc
    out = output or section.with_suffix(".svg")
    try:
        out.write_text(render_svg(doc), encoding="utf-8")
    except OSError as exc:
        logger.error("Cannot write {}: {}", out, exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Plot written to {out}")
```

Note: `json.JSONDecodeError` is a subclass of `ValueError`, so malformed JSON
is covered by the except clause.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_section.py -v`
Expected: 7 PASSED. Then run the full suite: `uv run pytest` — all PASS.

- [ ] **Step 5: Update docs**

In `README.md`, extend the CLI code block (after the `validator report ...`
lines) with:

```bash
# cross sections: JSON document at a frame or x-position, then SVG plot
validator section create model.3docx --frame FR20 -o section.json
validator section create model.3docx --x 50000
validator section plot section.json -o section.svg
```

In `cli.py`'s module docstring, add the two `validator section ...` usage
lines. In `.github/copilot-instructions.md`, add the same two commands to the
CLI section.

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/cli.py tests/test_cli_section.py README.md .github/copilot-instructions.md
git commit -m "feat(cli): add section plot command"
```

---

### Task 7: Integration test and final verification

**Files:**
- Create: `tests/test_integration_section_plot.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration_section_plot.py` (same model convention as
`tests/test_sections_integration.py`):

```python
"""Integration: section create -> JSON -> plot -> SVG on the VLCC model."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

MODEL = Path(r"C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODEL.exists(), reason="VLCC reference model not present"),
]

runner = CliRunner()


def test_create_then_plot(tmp_path: Path):
    doc_path = tmp_path / "section.json"
    created = runner.invoke(app, ["section", "create", str(MODEL),
                                  "--x", "150000",
                                  "--output", str(doc_path)])
    assert created.exit_code == 0, created.output
    assert doc_path.exists()

    svg_path = tmp_path / "section.svg"
    plotted = runner.invoke(app, ["section", "plot", str(doc_path),
                                  "--output", str(svg_path)])
    assert plotted.exit_code == 0, plotted.output
    svg = svg_path.read_text(encoding="utf-8")
    assert svg.count('class="plate"') > 10
    assert svg.count('class="stiffener"') > 50
    assert "Plate thickness" in svg
```

If `--x 150000` intersects nothing on the model, pick the midship x from the
frame table instead: run
`uv run validator report frame-table <MODEL> --format markdown` and choose an
x between the first and last frame positions, then hard-code that value.

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/test_integration_section_plot.py -m integration -v`
Expected: 1 PASSED (or SKIP if the model is absent). This parses a large
model — allow several minutes.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest`
Expected: all PASS (integration tests deselected by default).

- [ ] **Step 4: Manual smoke test**

Run (only if the VLCC model exists):
`uv run validator section create C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx --x 150000 -o smoke.json`
then `uv run validator section plot smoke.json` and confirm `smoke.svg` opens
as a sensible section plot. Delete `smoke.json`/`smoke.svg` afterwards.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration_section_plot.py
git commit -m "test(sections): integration test for section create + plot"
```
