from __future__ import annotations

from math import cos, sqrt

import pytest

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrLine3D,
    IrNurbs3D,
    IrPoint3D,
    IrPolyLine3D,
    IrVector3D,
)
from ocx_model_validator.sections.geometry import intersect_curve_plane


def p(x: float, y: float, z: float, unit: str = "Um") -> IrPoint3D:
    return IrPoint3D(x=x, y=y, z=z, unit=unit)


def to_mm(point: IrPoint3D) -> tuple[float, float, float]:
    return (point.x * 1000.0, point.y * 1000.0, point.z * 1000.0)


def test_line_crossing() -> None:
    curve = IrLine3D(curve_length=None, start=p(0, 0, 0), end=p(10, 2, 4))

    assert intersect_curve_plane(curve, 5000.0, to_mm) == pytest.approx(
        [(1000.0, 2000.0)]
    )


def test_line_parallel_no_hit() -> None:
    curve = IrLine3D(curve_length=None, start=p(1, 0, 0), end=p(1, 2, 4))

    assert intersect_curve_plane(curve, 5000.0, to_mm) == []


def test_line_in_plane() -> None:
    curve = IrLine3D(curve_length=None, start=p(5, 1, 2), end=p(5, 3, 4))

    assert intersect_curve_plane(curve, 5000.0, to_mm) == pytest.approx(
        [(1000.0, 2000.0), (3000.0, 4000.0)]
    )


def test_polyline_multi_cross() -> None:
    curve = IrPolyLine3D(
        curve_length=None,
        vertices=[p(0, 0, 0), p(10, 2, 4), p(0, 4, 0)],
    )

    assert intersect_curve_plane(curve, 5000.0, to_mm) == pytest.approx(
        [(1000.0, 2000.0), (3000.0, 2000.0)]
    )


def test_composite_dedupes_shared_vertex() -> None:
    vertex = p(5, 1, 2)
    curve = IrCompositeCurve3D(
        curve_length=None,
        segments=[
            IrLine3D(curve_length=None, start=p(0, 0, 0), end=vertex),
            IrLine3D(curve_length=None, start=vertex, end=p(10, 2, 4)),
        ],
    )

    assert intersect_curve_plane(curve, 5000.0, to_mm) == pytest.approx(
        [(1000.0, 2000.0)]
    )


def test_nurbs_linear_exact() -> None:
    curve = IrNurbs3D(
        curve_length=None,
        degree=1,
        knot_vector=[0.0, 0.0, 1.0, 1.0],
        control_points=[p(0, 0, 0), p(10, 2, 4)],
    )

    assert intersect_curve_plane(curve, 5000.0, to_mm) == pytest.approx(
        [(1000.0, 2000.0)], abs=0.1
    )


def test_nurbs_rational_quarter_circle() -> None:
    curve = IrNurbs3D(
        curve_length=None,
        degree=2,
        knot_vector=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        control_points=[p(1, 0, 0), p(1, 0, 1), p(0, 0, 1)],
        weights=[1.0, sqrt(2.0) / 2.0, 1.0],
        is_rational=True,
    )
    expected = 1000.0 * cos(45.0 * 3.141592653589793 / 180.0)

    hits = intersect_curve_plane(curve, expected, to_mm)

    assert len(hits) == 1
    assert hits[0] == pytest.approx((0.0, expected), abs=0.1)


def test_nurbs_tangent_plane_hit() -> None:
    curve = IrNurbs3D(
        curve_length=None,
        degree=2,
        knot_vector=[0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0],
        control_points=[
            p(0, 0, -1),
            p(1, 0, -1),
            p(1, 0, 0),
            p(1, 0, 1),
            p(0, 0, 1),
        ],
        weights=[1.0, sqrt(2.0) / 2.0, 1.0, sqrt(2.0) / 2.0, 1.0],
        is_rational=True,
    )

    hits = intersect_curve_plane(curve, 1000.0, to_mm)

    assert len(hits) == 1
    assert hits[0] == pytest.approx((0.0, 0.0), abs=0.1)


def test_nurbs_near_tangent_two_hits() -> None:
    curve = IrNurbs3D(
        curve_length=None,
        degree=2,
        knot_vector=[0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0],
        control_points=[
            p(0, 0, -1),
            p(1, 0, -1),
            p(1, 0, 0),
            p(1, 0, 1),
            p(0, 0, 1),
        ],
        weights=[1.0, sqrt(2.0) / 2.0, 1.0, sqrt(2.0) / 2.0, 1.0],
        is_rational=True,
    )
    expected_z = sqrt(1000.0**2 - 999.99**2)

    hits = sorted(intersect_curve_plane(curve, 999.99, to_mm), key=lambda yz: yz[1])

    assert len(hits) == 2
    assert hits[0] == pytest.approx((0.0, -expected_z), abs=0.1)
    assert hits[1] == pytest.approx((0.0, expected_z), abs=0.1)


def test_nurbs_invalid_degree_raises_geometry_error() -> None:
    curve = IrNurbs3D(
        curve_length=None,
        degree=2,
        knot_vector=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        control_points=[p(0, 0, 0), p(1, 0, 0)],
    )

    with pytest.raises(GeometryError, match="degree"):
        intersect_curve_plane(curve, 0.0, to_mm)


def test_circumarc_crossing() -> None:
    curve = IrCircumArc3D(
        curve_length=None,
        start=p(1, 0, 0),
        intermediate=p(0, 0, 1),
        end=p(-1, 0, 0),
    )

    assert intersect_curve_plane(curve, 0.0, to_mm) == pytest.approx(
        [(0.0, 1000.0)], abs=0.1
    )


def test_circle_crossing() -> None:
    curve = IrCircle3D(
        curve_length=None,
        center=p(0, 0, 0),
        diameter=Quantity(2.0, "Um"),
        normal=IrVector3D(0.0, 1.0, 0.0),
    )

    hits = sorted(intersect_curve_plane(curve, 0.0, to_mm), key=lambda yz: yz[1])

    assert hits == pytest.approx([(0.0, -1000.0), (0.0, 1000.0)], abs=0.1)


def test_circle_tangent_hit() -> None:
    curve = IrCircle3D(
        curve_length=None,
        center=p(0, 0, 0),
        diameter=Quantity(2.0, "Um"),
        normal=IrVector3D(0.0, 1.0, 0.0),
    )

    hits = intersect_curve_plane(curve, 1000.0, to_mm)

    assert len(hits) == 1
    assert hits[0] == pytest.approx((0.0, 0.0), abs=0.1)


def test_circle_near_tangent_hits_are_accurate() -> None:
    curve = IrCircle3D(
        curve_length=None,
        center=p(0, 0, 0),
        diameter=Quantity(2.0, "Um"),
        normal=IrVector3D(0.0, 1.0, 0.0),
    )
    expected_z = sqrt(1000.0**2 - 999.99**2)

    hits = sorted(intersect_curve_plane(curve, 999.99, to_mm), key=lambda yz: yz[1])

    assert len(hits) == 2
    assert hits[0] == pytest.approx((0.0, -expected_z), abs=0.1)
    assert hits[1] == pytest.approx((0.0, expected_z), abs=0.1)


def test_unknown_curve_raises_geometry_error() -> None:
    with pytest.raises(GeometryError, match="object"):
        intersect_curve_plane(object(), 0.0, to_mm)


def test_line_missing_points_raises() -> None:
    curve = IrLine3D(curve_length=None, start=None, end=None)

    with pytest.raises(GeometryError, match="IrLine3D"):
        intersect_curve_plane(curve, 0.0, to_mm)
