"""Pure helpers for HMX section export geometry."""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, degrees, hypot, pi, tau
from typing import Iterable

from ocx_model_validator.sections.section_builder import SectionPlate, SectionStiffener


_LSTIFF_TYPE = {
    "flat_bar": 10,
    "bulb_flat": 20,
    "l_section": 31,
    "l_overshoot_flange": 35,
    "l_overshoot_web": 36,
    "t_section": 40,
}


@dataclass
class _Chain:
    points: list[tuple[float, float]]
    plates: list[SectionPlate]

    def __post_init__(self) -> None:
        if len(self.points) != len(self.plates) + 1:
            raise ValueError(
                f"chain invariant violated: {len(self.points)} points "
                f"for {len(self.plates)} plates (expected plates + 1)"
            )


def _chain_segments(plates: Iterable[SectionPlate], tol: float = 1.0) -> list[_Chain]:
    """Greedily connect plate segments whose endpoints touch within ``tol`` mm."""
    unused = list(plates)
    chains: list[_Chain] = []

    while unused:
        first = unused.pop(0)
        chain = _Chain(
            points=[(first.y1_mm, first.z1_mm), (first.y2_mm, first.z2_mm)],
            plates=[first],
        )

        grew = True
        while grew:
            grew = False
            start = chain.points[0]
            end = chain.points[-1]

            for idx, candidate in enumerate(unused):
                p1 = (candidate.y1_mm, candidate.z1_mm)
                p2 = (candidate.y2_mm, candidate.z2_mm)

                if _same_point(end, p1, tol):
                    chain.points.append(p2)
                    chain.plates.append(candidate)
                elif _same_point(end, p2, tol):
                    chain.points.append(p1)
                    chain.plates.append(candidate)
                elif _same_point(start, p2, tol):
                    chain.points.insert(0, p1)
                    chain.plates.insert(0, candidate)
                elif _same_point(start, p1, tol):
                    chain.points.insert(0, p2)
                    chain.plates.insert(0, candidate)
                else:
                    continue

                unused.pop(idx)
                grew = True
                break

        chains.append(chain)

    return chains


