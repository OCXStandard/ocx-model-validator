# EPP-Based Plates in Cross-Section JSON Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw plate segments in the cross-section JSON document with elementary plate panels (EPPs) split at longitudinal stiffener intersections.

**Architecture:** Extract per-segment arc/chord geometry helpers from `hmx_export.py` into a new shared `sections/segment_math.py`. A new `sections/epp.py` splits each `SectionPlate` at the stations of same-panel stiffeners and emits frozen `EppPlate` dataclasses carrying bound-stiffener names and breadth. `sections/document.py` serializes EPPs as the `plates` array and bumps the schema to `nh-cross-section/2`. HMX/2DLX exports keep consuming unsplit `CrossSection.plates`.

**Tech Stack:** Python 3 dataclasses, stdlib `math`, pytest, `uv` for all commands. Spec: `docs/superpowers/specs/2026-09-16-epp-json-export-design.md`.

**Conventions:** All commands run from the repo root. Every commit message ends with the trailer:
`Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

---

## File Structure

- Create: `ocx_model_validator/sections/segment_math.py` — per-segment geometry (distance, projection, arc length, station projection, point-at-station). No project imports; pure math over duck-typed "arc segment" objects.
- Create: `ocx_model_validator/sections/epp.py` — `EppPlate` dataclass + `split_plates_to_epps()`. Imports `segment_math` and `section_builder` dataclasses only.
- Modify: `ocx_model_validator/sections/hmx_export.py` — delete its private copies of the extracted helpers; import them from `segment_math` under the old private names (call sites untouched).
- Modify: `ocx_model_validator/sections/document.py` — bump `SCHEMA`, serialize EPPs as `plates`.
- Create: `tests/test_segment_math.py`, `tests/test_epp.py`.
- Modify: `tests/test_sections_document.py`, `tests/test_cli_section.py`, `tests/test_sections_integration.py`, `tests/test_svg_plot.py` — schema string bump + new document-level assertions.

---

### Task 1: `segment_math.py` — shared per-segment geometry

The functions `_distance`, `_projection`, `_minor_sweep`, `_arc_length_of` (hmx_export.py:1284–1302, 1338–1342, 311–330) and `_arc_station_on_segment` (hmx_export.py:1305–1335) move here verbatim (public names, no leading underscore). Two functions are new: `project_point` (single-segment version of the arc branch of `_station_and_distance`, hmx_export.py:339–375) and `point_at_station` (inverse mapping, station → point).

**Files:**
- Create: `tests/test_segment_math.py`
- Create: `ocx_model_validator/sections/segment_math.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_segment_math.py`:

```python
"""Tests for shared per-segment geometry helpers."""
from math import isclose, pi, sqrt

import pytest

from ocx_model_validator.sections.section_builder import SectionPlate
from ocx_model_validator.sections.segment_math import (
    arc_length,
    distance,
    minor_sweep,
    point_at_station,
    project_point,
    projection,
)


def _plate(radius=None, cy=None, cz=None) -> SectionPlate:
    return SectionPlate(
        name="P",
        y1_mm=0.0,
        z1_mm=0.0,
        y2_mm=0.0,
        z2_mm=0.0,
        thickness_mm=None,
        material_reh_mpa=None,
        panel=None,
        radius_mm=radius,
        arc_center_y_mm=cy,
        arc_center_z_mm=cz,
    )


# Quarter arc: center (0, 0), radius 1000, from (1000, 0) to (0, 1000).
ARC = _plate(radius=1000.0, cy=0.0, cz=0.0)
ARC_P1 = (1000.0, 0.0)
ARC_P2 = (0.0, 1000.0)
ARC_LEN = pi / 2.0 * 1000.0


def test_distance() -> None:
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0


def test_projection_interior_point() -> None:
    t, dist = projection((5.0, 2.0), (0.0, 0.0), (10.0, 0.0))
    assert isclose(t, 0.5)
    assert isclose(dist, 2.0)


