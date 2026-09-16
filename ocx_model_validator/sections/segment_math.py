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
    snap to the nearest endpoint otherwise. Segments with a radius but no
    center data are treated as straight chords.
    """
    arc = is_arc(segment)
    seg_len = arc_length(segment, p1, p2) if arc else distance(p1, p2)
    if arc:
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
    """Return the point at clamped arc-length ``station`` along one segment.

    Segments with a radius but no center data are treated as straight chords.
    """
    arc = is_arc(segment)
    seg_len = arc_length(segment, p1, p2) if arc else distance(p1, p2)
    if seg_len <= 0.0:
        return p1

    t = max(0.0, min(1.0, station / seg_len))
    if arc:
        cy = segment.arc_center_y_mm
        cz = segment.arc_center_z_mm
        radius = abs(segment.radius_mm)
        start_angle = atan2(p1[1] - cz, p1[0] - cy)
        end_angle = atan2(p2[1] - cz, p2[0] - cy)
        angle = start_angle + t * minor_sweep(start_angle, end_angle)
        return (cy + radius * cos(angle), cz + radius * sin(angle))

    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
