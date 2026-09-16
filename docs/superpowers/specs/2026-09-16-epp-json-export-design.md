# Elementary Plate Panels (EPP) in the cross-section JSON export — Design

Date: 2026-09-16
Status: Approved

## Goal

The cross-section JSON document currently emits one `plates` entry per raw
plate–plane intersection (`SectionPlate`). A single plate typically spans
several longitudinal stiffeners, so each entry covers several elementary
plate panels (EPPs). This change replaces the `plates` array with EPP-sized
segments: each entry spans between two adjacent longitudinal stiffener
intersections (or a stiffener and the plate edge).

Scope is the JSON document only. HMX and 2DLX exports keep consuming the
unsplit `CrossSection.plates`. The SVG plot reads the JSON, so it will draw
EPP-sized segments — identical geometry, no plot code changes.

## Components

### 1. `sections/segment_math.py` (new)

Per-segment geometry helpers extracted from `hmx_export.py`, shared by the
HMX export and the new EPP splitter:

- `arc_length(plate, p1, p2) -> float` — chord length for straights,
  circular arc length for plates with `radius_mm` (minor arcs, <180°, per
  the OCX bilge use case).
- `project_point(plate, p1, p2, point) -> tuple[station, distance]` —
  clamped chord projection for straights; radial projection onto the arc
  when the point falls inside the arc sweep.
- `point_at_station(plate, p1, p2, station) -> tuple[y, z]` — linear
  interpolation for straights; angle interpolation about the arc center for
  arcs.

`hmx_export.py` is refactored to use these helpers with unchanged behavior.

### 2. `sections/epp.py` (new)

```python
@dataclass(frozen=True)
class EppPlate:
    # All SectionPlate fields:
    name: str                     # "{plate.name}_EPP{n}", n is 1-based
    y1_mm, z1_mm, y2_mm, z2_mm: float
    thickness_mm: float | None
    material_reh_mpa: float | None
    panel: str | None
    radius_mm: float | None
    arc_center_y_mm: float | None
    arc_center_z_mm: float | None
    guidref: str | None
    # EPP additions:
    bound_lower: str | None       # stiffener name at start bound, None at free edge
    bound_upper: str | None       # stiffener name at end bound, None at free edge
    breadth_mm: float             # arclength between the bounds
```

Public API:

```python
def split_plates_to_epps(
    plates: list[SectionPlate],
    stiffeners: list[SectionStiffener],
    snap_tol: float = 5.0,
    end_tol: float = 1.0,
) -> list[EppPlate]
```

Naming: EPP names use an index suffix `_EPP{n}` numbered along the plate's
point order. The suffix is applied uniformly — a plate with no interior
stiffeners yields one entry named `{plate.name}_EPP1`.

### 3. Splitting algorithm (per plate)

1. Candidate stiffeners: those whose `panel` equals the plate's `panel`.
2. For each candidate, `project_point` gives `(station, distance)` on the
   plate segment/arc.
3. Keep hits with `distance <= snap_tol` and station strictly inside
   `(end_tol, L - end_tol)` where `L = arc_length(plate)`. Sort by station;
   dedupe stations closer than `end_tol` (first stiffener name wins).
4. Split the plate geometry at the kept stations via `point_at_station`.
   Sub-arcs inherit `radius_mm` and the arc center.
5. Bounds: each interior split stiffener is `bound_upper` of the EPP it
   ends and `bound_lower` of the EPP it starts. For the outermost EPP ends,
   a candidate stiffener with `distance <= snap_tol` whose station is
   within `end_tol` of the plate end is recorded as the bound (it does not
   split); otherwise the bound is `None`.
6. `breadth_mm` = station span of the EPP (arclength).
7. Lower/upper follow the plate's own point order (`(y1,z1)` → `(y2,z2)`).

Edge cases:

- Zero/near-zero-length plates (`L <= 2 * end_tol`) pass through as a
  single EPP with `breadth_mm = L` and end-bound lookup only.
- Multiple stiffener hits at the same station collapse to one split.
- Stiffeners of other panels never split or bound a plate.
- No new exception types; existing warnings flow is untouched.

### 4. `sections/document.py` integration

`build_document` computes
`epps = split_plates_to_epps(cross_section.plates, cross_section.stiffeners)`
and serializes them as `cross_section.plates` (via `_dataclass_dict`).
`SCHEMA` is bumped from `"nh-cross-section/1"` to `"nh-cross-section/2"`.
Stiffeners, seams, frame table, compartments, and warnings are unchanged.

## Data flow

```
CrossSection.plates ── split_plates_to_epps(plates, stiffeners) ──> list[EppPlate]
                                                                        │
build_document ── serialize ──> doc["cross_section"]["plates"]  <───────┘
SVG plot / consumers read the JSON (EPP segments, same total geometry)
HMX / 2DLX continue to read CrossSection.plates (unsplit)
```

## Testing

`tests/test_epp.py` (unit, inline stub-free — plain `SectionPlate` /
`SectionStiffener` instances):

- Straight plate with 2 interior stiffeners → 3 EPPs; stations, names
  (`_EPP1.._EPP3`), breadths, and lower/upper bounds correct.
- Plate with no stiffeners → single `_EPP1`, bounds `None`, breadth = L.
- Stiffener within `end_tol` of a plate end → no split, recorded as bound.
- Arc (bilge) plate split → sub-arcs keep radius/center; arclength breadths.
- Stiffener from another panel ignored; stiffener farther than `snap_tol`
  ignored; duplicate stations deduped.

`tests/test_document.py` / `tests/test_cli_section.py`:

- Document-level: JSON `plates` entries carry `bound_lower`, `bound_upper`,
  `breadth_mm`, `_EPP{n}` names; `schema == "nh-cross-section/2"`.
- CLI regression against existing stub models: `section create` succeeds
  and `section plot` renders the EPP-based JSON.
- HMX/2DLX exports unchanged (existing tests keep passing after the
  `segment_math` refactor).