def test_projection_clamps_to_endpoints() -> None:
    t, dist = projection((-3.0, 4.0), (0.0, 0.0), (10.0, 0.0))
    assert t == 0.0
    assert isclose(dist, 5.0)


def test_minor_sweep_wraps_to_signed_minor_angle() -> None:
    assert isclose(minor_sweep(0.0, pi / 2.0), pi / 2.0)
    assert isclose(minor_sweep(pi / 2.0, 0.0), -pi / 2.0)


def test_arc_length_straight_is_chord() -> None:
    assert isclose(arc_length(_plate(), (0.0, 0.0), (3.0, 4.0)), 5.0)


def test_arc_length_quarter_circle() -> None:
    assert isclose(arc_length(ARC, ARC_P1, ARC_P2), ARC_LEN, rel_tol=1e-9)


def test_project_point_straight() -> None:
    station, dist = project_point(_plate(), (0.0, 0.0), (3000.0, 0.0), (1000.0, 5.0))
    assert isclose(station, 1000.0)
    assert isclose(dist, 5.0)


def test_project_point_mid_arc_uses_radial_distance() -> None:
    r = 1000.0 / sqrt(2.0)
    station, dist = project_point(ARC, ARC_P1, ARC_P2, (r, r))
    assert isclose(station, ARC_LEN / 2.0, rel_tol=1e-6)
    assert isclose(dist, 0.0, abs_tol=1e-6)


def test_project_point_beyond_arc_snaps_to_nearest_end() -> None:
    station, dist = project_point(ARC, ARC_P1, ARC_P2, (1010.0, -50.0))
    assert station == 0.0
    assert isclose(dist, distance((1010.0, -50.0), ARC_P1))


def test_point_at_station_straight() -> None:
    y, z = point_at_station(_plate(), (0.0, 0.0), (3000.0, 0.0), 1000.0)
    assert isclose(y, 1000.0)
    assert isclose(z, 0.0)


def test_point_at_station_arc_midpoint() -> None:
    y, z = point_at_station(ARC, ARC_P1, ARC_P2, ARC_LEN / 2.0)
    r = 1000.0 / sqrt(2.0)
    assert isclose(y, r, rel_tol=1e-9)
    assert isclose(z, r, rel_tol=1e-9)


