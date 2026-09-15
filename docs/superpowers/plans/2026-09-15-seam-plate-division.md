# Seam-Based Plate Division Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Divide exported 2DLX/HMX PLATEs at seam positions along each panel chain, matching Nauticus Hull's implicit seam encoding (spec: `docs/superpowers/specs/2026-09-15-seam-plate-division-design.md`).

**Architecture:** The section builder intersects each panel's `IrSeam.trace_line` with the section plane and records `SectionSeam` points on `CrossSection.seams` (also serialized into the JSON document). The shared exporter (`hmx_export.py`, used by both HMX and 2DLX) projects those points onto each `_PanelChain` as arclength stations and emits one PLATE per seam-to-seam span (properties from the plate at the span midpoint), leaving SEGMENT emission untouched.

**Tech Stack:** Python 3 (uv-managed), pytest, lxml. All commands run from the repo root with `uv run`.

**Verification oracle:** `NAPA VLCC_Fr(x=160000).2dlx` at the repo root (Nauticus Hull's own export of the same section — untracked, do not delete or modify).

---

## File map

- Modify: `ocx_model_validator/sections/section_builder.py` — new `SectionSeam` dataclass, `CrossSection.seams` field, `_build_seams()`.
- Modify: `ocx_model_validator/sections/document.py` — serialize `seams` in the JSON `cross_section` block.
- Modify: `ocx_model_validator/sections/hmx_export.py` — `_station_and_distance()` (arc-aware projection, refactor of `_arc_position`), `_seam_stations()`, span-based `_append_plates()` + `_plate_at_station()` + `_warn_if_mixed_span()`, wiring in `_append_section_body` / `_append_panel`.
- Test: `tests/test_sections_builder.py`, `tests/test_sections_document.py`, `tests/test_hmx_export_helpers.py`, `tests/test_hmx_export.py` (one assertion update).

Key existing pieces you build on (all in `hmx_export.py` unless noted):

- `_Chain` — `points: list[(y, z)]`, `plates: list[SectionPlate]`, invariant `len(points) == len(plates) + 1`. Segment *i* runs `points[i] → points[i+1]` carrying `plates[i]`.
- `_PanelChain` — `name` (export PANEL name, may have `_2` suffix), `panel` (source panel name, matches `SectionPlate.panel` and will match `SectionSeam.panel`), `chain`.
- `_arc_length_of(plate, p1, p2)` — chord length, or arc length `R·θ` when `plate.radius_mm` is set.
- `_projection(point, p1, p2) -> (t, dist)` — clamped chord projection.
- `_arc_station_on_segment(plate, p1, p2, point, seg_len)` — arclength along an arc segment for a query point (already clamped to `[0, seg_len]`).
- `_arc_position(chain, y, z)` — nearest-station projection used for LSTIFF positions; picks the segment by **chord** distance, which is wrong for mid-arc points (task 3 fixes this).
- `intersect_curve_plane(curve, x_mm, to_mm, tol)` (`sections/geometry.py`) — returns `[(y_mm, z_mm), ...]`; raises `GeometryError` for malformed/unsupported curves; handles `IrCompositeCurve3D` recursively.
- `tests/section_fixtures.py` — `make_synthetic_vessel()`, `p()`, `q()`, `line(y, z, start_x=0.0, end_x=10.0)` (an `IrLine3D` in metres; `line(1.0, 0.0)` crosses the x=5 m plane at `(1000.0, 0.0)` mm).
- `tests/test_hmx_export_helpers.py` — module-level `plate(name, y1, z1, y2, z2, *, radius=None, center=None, panel="Panel")` helper returning a `SectionPlate` with `thickness_mm=10.0`, `material_reh_mpa=315.0`.

---

### Task 1: `SectionSeam` + `_build_seams` in the section builder

**Files:**
- Modify: `ocx_model_validator/sections/section_builder.py`
- Test: `tests/test_sections_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sections_builder.py` (it already imports `make_synthetic_vessel`, `line`, `p` from `tests.section_fixtures` and `build_cross_section`):

```python
def _vessel_with_seam(seam_trace):
    from dataclasses import replace as dc_replace
    from ocx_model_validator.model.ir.structural import IrSeam

    vessel = make_synthetic_vessel()
    vessel.seams["seam-1"] = IrSeam(id="seam-1", name="SM1", trace_line=seam_trace)
    vessel.panels["panel-a"] = dc_replace(vessel.panels["panel-a"], seam_ids=["seam-1"])
    return vessel


def test_build_cross_section_collects_seam_intersections() -> None:
    # line(1.0, 0.0) runs x=0..10 m at y=1 m, z=0: crosses the x=5000 mm plane once.
    vessel = _vessel_with_seam(line(1.0, 0.0))

    section = build_cross_section(vessel, 5000.0)

    assert len(section.seams) == 1
    seam = section.seams[0]
    assert seam.name == "SM1"
    assert seam.panel == "Panel A"
    assert seam.y_mm == pytest.approx(1000.0)
    assert seam.z_mm == pytest.approx(0.0)


def test_build_cross_section_skips_seam_missing_the_plane() -> None:
    vessel = _vessel_with_seam(line(1.0, 0.0, start_x=0.0, end_x=4.0))  # ends before x=5 m

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []


def test_build_cross_section_warns_on_seam_geometry_error() -> None:
    from ocx_model_validator.model.ir.geometry import IrLine3D

    # IrLine3D without a start point makes intersect_curve_plane raise GeometryError.
    vessel = _vessel_with_seam(IrLine3D(curve_length=None, start=None, end=p(10.0, 1.0, 0.0)))

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []
    assert any(w.startswith("seam SM1:") for w in section.warnings)


def test_build_cross_section_skips_seam_without_trace_line() -> None:
    vessel = _vessel_with_seam(None)

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []
    assert not any("seam" in w for w in section.warnings)
```

Note: `IrPanel` exposes `seam_ids: list[str]` and `IrVessel.seams: dict[str, IrSeam]` — both already exist. If `dataclasses.replace` fails because `IrPanel` is not frozen in this codebase, simply mutate: `vessel.panels["panel-a"].seam_ids.append("seam-1")` — check `model/ir/structural.py` and use whichever works.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sections_builder.py -q -k seam`
Expected: 4 failures — `AttributeError: 'CrossSection' object has no attribute 'seams'` (or similar).

- [ ] **Step 3: Implement `SectionSeam`, `CrossSection.seams`, `_build_seams`**

In `ocx_model_validator/sections/section_builder.py`:

1. Change the dataclasses import to include `field`:

```python
from dataclasses import dataclass, field, replace
```

2. Add after the `SectionPlate` dataclass:

```python
@dataclass(frozen=True)
class SectionSeam:
    """A panel seam's intersection with the section plane."""
    name: str | None
    panel: str | None
    y_mm: float
    z_mm: float
```

3. Add to `CrossSection` (after `warnings`):

```python
    seams: list[SectionSeam] = field(default_factory=list)
```

4. In `build_cross_section`, after `plates = _build_plates(...)`:

```python
    seams = _build_seams(vessel, x_mm, to_mm, tol, warnings)
```

and pass `seams=seams` to the `CrossSection(...)` constructor call.

5. Add the builder function (place it after `_build_plates`):

```python
def _build_seams(
    vessel: IrVessel,
    x_mm: float,
    to_mm,
    tol: float,
    warnings: list[str],
) -> list[SectionSeam]:
    """Intersect each panel's seam tracelines with the section plane.

    Transverse seams parallel to the plane simply produce no hits; a seam
    traceline may cross the plane more than once (one SectionSeam per hit).
    """
    result: list[SectionSeam] = []
    for panel in vessel.panels.values():
        panel_name = _panel_name(panel)
        for seam_id in panel.seam_ids:
            seam = vessel.seams.get(seam_id)
            if seam is None or seam.trace_line is None:
                continue
            name = seam.name or seam.id
            try:
                hits = intersect_curve_plane(seam.trace_line, x_mm, to_mm, tol)
            except GeometryError as exc:
                warnings.append(f"seam {name}: {exc}")
                continue
            for y_mm, z_mm in hits:
                result.append(SectionSeam(name=name, panel=panel_name, y_mm=y_mm, z_mm=z_mm))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sections_builder.py -q`
Expected: all pass (new seam tests + existing).

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/section_builder.py tests/test_sections_builder.py
git commit -m "Collect panel seam intersections on CrossSection

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Serialize seams in the JSON section document

**Files:**
- Modify: `ocx_model_validator/sections/document.py`
- Test: `tests/test_sections_document.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sections_document.py` (it already imports `make_synthetic_vessel` and `q` from `tests.section_fixtures`; check the top of the file for how `build_document` is imported and reuse that):

```python
def test_document_includes_seams_block() -> None:
    from dataclasses import replace as dc_replace

    from ocx_model_validator.model.ir.structural import IrSeam
    from tests.section_fixtures import line

    vessel = make_synthetic_vessel()
    vessel.seams["seam-1"] = IrSeam(id="seam-1", name="SM1", trace_line=line(1.0, 0.0))
    vessel.panels["panel-a"] = dc_replace(vessel.panels["panel-a"], seam_ids=["seam-1"])

    doc = build_document(vessel, "model.3docx", x_mm=5000.0)

    assert doc["cross_section"]["seams"] == [
        {"name": "SM1", "panel": "Panel A", "y_mm": 1000.0, "z_mm": 0.0}
    ]
```

(Adjust the `IrPanel` mutation the same way as in Task 1 if `replace` doesn't apply.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sections_document.py::test_document_includes_seams_block -q`
Expected: FAIL with `KeyError: 'seams'`.

- [ ] **Step 3: Implement**

In `ocx_model_validator/sections/document.py`, inside `build_document`, add one line to the `"cross_section"` dict after the `"plates"` entry:

```python
            "seams": [_dataclass_dict(seam) for seam in cross_section.seams],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sections_document.py -q`
Expected: all pass. (`_round_floats` already rounds the values; `_dataclass_dict` serializes any frozen dataclass.)

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/document.py tests/test_sections_document.py
git commit -m "Serialize seam points in the cross-section JSON document

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Arc-aware `_station_and_distance` in the exporter

`_arc_position` picks the nearest segment by **chord** distance. For a point in the middle of the bilge arc (R≈2600 mm) the chord distance is the sagitta — hundreds of mm — so a 50 mm seam snap tolerance would wrongly reject seams on arcs. Introduce `_station_and_distance` that measures radial distance to the circle on arc segments, and make `_arc_position` a thin wrapper.

**Files:**
- Modify: `ocx_model_validator/sections/hmx_export.py` (replace the body of `_arc_position`, ~line 334)
- Test: `tests/test_hmx_export_helpers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hmx_export_helpers.py` (uses the module's existing `plate()` helper):

```python
def test_station_and_distance_uses_radial_distance_on_arcs() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    # Quarter circle R=1000 centered at origin, from (1000, 0) to (0, 1000).
    arc = plate("bilge", 1000.0, 0.0, 0.0, 1000.0, radius=1000.0, center=(0.0, 0.0))
    chain = _Chain(points=[(1000.0, 0.0), (0.0, 1000.0)], plates=[arc])

    # Point exactly on the arc at 45 degrees: chord distance would be the
    # sagitta (~293 mm) but the radial distance is 0.
    on_arc = (1000.0 * math.cos(math.pi / 4), 1000.0 * math.sin(math.pi / 4))
    station, dist = _station_and_distance(chain, on_arc)

    assert dist == pytest.approx(0.0, abs=1e-6)
    assert station == pytest.approx(1000.0 * math.pi / 4, rel=1e-6)


def test_station_and_distance_on_straight_segment() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    chain = _Chain(
        points=[(0.0, 0.0), (1000.0, 0.0), (1000.0, 500.0)],
        plates=[plate("a", 0.0, 0.0, 1000.0, 0.0), plate("b", 1000.0, 0.0, 1000.0, 500.0)],
    )

    station, dist = _station_and_distance(chain, (1000.0, 200.0))

    assert station == pytest.approx(1200.0)
    assert dist == pytest.approx(0.0, abs=1e-9)


def test_station_and_distance_reports_offset_distance() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    chain = _Chain(points=[(0.0, 0.0), (1000.0, 0.0)], plates=[plate("a", 0.0, 0.0, 1000.0, 0.0)])

    station, dist = _station_and_distance(chain, (500.0, 80.0))

    assert station == pytest.approx(500.0)
    assert dist == pytest.approx(80.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hmx_export_helpers.py -q -k station_and_distance`
Expected: 3 failures — `ImportError: cannot import name '_station_and_distance'`.

- [ ] **Step 3: Implement**

In `ocx_model_validator/sections/hmx_export.py`, replace the entire `_arc_position` function (~line 334) with:

```python
def _arc_position(_chain: _Chain, y: float, z: float) -> float:
    """Return arc-length station of the nearest projection on ``chain``."""
    return _station_and_distance(_chain, (y, z))[0]


def _station_and_distance(chain: _Chain, point: tuple[float, float]) -> tuple[float, float]:
    """Return ``(arc-length station, distance)`` of the nearest point on ``chain``.

    Straight segments use clamped chord projection; arc segments use radial
    distance to the circle when the point projects inside the arc sweep, so
    mid-arc points are not penalized by chord sagitta.
    """
    best_station = 0.0
    best_dist = float("inf")
    prefix = 0.0
    for plate, p1, p2 in zip(chain.plates, chain.points, chain.points[1:]):
        seg_len = _arc_length_of(plate, p1, p2)
        is_arc = (
            plate.radius_mm is not None
            and abs(plate.radius_mm) > 0.0
            and plate.arc_center_y_mm is not None
            and plate.arc_center_z_mm is not None
        )
        if is_arc:
            center = (plate.arc_center_y_mm, plate.arc_center_z_mm)
            swept = _arc_station_on_segment(plate, p1, p2, point, seg_len)
            if 0.0 < swept < seg_len:
                dist = abs(_distance(center, point) - abs(plate.radius_mm))
            else:
                d1 = _distance(point, p1)
                d2 = _distance(point, p2)
                swept, dist = (0.0, d1) if d1 <= d2 else (seg_len, d2)
            station = prefix + swept
        else:
            t, dist = _projection(point, p1, p2)
            station = prefix + t * seg_len
        if dist < best_dist:
            best_dist = dist
            best_station = station
        prefix += seg_len
    return best_station, best_dist
```

- [ ] **Step 4: Run the helper and export test files**

Run: `uv run pytest tests/test_hmx_export_helpers.py tests/test_hmx_export.py tests/test_dlx_export.py -q`
Expected: all pass — `_arc_position` callers (LSTIFF positioning) keep working; on straight segments the behavior is identical, on arcs it is strictly more accurate.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/hmx_export.py tests/test_hmx_export_helpers.py
git commit -m "Add arc-aware chain projection with distance

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: `_seam_stations` — project seam points to chain stations

**Files:**
- Modify: `ocx_model_validator/sections/hmx_export.py`
- Test: `tests/test_hmx_export_helpers.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hmx_export_helpers.py`:

```python
def seam(y: float, z: float, panel: str = "Panel"):
    from ocx_model_validator.sections.section_builder import SectionSeam

    return SectionSeam(name="SM", panel=panel, y_mm=y, z_mm=z)


def test_seam_stations_sorted_interior_stations() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _seam_stations

    chain = _Chain(
        points=[(0.0, 0.0), (5000.0, 0.0), (5000.0, 3000.0)],
        plates=[plate("a", 0.0, 0.0, 5000.0, 0.0), plate("b", 5000.0, 0.0, 5000.0, 3000.0)],
    )
    seams = [seam(5000.0, 1000.0), seam(2000.0, 0.0)]

    assert _seam_stations(chain, seams) == pytest.approx([2000.0, 6000.0])


def test_seam_stations_ignores_far_points() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _seam_stations

    chain = _Chain(points=[(0.0, 0.0), (5000.0, 0.0)], plates=[plate("a", 0.0, 0.0, 5000.0, 0.0)])

    # 80 mm off the chain: beyond the 50 mm snap tolerance.
    assert _seam_stations(chain, [seam(2000.0, 80.0)]) == []
    # 30 mm off: snapped.
    assert _seam_stations(chain, [seam(2000.0, 30.0)]) == pytest.approx([2000.0])


def test_seam_stations_drops_chain_ends_and_duplicates() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _seam_stations

    chain = _Chain(points=[(0.0, 0.0), (5000.0, 0.0)], plates=[plate("a", 0.0, 0.0, 5000.0, 0.0)])
    seams = [
        seam(0.5, 0.0),       # within 1 mm of the chain start -> dropped
        seam(4999.5, 0.0),    # within 1 mm of the chain end -> dropped
        seam(2000.0, 0.0),
        seam(2000.4, 0.0),    # duplicate of the previous station -> dropped
    ]

    assert _seam_stations(chain, seams) == pytest.approx([2000.0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hmx_export_helpers.py -q -k seam_stations`
Expected: 3 failures — `ImportError: cannot import name '_seam_stations'`.

- [ ] **Step 3: Implement**

In `ocx_model_validator/sections/hmx_export.py`:

1. Extend the existing `section_builder` import with `SectionSeam` (find the `from ocx_model_validator.sections.section_builder import ...` line and add it).

2. Add after `_station_and_distance`:

```python
def _seam_stations(
    chain: _Chain,
    seams: Iterable[SectionSeam],
    snap_tol: float = 50.0,
    end_tol: float = 1.0,
) -> list[float]:
    """Project seam points onto the chain as sorted interior arclength stations.

    Points farther than ``snap_tol`` from the chain belong to another
    disconnected part of the panel (or the other centerline half) and are
    ignored; stations within ``end_tol`` of the chain ends or of each other
    are dropped so no zero-width plates are emitted.
    """
    total = sum(
        _arc_length_of(plate, p1, p2)
        for plate, p1, p2 in zip(chain.plates, chain.points, chain.points[1:])
    )
    stations: list[float] = []
    for seam in seams:
        station, dist = _station_and_distance(chain, (seam.y_mm, seam.z_mm))
        if dist > snap_tol or station <= end_tol or station >= total - end_tol:
            continue
        stations.append(station)
    stations.sort()
    deduped: list[float] = []
    for station in stations:
        if not deduped or station - deduped[-1] > end_tol:
            deduped.append(station)
    return deduped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hmx_export_helpers.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/hmx_export.py tests/test_hmx_export_helpers.py
git commit -m "Project seam points onto panel chains as arclength stations

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Span-based PLATE emission + wiring

**Files:**
- Modify: `ocx_model_validator/sections/hmx_export.py` (`_append_plates` ~line 702, `_append_panel` ~line 644, `_append_section_body` ~line 557)
- Test: `tests/test_hmx_export_helpers.py`, `tests/test_hmx_export.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hmx_export_helpers.py`:

```python
def _plates_block(chain, stations, warnings=None):
    from lxml import etree

    from ocx_model_validator.sections.hmx_export import _append_plates

    panel = etree.Element("PANEL")
    _append_plates(panel, chain, None, [] if warnings is None else warnings, stations)
    return panel.findall("./PLATES/PLATE")


def test_append_plates_emits_one_plate_per_seam_span() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain

    # Three collinear 3000 mm plates, seams at 4000 and 6500.
    chain = _Chain(
        points=[(0.0, 0.0), (3000.0, 0.0), (6000.0, 0.0), (9000.0, 0.0)],
        plates=[
            plate("a", 0.0, 0.0, 3000.0, 0.0),
            plate("b", 3000.0, 0.0, 6000.0, 0.0),
            plate("c", 6000.0, 0.0, 9000.0, 0.0),
        ],
    )

    elements = _plates_block(chain, [4000.0, 6500.0])

    assert [float(e.get("Width")) for e in elements] == pytest.approx([4000.0, 2500.0, 2500.0])
    assert all(e.get("RefCode") == "CURVE" for e in elements)
    assert all(e.get("Thickness") == "10" for e in elements)


def test_append_plates_without_stations_merges_whole_chain() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain

    chain = _Chain(
        points=[(0.0, 0.0), (3000.0, 0.0), (6000.0, 0.0)],
        plates=[plate("a", 0.0, 0.0, 3000.0, 0.0), plate("b", 3000.0, 0.0, 6000.0, 0.0)],
    )

    elements = _plates_block(chain, [])

    assert len(elements) == 1
    assert float(elements[0].get("Width")) == pytest.approx(6000.0)


def test_append_plates_arc_span_width_is_arc_length() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain

    arc = plate("bilge", 1000.0, 0.0, 0.0, 1000.0, radius=1000.0, center=(0.0, 0.0))
    chain = _Chain(points=[(1000.0, 0.0), (0.0, 1000.0)], plates=[arc])

    elements = _plates_block(chain, [])

    assert float(elements[0].get("Width")) == pytest.approx(1000.0 * math.pi / 2, rel=1e-4)


def test_append_plates_mixed_span_uses_midpoint_plate_and_warns() -> None:
    from dataclasses import replace

    from ocx_model_validator.sections.hmx_export import _Chain

    thin = plate("thin", 0.0, 0.0, 1000.0, 0.0)
    thick = replace(plate("thick", 1000.0, 0.0, 5000.0, 0.0), thickness_mm=20.0)
    chain = _Chain(points=[(0.0, 0.0), (1000.0, 0.0), (5000.0, 0.0)], plates=[thin, thick])
    warnings: list[str] = []

    elements = _plates_block(chain, [], warnings)

    # Span midpoint at s=2500 lies on "thick".
    assert elements[0].get("Thickness") == "20"
    assert len(warnings) == 1
    assert "mixes plate properties" in warnings[0]
    assert "thick" in warnings[0]


def test_append_plates_uniform_span_does_not_warn() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain

    chain = _Chain(
        points=[(0.0, 0.0), (3000.0, 0.0), (6000.0, 0.0)],
        plates=[plate("a", 0.0, 0.0, 3000.0, 0.0), plate("b", 3000.0, 0.0, 6000.0, 0.0)],
    )
    warnings: list[str] = []

    _plates_block(chain, [], warnings)

    assert warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hmx_export_helpers.py -q -k append_plates`
Expected: 5 failures — `TypeError: _append_plates() takes 4 positional arguments but 5 were given`.

- [ ] **Step 3: Implement span-based `_append_plates`**

In `ocx_model_validator/sections/hmx_export.py`, replace the entire `_append_plates` function with:

```python
def _append_plates(
    panel: etree._Element,
    chain: _Chain,
    materials: _MaterialIds | None,
    warnings: list[str],
    stations: list[float],
) -> None:
    """Emit the PLATES block: one PLATE per seam-to-seam span.

    Nauticus divides plates by seam positions along the panel shape curve,
    independent of SEGMENT geometry. Spans between consecutive stations merge
    the underlying OCX plates; Thickness/Yield come from the plate at the
    span's arclength midpoint (a warning is emitted if the span mixes
    differing plate properties). No stations -> one PLATE for the whole chain.
    """
    plates_el = etree.SubElement(panel, "PLATES")
    side = _side(chain)
    seg_lens = [
        _arc_length_of(plate, p1, p2)
        for plate, p1, p2 in zip(chain.plates, chain.points, chain.points[1:])
    ]
    bounds = [0.0, *stations, sum(seg_lens)]
    for s1, s2 in zip(bounds, bounds[1:]):
        span_plate = _plate_at_station(chain, seg_lens, (s1 + s2) / 2.0)
        _warn_if_mixed_span(chain, seg_lens, s1, s2, span_plate, warnings)
        yield_mpa = _yield_or_default(span_plate.material_reh_mpa)
        thickness = _required_numeric(
            span_plate.thickness_mm,
            0.0,
            f"plate {span_plate.name}: thickness is missing; emitted 0",
            warnings,
        )
        attrs = {
            "Width": _fmt(s2 - s1),
            "RefCode": "CURVE",
            "Thickness": _fmt(thickness),
            "Yield": _fmt(yield_mpa),
        }
        if materials is not None:
            attrs["MaterialId"] = materials.id_for(yield_mpa)
        attrs["Material"] = "STDSTEEL"
        attrs["Side"] = side
        etree.SubElement(plates_el, "PLATE", **attrs)


def _plate_at_station(chain: _Chain, seg_lens: list[float], station: float) -> SectionPlate:
    """Return the chain plate whose segment contains the arclength station."""
    prefix = 0.0
    for plate, seg_len in zip(chain.plates, seg_lens):
        if station <= prefix + seg_len:
            return plate
        prefix += seg_len
    return chain.plates[-1]


def _warn_if_mixed_span(
    chain: _Chain,
    seg_lens: list[float],
    s1: float,
    s2: float,
    span_plate: SectionPlate,
    warnings: list[str],
) -> None:
    """Warn once if plates overlapping ``[s1, s2]`` differ from the midpoint plate."""
    prefix = 0.0
    for plate, seg_len in zip(chain.plates, seg_lens):
        lo, hi = prefix, prefix + seg_len
        prefix = hi
        if hi <= s1 + 1e-6 or lo >= s2 - 1e-6:
            continue
        if (plate.thickness_mm, plate.material_reh_mpa) != (
            span_plate.thickness_mm,
            span_plate.material_reh_mpa,
        ):
            warnings.append(
                f"panel {span_plate.panel or span_plate.name}: seam span at "
                f"s={_fmt((s1 + s2) / 2.0)} mixes plate properties; "
                f"using {span_plate.name}"
            )
            return
```

- [ ] **Step 4: Wire seam stations through the panel emission**

Still in `hmx_export.py`:

1. In `_append_panel` (~line 644), add a `stations: list[float]` parameter after `chain` and pass it through:

```python
def _append_panel(
    parent: etree._Element,
    name: str,
    chain: _Chain,
    stations: list[float],
    stiffeners: list[SectionStiffener],
    ...
```

and change the `_append_plates` call inside it to:

```python
    _append_plates(panel, chain, materials, warnings, stations)
```

2. In `_append_section_body`, replace the chain loop with:

```python
    chains = _panel_chains(cross_section.plates)
    assigned_stiffeners = _assign_stiffeners_to_chains(cross_section.stiffeners, chains)
    for index, item in enumerate(chains):
        panel_seams = [seam for seam in cross_section.seams if seam.panel == item.panel]
        _append_panel(
            parent,
            item.name,
            item.chain,
            _seam_stations(item.chain, panel_seams),
            assigned_stiffeners.get(index, []),
            extent,
            comp_boxes,
            cross_section.x_mm,
            stdspan,
            stdspace,
            materials,
            warnings,
            lstiff_types,
        )
```

Centerline halves need no special handling: stations come from projection onto the already-split chain, and the 50 mm snap rejects points on the other half.

- [ ] **Step 5: Update the one existing assertion that legitimately changes**

In `tests/test_hmx_export.py` (~line 132), the closed-ring test asserts `len(panel.findall("./PLATES/PLATE")) == len(segments)`. The ring plates all share thickness 10 / yield 315 and the vessel has no seams, so each half now merges into **one** PLATE. Change that assertion to:

```python
        # No seams in the synthetic vessel: each chain merges into one PLATE.
        plate_elements = panel.findall("./PLATES/PLATE")
        assert len(plate_elements) == 1
        expected_length = sum(
            math.hypot(
                float(b.get("Y")) - float(a.get("Y")),
                float(b.get("Z")) - float(a.get("Z")),
            )
            for a, b in zip([node, *segments], segments)
        )
        assert float(plate_elements[0].get("Width")) == pytest.approx(expected_length)
```

Add `import math` at the top of `tests/test_hmx_export.py` if it is not already imported. If other tests in `tests/test_hmx_export.py` / `tests/test_dlx_export.py` fail on PLATE counts, apply the same reasoning: PLATE count per PANEL is now `len(stations) + 1`, and total Width per PANEL equals the chain length — update expectations accordingly, never weaken Thickness/Yield assertions.

- [ ] **Step 6: Run the affected test files**

Run: `uv run pytest tests/test_hmx_export_helpers.py tests/test_hmx_export.py tests/test_dlx_export.py tests/test_cli_section.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add ocx_model_validator/sections/hmx_export.py tests/test_hmx_export.py tests/test_hmx_export_helpers.py
git commit -m "Divide exported PLATEs at seam stations along panel chains

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Full suite + oracle verification against the NH baseline

**Files:**
- No source changes expected (fixes only if verification reveals bugs).
- Uses: `models/D-VLCC_1-HOLD-OCX-simple_v3.3docx`, `NAPA VLCC_Fr(x=160000).2dlx` (repo root, untracked — do not delete).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all pass (was 458 passed, 2 skipped before this work; now ~470).

- [ ] **Step 2: Regenerate the 2DLX export**

```bash
uv run validator section export "models\D-VLCC_1-HOLD-OCX-simple_v3.3docx" --x 160000 -o "D-VLCC_1-HOLD-OCX-simple_v3-x160000.2dlx"
```

Expected: `2DLX section written to D-VLCC_1-HOLD-OCX-simple_v3-x160000.2dlx`.

- [ ] **Step 3: Compare per-PANEL plate widths against the NH baseline**

Run this comparison script (PowerShell here-string piped to python):

```powershell
@'
import xml.etree.ElementTree as ET

def panels(path):
    result = {}
    for p in ET.parse(path).getroot().iter("PANEL"):
        name = p.get("Name")
        if name is None:
            idd = p.find(".//IDDATA")
            name = idd.get("Name") if idd is not None else "?"
        result[name] = sorted(round(float(pl.get("Width")), 0) for pl in p.findall(".//PLATE"))
    return result

ours = panels("D-VLCC_1-HOLD-OCX-simple_v3-x160000.2dlx")
base = panels("NAPA VLCC_Fr(x=160000).2dlx")
for name in sorted(set(ours) | set(base)):
    o, b = ours.get(name), base.get(name)
    mark = "OK " if o == b else "DIFF"
    print(f"{mark} {name}: ours={o} base={b}")
'@ | uv run python -
```

Expected outcome (this is the acceptance oracle):
- DECK / DECK_2: **10 plates** each, including one ≈13764 mm span and five 4536 mm spans.
- Girder/stringer panels (STG_*, BGI_*): **1 plate** each.
- Side shell (SHELLS/SHELLP): plate widths matching the baseline strakes within ~1 mm.
- Small residual width differences (< a few mm) from tessellation are acceptable; different plate **counts** are not.

If a panel shows the wrong count, debug before proceeding: check whether the seam points exist in the JSON (`uv run validator section create "models\D-VLCC_1-HOLD-OCX-simple_v3.3docx" --x 160000 -o tmp-seams.json`, inspect `cross_section.seams`, then delete `tmp-seams.json`), then whether the station projection snapped them (50 mm tolerance vs actual offset). Follow superpowers:systematic-debugging — no tolerance tweaking without evidence.

- [ ] **Step 4: Commit the regenerated artifact reference (code only)**

Only commit source/test changes made during debugging (the `.2dlx` outputs and baseline stay untracked):

```bash
git status --short
git add <any fixed source/test files>
git commit -m "Verify seam-divided plates against Nauticus baseline

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

(Skip the commit if Step 3 passed with no code changes.)

- [ ] **Step 5: Hand off for user acceptance**

Ask the user to import `D-VLCC_1-HOLD-OCX-simple_v3-x160000.2dlx` into Nauticus Hull and confirm the plate strakes now match the NH baseline.
