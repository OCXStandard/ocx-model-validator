"""Tests for shared per-segment geometry helpers."""
from math import isclose, pi, sqrt

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