def test_point_at_station_clamps_and_handles_zero_length() -> None:
    assert point_at_station(_plate(), (5.0, 5.0), (5.0, 5.0), 100.0) == (5.0, 5.0)
    y, z = point_at_station(_plate(), (0.0, 0.0), (10.0, 0.0), 99.0)
    assert isclose(y, 10.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_segment_math.py -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'ocx_model_validator.sections.segment_math'`

- [ ] **Step 3: Create the module**

Create `ocx_model_validator/sections/segment_math.py`:

```python
"""Per-segment 2D geometry helpers shared by section exports.

Straight segments are chords; segments with ``radius_mm`` are circular arcs.
Arcs are assumed minor (<180°, chord-recoverable) per the OCX bilge use case:
bilge arcs are quarter-to-semi circles, and the chord formula degrades at
exactly 180°.
"""
from __future__ import annotations

from math import asin, atan2, cos, hypot, pi, sin, tau
from typing import Protocol

Point = tuple[float, float]


class ArcSegment(Protocol):
    """Anything carrying optional circular-arc data (SectionPlate, EppPlate)."""

    radius_mm: float | None
    arc_center_y_mm: float | None
    arc_center_z_mm: float | None


def distance(a: Point, b: Point) -> float:
    return hypot(b[0] - a[0], b[1] - a[1])


def projection(point: Point, p1: Point, p2: Point) -> tuple[float, float]:
    """Return ``(t, distance)`` of the clamped chord projection of ``point``."""
    vx = p2[0] - p1[0]
    vz = p2[1] - p1[1]
    length_sq = vx * vx + vz * vz
    if length_sq <= 0.0:
        return (0.0, distance(point, p1))

    t = ((point[0] - p1[0]) * vx + (point[1] - p1[1]) * vz) / length_sq
    t = max(0.0, min(1.0, t))
    projected = (p1[0] + t * vx, p1[1] + t * vz)
    return (t, distance(point, projected))


def minor_sweep(start_angle: float, end_angle: float) -> float:
    """Return the signed minor sweep from ``start_angle`` to ``end_angle``."""
    delta = (end_angle - start_angle) % tau
    if delta > pi:
        delta -= tau
    return delta


def is_arc(segment: ArcSegment) -> bool:
    return (
        segment.radius_mm is not None
        and abs(segment.radius_mm) > 0.0
        and segment.arc_center_y_mm is not None
        and segment.arc_center_z_mm is not None
    )


def arc_length(segment: ArcSegment, p1: Point, p2: Point) -> float:
    """Return chord length for straight segments or circular arc length."""
    chord = distance(p1, p2)
    if segment.radius_mm is None:
        return chord

    radius = abs(segment.radius_mm)
    if radius <= 0.0:
        return chord

    theta = 2.0 * asin(min(1.0, chord / (2.0 * radius)))
    return radius * theta


def arc_station_on_segment(
    segment: ArcSegment,
    p1: Point,
    p2: Point,
    point: Point,
    seg_len: float,
) -> float:
    """Return the clamped arc-length station of ``point`` swept from ``p1``."""
    radius = abs(segment.radius_mm or 0.0)
    if radius <= 0.0:
        return 0.0

    cy = segment.arc_center_y_mm
    cz = segment.arc_center_z_mm
    if cy is None or cz is None:
        return 0.0

    query_radius = distance((cy, cz), point)
    if query_radius <= 0.0:
        return 0.0

    start_angle = atan2(p1[1] - cz, p1[0] - cy)
    end_angle = atan2(p2[1] - cz, p2[0] - cy)
    query_angle = atan2(point[1] - cz, point[0] - cy)

    total = minor_sweep(start_angle, end_angle)
    query_delta = minor_sweep(start_angle, query_angle)
    swept = query_delta if total >= 0.0 else -query_delta

    theta_total = min(abs(total), seg_len / radius if radius > 0.0 else 0.0)
    swept = max(0.0, min(theta_total, swept))
    return radius * swept


def project_point(
    segment: ArcSegment,
    p1: Point,
    p2: Point,
    point: Point,
) -> tuple[float, float]:
    """Return ``(arc-length station, distance)`` of ``point`` on one segment.

    Straight segments use clamped chord projection; arc segments use radial
    distance to the circle when the point projects inside the arc sweep, and
    snap to the nearest endpoint otherwise.
    """
    seg_len = arc_length(segment, p1, p2)
    if is_arc(segment):
        center = (segment.arc_center_y_mm, segment.arc_center_z_mm)
        swept = arc_station_on_segment(segment, p1, p2, point, seg_len)
        if 0.0 < swept < seg_len:
            return (swept, abs(distance(center, point) - abs(segment.radius_mm)))
        d1 = distance(point, p1)
        d2 = distance(point, p2)
        return (0.0, d1) if d1 <= d2 else (seg_len, d2)

    t, dist = projection(point, p1, p2)
    return (t * seg_len, dist)


def point_at_station(
    segment: ArcSegment,
    p1: Point,
    p2: Point,
    station: float,
) -> Point:
    """Return the point at clamped arc-length ``station`` along one segment."""
    seg_len = arc_length(segment, p1, p2)
    if seg_len <= 0.0:
        return p1

    t = max(0.0, min(1.0, station / seg_len))
    if is_arc(segment):
        cy = segment.arc_center_y_mm
        cz = segment.arc_center_z_mm
        radius = abs(segment.radius_mm)
        start_angle = atan2(p1[1] - cz, p1[0] - cy)
        end_angle = atan2(p2[1] - cz, p2[0] - cy)
        angle = start_angle + t * minor_sweep(start_angle, end_angle)
        return (cy + radius * cos(angle), cz + radius * sin(angle))

    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_segment_math.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/segment_math.py tests/test_segment_math.py
git commit -m "Add shared per-segment geometry helpers (segment_math)"
```

---

### Task 2: Refactor `hmx_export.py` to use `segment_math`

Replace the five private helper definitions with import aliases so every existing call site keeps working unchanged. Behavior must be identical — the existing HMX/2DLX tests are the safety net.

**Files:**
- Modify: `ocx_model_validator/sections/hmx_export.py`

- [ ] **Step 1: Add the aliasing import**

In `hmx_export.py`, below the existing `section_builder` import (around line 15), add:

```python
from ocx_model_validator.sections.segment_math import (
    arc_length as _arc_length_of,
    arc_station_on_segment as _arc_station_on_segment,
    distance as _distance,
    minor_sweep as _minor_sweep,
    projection as _projection,
)
```

- [ ] **Step 2: Delete the now-duplicate local definitions**

Delete these five function definitions from `hmx_export.py` (bodies included):

- `def _arc_length_of(...)` (around line 311, ends before `def _arc_position`)
- `def _distance(...)` (around line 1284)
- `def _projection(...)` (around line 1288)
- `def _arc_station_on_segment(...)` (around line 1305)
- `def _minor_sweep(...)` (around line 1338)

Do NOT delete `_station_and_distance`, `_arc_position`, `_seam_stations`, or the plate-side/radius-sign helper near line 290 — those stay in `hmx_export.py`.

- [ ] **Step 3: Clean up unused math imports**

The top-of-file `from math import asin, atan2, degrees, hypot, pi, tau` now over-imports. `atan2` and `degrees` are still used by `_angles`; check each of `asin`, `hypot`, `pi`, `tau` with a search and remove the ones no longer referenced in this file. Expected result (verify, don't assume):

```python
from math import atan2, degrees
```

- [ ] **Step 4: Run the HMX/2DLX test suite**

Run: `uv run pytest tests/test_hmx_export.py tests/test_hmx_export_helpers.py tests/test_hmx_export_blocks.py tests/test_hmx_schema.py tests/test_dlx_export.py -q`
Expected: all PASS (no behavior change). If a helper test imports one of the deleted private names from `hmx_export`, the alias import keeps it resolvable — failures indicate a wrong deletion.

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/hmx_export.py
git commit -m "Refactor hmx_export to use shared segment_math helpers"
```

---

### Task 3: `epp.py` — EppPlate dataclass and splitter

**Files:**
- Create: `tests/test_epp.py`
- Create: `ocx_model_validator/sections/epp.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_epp.py`:

```python
"""Tests for elementary plate panel (EPP) splitting."""
from math import isclose, pi, sqrt

from ocx_model_validator.sections.epp import EppPlate, split_plates_to_epps
from ocx_model_validator.sections.section_builder import SectionPlate, SectionStiffener


def _plate(
    name="PL1",
    p1=(0.0, 0.0),
    p2=(3000.0, 0.0),
    panel="deck",
    thickness=12.0,
    radius=None,
    cy=None,
    cz=None,
) -> SectionPlate:
    return SectionPlate(
        name=name,
        y1_mm=p1[0],
        z1_mm=p1[1],
        y2_mm=p2[0],
        z2_mm=p2[1],
        thickness_mm=thickness,
        material_reh_mpa=315.0,
        panel=panel,
        radius_mm=radius,
        arc_center_y_mm=cy,
        arc_center_z_mm=cz,
        guidref="guid-1",
    )


def _stiff(name, y, z, panel="deck") -> SectionStiffener:
    return SectionStiffener(
        name=name,
        y_mm=y,
        z_mm=z,
        panel=panel,
        profile_type=None,
        profile_dimensions=None,
        material_reh_mpa=None,
        spacing_mm=None,
    )


def test_two_interior_stiffeners_give_three_epps() -> None:
    stiffs = [_stiff("S1", 1000.0, 0.0), _stiff("S2", 2000.0, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)

    assert [e.name for e in epps] == ["PL1_EPP1", "PL1_EPP2", "PL1_EPP3"]
    assert [(e.bound_lower, e.bound_upper) for e in epps] == [
        (None, "S1"),
        ("S1", "S2"),
        ("S2", None),
    ]
    assert all(isclose(e.breadth_mm, 1000.0) for e in epps)
    assert isclose(epps[0].y1_mm, 0.0) and isclose(epps[0].y2_mm, 1000.0)
    assert isclose(epps[1].y1_mm, 1000.0) and isclose(epps[1].y2_mm, 2000.0)
    assert isclose(epps[2].y1_mm, 2000.0) and isclose(epps[2].y2_mm, 3000.0)


def test_epps_inherit_plate_attributes() -> None:
    epps = split_plates_to_epps([_plate()], [_stiff("S1", 1000.0, 0.0)])
    for e in epps:
        assert isinstance(e, EppPlate)
        assert e.thickness_mm == 12.0
        assert e.material_reh_mpa == 315.0
        assert e.panel == "deck"
        assert e.guidref == "guid-1"


def test_plate_without_stiffeners_is_single_epp() -> None:
    epps = split_plates_to_epps([_plate()], [])
    assert len(epps) == 1
    assert epps[0].name == "PL1_EPP1"
    assert epps[0].bound_lower is None and epps[0].bound_upper is None
    assert isclose(epps[0].breadth_mm, 3000.0)


def test_stiffener_at_plate_end_bounds_without_splitting() -> None:
    stiffs = [_stiff("S0", 0.0, 0.0), _stiff("S3", 3000.0, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 1
    assert epps[0].bound_lower == "S0"
    assert epps[0].bound_upper == "S3"


def test_other_panel_and_far_stiffeners_are_ignored() -> None:
    stiffs = [
        _stiff("OTHER", 1000.0, 0.0, panel="side"),
        _stiff("FAR", 1500.0, 100.0),  # 100 mm off the plate > snap_tol
    ]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 1


def test_coincident_stations_collapse_to_one_split() -> None:
    stiffs = [_stiff("A", 1500.0, 0.0), _stiff("B", 1500.5, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 2
    assert epps[0].bound_upper == "A"
    assert epps[1].bound_lower == "A"


def test_arc_plate_splits_by_arclength_and_keeps_arc_data() -> None:
    # Quarter bilge arc: center (0, 0), radius 1000, (1000, 0) -> (0, 1000).
    arc = _plate(
        name="BILGE",
        p1=(1000.0, 0.0),
        p2=(0.0, 1000.0),
        panel="shell",
        radius=1000.0,
        cy=0.0,
        cz=0.0,
    )
    r = 1000.0 / sqrt(2.0)
    epps = split_plates_to_epps([arc], [_stiff("S1", r, r, panel="shell")])

    assert len(epps) == 2
    quarter = pi / 2.0 * 1000.0
    assert isclose(epps[0].breadth_mm, quarter / 2.0, rel_tol=1e-6)
    assert isclose(epps[1].breadth_mm, quarter / 2.0, rel_tol=1e-6)
    # Split vertex lies on the arc at 45 degrees.
    assert isclose(epps[0].y2_mm, r, rel_tol=1e-6)
    assert isclose(epps[0].z2_mm, r, rel_tol=1e-6)
    # Sub-arcs keep radius and center.
    for e in epps:
        assert e.radius_mm == 1000.0
        assert e.arc_center_y_mm == 0.0 and e.arc_center_z_mm == 0.0
    assert (epps[0].bound_upper, epps[1].bound_lower) == ("S1", "S1")


def test_zero_length_plate_passes_through() -> None:
    degenerate = _plate(p1=(100.0, 100.0), p2=(100.0, 100.0))
    epps = split_plates_to_epps([degenerate], [_stiff("S1", 100.0, 100.0)])
    assert len(epps) == 1
    assert epps[0].breadth_mm == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_epp.py -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'ocx_model_validator.sections.epp'`

- [ ] **Step 3: Create the module**

Create `ocx_model_validator/sections/epp.py`:

```python
"""Split cross-section plates into elementary plate panels (EPPs).

An EPP spans between two adjacent longitudinal stiffeners on the same panel
(or between a stiffener and the plate edge). See
docs/superpowers/specs/2026-09-16-epp-json-export-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.sections.section_builder import SectionPlate, SectionStiffener
from ocx_model_validator.sections.segment_math import (
    arc_length,
    point_at_station,
    project_point,
)


@dataclass(frozen=True)
class EppPlate:
    """One elementary plate panel segment in the section plane."""

    name: str
    y1_mm: float
    z1_mm: float
    y2_mm: float
    z2_mm: float
    thickness_mm: float | None
    material_reh_mpa: float | None
    panel: str | None
    radius_mm: float | None
    arc_center_y_mm: float | None
    arc_center_z_mm: float | None
    guidref: str | None
    bound_lower: str | None
    bound_upper: str | None
    breadth_mm: float


def split_plates_to_epps(
    plates: list[SectionPlate],
    stiffeners: list[SectionStiffener],
    snap_tol: float = 5.0,
    end_tol: float = 1.0,
) -> list[EppPlate]:
    """Split every plate at same-panel stiffener stations into EPPs."""
    return [
        epp
        for plate in plates
        for epp in _split_plate(plate, stiffeners, snap_tol, end_tol)
    ]


def _split_plate(
    plate: SectionPlate,
    stiffeners: list[SectionStiffener],
    snap_tol: float,
    end_tol: float,
) -> list[EppPlate]:
    p1 = (plate.y1_mm, plate.z1_mm)
    p2 = (plate.y2_mm, plate.z2_mm)
    length = arc_length(plate, p1, p2)

    # (station, stiffener name) hits on this plate, sorted along it.
    hits: list[tuple[float, str]] = []
    for stiffener in stiffeners:
        if stiffener.panel != plate.panel:
            continue
        station, dist = project_point(plate, p1, p2, (stiffener.y_mm, stiffener.z_mm))
        if dist <= snap_tol:
            hits.append((station, stiffener.name))
    hits.sort(key=lambda hit: hit[0])

    # Stiffeners sitting on a plate end bound the outermost EPP but never split.
    bound_start = next((name for st, name in hits if st <= end_tol), None)
    bound_end = next(
        (name for st, name in reversed(hits) if st >= length - end_tol), None
    )

    interior: list[tuple[float, str]] = []
    for station, name in hits:
        if station <= end_tol or station >= length - end_tol:
            continue
        if interior and station - interior[-1][0] <= end_tol:
            continue  # coincident stations collapse; first stiffener name wins
        interior.append((station, name))

    stations = [0.0, *(st for st, _ in interior), length]
    bounds = [bound_start, *(name for _, name in interior), bound_end]
    points = [point_at_station(plate, p1, p2, st) for st in stations]
    points[0] = p1
    points[-1] = p2

    return [
        EppPlate(
            name=f"{plate.name}_EPP{index + 1}",
            y1_mm=points[index][0],
            z1_mm=points[index][1],
            y2_mm=points[index + 1][0],
            z2_mm=points[index + 1][1],
            thickness_mm=plate.thickness_mm,
            material_reh_mpa=plate.material_reh_mpa,
            panel=plate.panel,
            radius_mm=plate.radius_mm,
            arc_center_y_mm=plate.arc_center_y_mm,
            arc_center_z_mm=plate.arc_center_z_mm,
            guidref=plate.guidref,
            bound_lower=bounds[index],
            bound_upper=bounds[index + 1],
            breadth_mm=stations[index + 1] - stations[index],
        )
        for index in range(len(stations) - 1)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_epp.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ocx_model_validator/sections/epp.py tests/test_epp.py
git commit -m "Add EPP splitting of section plates at stiffener stations"
```

---

### Task 4: JSON document integration and schema bump

**Files:**
- Modify: `ocx_model_validator/sections/document.py` (SCHEMA at line 18, plates serialization around line 77)
- Modify: `tests/test_sections_document.py` (lines 28, 161 + new test)
- Modify: `tests/test_cli_section.py` (lines 21, 168, 187, 267)
- Modify: `tests/test_sections_integration.py` (line 51)
- Modify: `tests/test_svg_plot.py` (line 9)

- [ ] **Step 1: Write the failing document-level test**

Append to `tests/test_sections_document.py` (it already has a `vessel` fixture used at `x_mm=5000.0`):

```python
def test_plates_are_elementary_plate_panels(vessel) -> None:
    doc = build_document(vessel, "model.ocx", x_mm=5000.0)
    plates = doc["cross_section"]["plates"]
    assert plates
    for entry in plates:
        assert "_EPP" in entry["name"]
        assert {"bound_lower", "bound_upper", "breadth_mm"} <= set(entry)
        assert entry["breadth_mm"] >= 0.0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_sections_document.py::test_plates_are_elementary_plate_panels -v`
Expected: FAIL — plate names carry no `_EPP` suffix and lack the new keys.

- [ ] **Step 3: Implement the document changes**

In `ocx_model_validator/sections/document.py`:

1. Change line 18 from `SCHEMA = "nh-cross-section/1"` to:

```python
SCHEMA = "nh-cross-section/2"
```

2. Add to the imports:

```python
from ocx_model_validator.sections.epp import split_plates_to_epps
```

3. In `build_document`, replace the plates line

```python
            "plates": [_dataclass_dict(plate) for plate in cross_section.plates],
```

with

```python
            "plates": [
                _dataclass_dict(epp)
                for epp in split_plates_to_epps(
                    cross_section.plates, cross_section.stiffeners
                )
            ],
```

- [ ] **Step 4: Update the hard-coded schema strings in tests**

Replace every `"nh-cross-section/1"` with `"nh-cross-section/2"` in:

- `tests/test_sections_document.py` lines 28 and 161
- `tests/test_cli_section.py` lines 21, 168, 187, 267
- `tests/test_sections_integration.py` line 51
- `tests/test_svg_plot.py` line 9

Verify none remain: `uv run python -c "import pathlib; print([str(p) for p in pathlib.Path('.').rglob('*.py') if 'nh-cross-section/1' in p.read_text(encoding='utf-8')])"` → `[]`

- [ ] **Step 5: Run the affected suites**

Run: `uv run pytest tests/test_sections_document.py tests/test_cli_section.py tests/test_sections_integration.py tests/test_svg_plot.py tests/test_integration_section_plot.py tests/test_mcp_server.py -q`
Expected: all PASS. If a test asserts on exact plate counts or names in the JSON, update it to the EPP shape (more segments, `_EPP{n}` names) — the geometry union is unchanged.

- [ ] **Step 6: Commit**

```bash
git add ocx_model_validator/sections/document.py tests/test_sections_document.py tests/test_cli_section.py tests/test_sections_integration.py tests/test_svg_plot.py
git commit -m "Emit elementary plate panels in cross-section JSON (schema v2)"
```

---

### Task 5: Full regression and docs

**Files:**
- Modify: `README.md` and/or `.github/copilot-instructions.md` only if they state the JSON `plates` semantics or schema version (check before editing; both files currently have uncommitted local edits — touch only lines you must, and stage only your own hunks).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all PASS. Fix any stragglers that assert the old plates shape (search: `uv run python -c "print(open('README.md', encoding='utf-8').read().count('nh-cross-section'))"` and grep tests for `["plates"]`).

- [ ] **Step 2: End-to-end smoke test (if a model file is available)**

If a `.3docx` file exists under `models/`, run:

```bash
uv run validator section create <models/somefile>.3docx --x 50000 -o _epp_smoke.json
uv run validator section plot _epp_smoke.json -o _epp_smoke.svg
```

Expected: JSON contains `"schema": "nh-cross-section/2"` and `_EPP` plate names; SVG renders. Delete `_epp_smoke.json` / `_epp_smoke.svg` afterwards. Skip this step if no model file exists.

- [ ] **Step 3: Commit any remaining fixes**

```bash
git add -u
git commit -m "Finish EPP JSON export regression fixes"
```

Only commit if Step 1/2 required changes; otherwise skip.
