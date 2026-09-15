# Seam-Based Plate Division in Cross-Section Export — Design

**Date:** 2026-09-15
**Status:** Approved for planning

## Problem

The 2DLX/HMX cross-section export currently emits one PLATE per intersected OCX
plate piece. Nauticus Hull divides plates by **seam positions**: each PANEL
carries an ordered PLATE list whose `Width` values (RefCode=`CURVE`, measured
along the panel shape curve) are the seam-to-seam strake widths. NH merges
plates across OCX plate-object boundaries that are not seams, and splits
equal-property plates at seams.

Evidence from the NH baseline `NAPA VLCC_Fr(x=160000).2dlx`:

- DECK: 9 SEGMENTs but 10 PLATEs — plate and segment subdivisions are
  independent.
- One deck PLATE of 13764 mm spans several geometry segments; our export emits
  three plates (6900 + 4083 + 2780 ≈ 13764) there because the OCX model divides
  that strake into three plate objects.
- Five deck PLATEs of 4536 mm all share thickness 20 mm — divisions that only
  seams (not property changes or geometry) can explain.
- The 2DLX schema (`schema/CrossSection_2DLX.xsd`) has **no SEAM element**;
  seams exist only implicitly as PLATE boundaries.

## Existing IR support (no changes needed)

`IrSeam` (`model/ir/structural.py`) already exists with `id`, `name`,
`guidref`, and `trace_line` (an IR curve). `OcxV3Builder._build_seams_for_panel`
builds seams from `Panel/SplitBy/Seam`, registers them in `IrVessel.seams`, and
stores `seam_ids` on each `IrPanel`. The D-VLCC model yields 230 seams, all
with `IrCompositeCurve3D` tracelines (DECK: 15, SHELLS/SHELLP: 12 each, …).

## Scope decisions (user-approved)

1. **Export-only.** Plate re-division happens in the 2DLX/HMX exporter. The
   JSON section document keeps its per-OCX-plate entries and gains a new
   seam-points list. SVG plotting is unaffected.
2. **Midpoint-with-warning conflict rule.** When a seam-to-seam span covers
   OCX plates with differing Thickness/Yield, the plate under the span
   midpoint supplies the properties and a warning is emitted.

## Design

### 1. Section builder (`sections/section_builder.py`)

New frozen dataclass:

```python
@dataclass(frozen=True)
class SectionSeam:
    name: str | None      # seam name or id
    panel: str | None     # owning panel name (matches SectionPlate.panel)
    y_mm: float
    z_mm: float
```

New `_build_seams(vessel, x_mm, to_mm, tol, warnings)` called from
`build_cross_section`:

- For each panel with `seam_ids`, look up each `IrSeam` and intersect
  `seam.trace_line` with the section plane via the existing
  `intersect_curve_plane` (same `tol`).
- Each hit produces one `SectionSeam` (a seam may hit the plane more than
  once; transverse seams parallel to the plane typically produce no hits).
- Missing tracelines are skipped silently; `GeometryError` → warning
  (`"seam <name>: <error>"`) and skip, mirroring plate/stiffener handling.

`CrossSection` gains `seams: list[SectionSeam]` (default `[]`). The JSON
document writer serializes it as a `seams` array (`name`, `panel`, `y_mm`,
`z_mm`). An empty seams list changes nothing else.

### 2. Exporter (`sections/hmx_export.py`)

Applies to both HMX and 2DLX (shared `_append_section_body` path). SEGMENT
emission (geometry nodes, radii, knuckle/arc decomposition) is **unchanged** —
only the PLATES block per PANEL changes.

For each `_PanelChain`:

1. **Collect stations.** Take the `SectionSeam` points whose `panel` matches
   the chain's source panel. Project each point onto the chain (straight
   segments: perpendicular projection clamped to the segment; arc segments:
   angular projection clamped to the arc) → arclength station from the chain
   start. Discard points farther than a snap tolerance of **50 mm** from the
   chain (they belong to another disconnected part of the panel or to the
   other CL half).
2. **Clean stations.** Sort ascending; drop stations within **1 mm** of the
   chain start, the chain end, or a previously kept station (no zero-width
   plates).
3. **Emit PLATEs.** Spans run chain start → station₁ → … → chain end. One
   PLATE per span with `Width` = span arclength (arcs contribute R·Δθ),
   `RefCode="CURVE"`. No stations → a single PLATE covering the whole chain
   (matches NH girder panels).
4. **Properties.** Locate the exported `SectionPlate` covering the span's
   arclength midpoint; take its Thickness/Yield (and HMX MaterialId). If any
   plate overlapping the span differs in thickness or yield from the midpoint
   plate, append a warning
   (`"panel <name>: seam span at s=<mid> mixes plate properties; using <plate>"`).
5. **CL-split chains** naturally keep only their own stations: stations come
   from projection onto the (already split) chain geometry, and the 50 mm snap
   rejects points from the other half.

Total PLATE width per PANEL remains the chain length, preserving NH's
sequential-width layout.

### 3. Out of scope

- No 2DLX/HMX SEAM element (none exists in the schema).
- No changes to SVG plotting, stiffener handling, or SEGMENT decomposition.
- No IR or builder changes.
- Transverse seams that do not intersect the section plane are ignored.

## Testing

Unit tests (`tests/test_sections_builder.py`, `tests/test_hmx_export_helpers.py`,
`tests/test_dlx_export.py`):

- `_build_seams`: seam crossing the plane → one `SectionSeam` with correct
  y/z and panel; seam missing the plane → none; traceline raising
  `GeometryError` → warning, no seam; seam without traceline → skipped.
- JSON document round-trip includes the `seams` array.
- Station projection: point on a straight segment, point near an arc segment,
  point beyond the 50 mm snap tolerance (ignored), station within 1 mm of a
  chain end (dropped).
- Span emission: two stations → three PLATEs with correct widths summing to
  chain length; arc span width = R·Δθ; no stations → one full-width PLATE.
- Properties: uniform span → plate properties passed through; mixed span →
  midpoint plate wins + warning recorded.
- CL split: seam on the far half is not applied to the near chain.

Oracle verification (manual + scripted comparison, as in previous fixes):

- Regenerate `D-VLCC_1-HOLD-OCX-simple_v3-x160000.2dlx` and compare per-PANEL
  PLATE counts and widths against the NH baseline
  `NAPA VLCC_Fr(x=160000).2dlx`. Expected: DECK 10 plates including the
  13764 mm span and 5 × 4536 mm; single-plate girder panels; side shell plate
  widths matching baseline strakes.
- User imports the regenerated file into Nauticus Hull as final acceptance.