def _signed_radius(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float | None:
    """Return radius signed by arc center side relative to segment travel.

    Arcs are assumed minor (<180°, chord-recoverable) per the OCX bilge use case:
    bilge arcs are quarter-to-semi circles, and the chord formula degrades at exactly
    180°.
    """
    if plate.radius_mm is None:
        return None
    if plate.arc_center_y_mm is None or plate.arc_center_z_mm is None:
        return -abs(plate.radius_mm)

    y1, z1 = p1
    y2, z2 = p2
    dy = y2 - y1
    dz = z2 - z1
    cross = dy * (plate.arc_center_z_mm - z1) - dz * (plate.arc_center_y_mm - y1)
    return abs(plate.radius_mm) if cross >= 0.0 else -abs(plate.radius_mm)


def _arc_length_of(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Return chord length for straight segments or circular arc length.

    Arcs are assumed minor (<180°, chord-recoverable) per the OCX bilge use case:
    bilge arcs are quarter-to-semi circles, and the chord formula degrades at exactly
    180°.
    """
    chord = _distance(p1, p2)
    if plate.radius_mm is None:
        return chord

    radius = abs(plate.radius_mm)
    if radius <= 0.0:
        return chord

    theta = 2.0 * asin(min(1.0, chord / (2.0 * radius)))
    return radius * theta


def _arc_position(_chain: _Chain, y: float, z: float) -> float:
    """Return arc-length station of the nearest chord projection on ``chain``."""
    best_index = 0
    best_t = 0.0
    best_dist = float("inf")

    for idx, (p1, p2) in enumerate(zip(_chain.points, _chain.points[1:])):
        t, dist = _projection((y, z), p1, p2)
        if dist < best_dist:
            best_index = idx
            best_t = t
            best_dist = dist

    prefix = sum(
        _arc_length_of(plate, p1, p2)
        for plate, p1, p2 in zip(_chain.plates[:best_index], _chain.points, _chain.points[1:])
    )
    plate = _chain.plates[best_index]
    p1 = _chain.points[best_index]
    p2 = _chain.points[best_index + 1]
    seg_len = _arc_length_of(plate, p1, p2)
    if (
        plate.radius_mm is not None
        and plate.arc_center_y_mm is not None
        and plate.arc_center_z_mm is not None
        and abs(plate.radius_mm) > 0.0
    ):
        return prefix + _arc_station_on_segment(plate, p1, p2, (y, z), seg_len)

    return prefix + best_t * seg_len


def _level1_code(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
    extent: dict[str, float] | None,
) -> str:
    """Classify a plate segment into the HMX level-1 structural code."""
    if plate.radius_mm is not None:
        return "BILGE"

    if not extent:
        return "Undefined"

    try:
        min_y = extent["min_y"]
        max_y = extent["max_y"]
        min_z = extent["min_z"]
        max_z = extent["max_z"]
    except KeyError:
        return "Undefined"

    if None in (min_y, max_y, min_z, max_z):
        return "Undefined"

    y1, z1 = p1
    y2, z2 = p2
    dy = y2 - y1
    dz = z2 - z1
    span_z = max_z - min_z
    if span_z <= 0.0 or max(abs(min_y), abs(max_y)) <= 0.0:
        return "Undefined"

    mid_y = (y1 + y2) / 2.0
    mid_z = (z1 + z2) / 2.0

    if abs(dz) <= 0.05 * max(abs(dy), 1.0):
        edge_tol = 0.05 * span_z
        if abs(mid_z - min_z) <= edge_tol:
            return "GBOTTOM"
        if abs(mid_z - max_z) <= edge_tol:
            return "STRDECK"

    if abs(dy) <= 0.05 * max(abs(dz), 1.0):
        side_limit = 0.95 * max(abs(min_y), abs(max_y))
        if abs(mid_y) >= side_limit:
            return "SIDE"

    return "Undefined"


def _side(chain: _Chain) -> str:
    """Return side code based on mean transverse coordinate of chain vertices."""
    mean_y = sum(y for y, _ in chain.points) / len(chain.points)
    if mean_y > 1.0:
        return "LEFT"
    if mean_y < -1.0:
        return "RIGHT"
    return "CENTER"


def _angles(stiffener: SectionStiffener) -> tuple[float, float]:
    """Return web and flange angles from a stiffener web direction vector."""
    if stiffener.web_dir_y is None or stiffener.web_dir_z is None:
        return (90.0, 270.0)

    web = degrees(atan2(stiffener.web_dir_z, stiffener.web_dir_y)) % 360.0
    # Nauticus sample convention: FlAngle=90 for WebAngle in [0°,90°), otherwise 270.
    flange = 90.0 if web < 90.0 else 270.0
    return (web, flange)


class _MaterialIds:
    """Stable sequential material IDs keyed by yield strength."""

    def __init__(self) -> None:
        self._ids: dict[float, str] = {}

    def id_for(self, yield_mpa: float) -> str:
        if yield_mpa not in self._ids:
            self._ids[yield_mpa] = str(len(self._ids) + 1)
        return self._ids[yield_mpa]

    def items(self):
        return self._ids.items()


def _same_point(a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    return _distance(a, b) <= tol


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(b[0] - a[0], b[1] - a[1])


def _projection(
    point: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> tuple[float, float]:
    vx = p2[0] - p1[0]
    vz = p2[1] - p1[1]
    length_sq = vx * vx + vz * vz
    if length_sq <= 0.0:
        return (0.0, _distance(point, p1))

    t = ((point[0] - p1[0]) * vx + (point[1] - p1[1]) * vz) / length_sq
    t = max(0.0, min(1.0, t))
    projected = (p1[0] + t * vx, p1[1] + t * vz)
    return (t, _distance(point, projected))


def _arc_station_on_segment(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
    point: tuple[float, float],
    seg_len: float,
) -> float:
    radius = abs(plate.radius_mm or 0.0)
    if radius <= 0.0:
        return 0.0

    cy = plate.arc_center_y_mm
    cz = plate.arc_center_z_mm
    if cy is None or cz is None:
        return 0.0

    query_radius = _distance((cy, cz), point)
    if query_radius <= 0.0:
        return 0.0

    start_angle = atan2(p1[1] - cz, p1[0] - cy)
    end_angle = atan2(p2[1] - cz, p2[0] - cy)
    query_angle = atan2(point[1] - cz, point[0] - cy)

    total = _minor_sweep(start_angle, end_angle)
    query_delta = _minor_sweep(start_angle, query_angle)
    swept = query_delta if total >= 0.0 else -query_delta

    theta_total = min(abs(total), seg_len / radius if radius > 0.0 else 0.0)
    swept = max(0.0, min(theta_total, swept))
    return radius * swept


def _minor_sweep(start_angle: float, end_angle: float) -> float:
    delta = (end_angle - start_angle) % tau
    if delta > pi:
        delta -= tau
    return delta
