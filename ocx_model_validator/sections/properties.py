"""Load, match, and derive hull-girder cross-section properties."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ocx_model_validator.exeptions import SectionError

_MATCH_TOLERANCE_MM = 1.0
_MODEL_DERIVED_KEYS = ("ibh", "z_deck_corner", "bx")
_DECK_EXCLUDE = ("inner bottom", "platform", "floor")
_INNER_BOTTOM_MARKERS = ("inner bottom", "double bottom")
_IBH_FALLBACK_Y_MM = 50.0
_IBH_DEDUPE_MM = 1.0
# second intersection this close (relative) to the section top is the deck
_IBH_MAX_Z_REL_TOLERANCE = 0.05


def load_section_properties(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON list of section-property entries keyed by ``x_pos`` (mm)."""
    with Path(path).open(encoding="utf-8") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        raise SectionError("Section properties root must be a JSON list")
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(
            entry.get("x_pos"), (int, float)
        ):
            raise SectionError(
                f"Section properties entry {i} must be an object with a numeric x_pos"
            )
        rejected = [key for key in _MODEL_DERIVED_KEYS if key in entry]
        if rejected:
            raise SectionError(
                f"Section properties entry {i}: {', '.join(rejected)} "
                "are derived from the OCX model and must not be user input"
            )
    return entries


def match_properties(
    entries: list[dict[str, Any]], x_mm: float
) -> dict[str, Any] | None:
    """Return the entry whose x_pos is within 1 mm of x_mm, or None."""
    for entry in entries:
        if abs(entry["x_pos"] - x_mm) <= _MATCH_TOLERANCE_MM:
            return entry
    return None


def derive_section_properties(
    plates: Iterable[Any],
) -> tuple[dict[str, float | None], list[str]]:
    """Derive ibh, z_deck_corner and bx (all in m) from section plates.

    - bx: full local breadth from the y-extent of all plates (doubled for
      half-breadth models).
    - z_deck_corner: z of the deck-plate endpoint furthest outboard.
    - ibh: max z of inner-bottom / double-bottom plates.
    """
    warnings: list[str] = []
    plates = list(plates)
    endpoints = [
        (y, z)
        for plate in plates
        for y, z in ((plate.y1_mm, plate.z1_mm), (plate.y2_mm, plate.z2_mm))
    ]

    return (
        {
            "ibh": _ibh_m(plates, warnings),
            "z_deck_corner": _z_deck_corner_m(plates, warnings),
            "bx": _bx_m(endpoints, warnings),
        },
        warnings,
    )


def _bx_m(endpoints: list[tuple[float, float]], warnings: list[str]) -> float | None:
    if not endpoints:
        warnings.append("bx not derivable: cross-section has no plates")
        return None
    ys = [y for y, _ in endpoints]
    min_y, max_y = min(ys), max(ys)
    breadth_mm = max_y - min_y if min_y < -1.0 else 2.0 * max_y
    return breadth_mm / 1000.0


def _deck_endpoints(plates: list[Any]) -> list[tuple[float, float]]:
    endpoints: list[tuple[float, float]] = []
    for plate in plates:
        ft = (plate.function_type or "").lower()
        if not ft.startswith("deck"):
            continue
        if any(marker in ft for marker in _DECK_EXCLUDE):
            continue
        endpoints.append((plate.y1_mm, plate.z1_mm))
        endpoints.append((plate.y2_mm, plate.z2_mm))
    return endpoints


def _z_deck_corner_m(plates: list[Any], warnings: list[str]) -> float | None:
    endpoints = _deck_endpoints(plates)
    if not endpoints:
        warnings.append(
            "z_deck_corner not derivable: no deck plates in the cross-section")
        return None
    _, z = max(endpoints, key=lambda point: (abs(point[0]), point[1]))
    return z / 1000.0


def _ibh_m(plates: list[Any], warnings: list[str]) -> float | None:
    zs = [
        z
        for plate in plates
        if any(marker in (plate.function_type or "").lower()
               for marker in _INNER_BOTTOM_MARKERS)
        for z in (plate.z1_mm, plate.z2_mm)
    ]
    if zs:
        return max(zs) / 1000.0
    return _ibh_fallback_m(plates, warnings)


def _ibh_fallback_m(plates: list[Any], warnings: list[str]) -> float | None:
    """Second plate intersection with the vertical line y=50 mm (first = bottom)."""
    hits: list[float] = []
    for plate in plates:
        z = _segment_z_at_y(plate, _IBH_FALLBACK_Y_MM)
        if z is not None and not any(abs(z - hit) <= _IBH_DEDUPE_MM for hit in hits):
            hits.append(z)
    hits.sort()

    if len(hits) < 2:
        warnings.append(
            "ibh not derivable: no inner-bottom plates and fewer than two "
            f"intersections at y={_IBH_FALLBACK_Y_MM:g} mm")
        return None

    ibh_mm = hits[1]
    max_z = max(z for plate in plates for z in (plate.z1_mm, plate.z2_mm))
    if abs(max_z - ibh_mm) <= _IBH_MAX_Z_REL_TOLERANCE * abs(max_z):
        warnings.append(
            "ibh not derivable: no inner-bottom plates and the second "
            f"intersection at y={_IBH_FALLBACK_Y_MM:g} mm is near the section top")
        return None
    return ibh_mm / 1000.0


def _segment_z_at_y(plate: Any, y: float) -> float | None:
    y1, z1, y2, z2 = plate.y1_mm, plate.z1_mm, plate.y2_mm, plate.z2_mm
    if not (min(y1, y2) <= y <= max(y1, y2)) or y1 == y2:
        return None
    t = (y - y1) / (y2 - y1)
    return z1 + t * (z2 - z1)
