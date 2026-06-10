"""Unit tests for geometry IR dataclasses."""
from __future__ import annotations

import pytest

from ocx_model_validator.model.ir import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCone3D,
    IrCoordinateSystem,
    IrCurve3D,
    IrCylinder3D,
    IrEllipse3D,
    IrExtrudedSurface,
    IrLine3D,
    IrNurbs3D,
    IrNurbsSurface,
    IrPlane3D,
    IrPoint3D,
    IrPolyLine3D,
    IrRefPlane,
    IrSphere3D,
    IrSurface,
    IrSurface3D,
    IrSurfaceCollection,
    IrVector3D,
    Quantity,
)


def test_point3d_holds_coordinates_and_unit():
    p = IrPoint3D(x=1.0, y=2.0, z=3.0, unit="Umm")
    assert (p.x, p.y, p.z, p.unit) == (1.0, 2.0, 3.0, "Umm")


def test_vector3d_is_dimensionless():
    v = IrVector3D(x=0.0, y=0.0, z=1.0)
    assert (v.x, v.y, v.z) == (0.0, 0.0, 1.0)


def test_curve_length_is_required_positional():
    with pytest.raises(TypeError):
        IrLine3D()  # curve_length has no default


def test_line3d_construction():
    a = IrPoint3D(0.0, 0.0, 0.0, "Um")
    b = IrPoint3D(1.0, 0.0, 0.0, "Um")
    line = IrLine3D(curve_length=Quantity(1.0, "Um"), start=a, end=b)
    assert isinstance(line, IrCurve3D)
    assert line.curve_length == Quantity(1.0, "Um")
    assert line.start is a and line.end is b
    assert line.id is None


def test_circle3d_defaults():
    c = IrCircle3D(curve_length=None)
    assert c.center is None and c.diameter is None and c.normal is None


def test_polyline_and_composite_default_to_empty_lists():
    pl = IrPolyLine3D(curve_length=None)
    cc = IrCompositeCurve3D(curve_length=None)
    assert pl.vertices == [] and cc.segments == []
    assert pl.is_closed is False
    assert pl.vertices is not IrPolyLine3D(curve_length=None).vertices  # no shared default


def test_circumarc_ellipse_nurbs_curves_construct():
    assert IrCircumArc3D(curve_length=None).intermediate is None
    assert IrEllipse3D(curve_length=None).major_axis is None
    assert IrEllipse3D(curve_length=None).normal is None
    n = IrNurbs3D(curve_length=None, degree=2)
    assert n.degree == 2 and n.knot_vector == [] and n.control_points == []
    assert n.is_rational is False


def test_surface_subclasses_construct():
    assert isinstance(IrPlane3D(), IrSurface3D)
    assert IrPlane3D().id is None and IrPlane3D().udirection is None
    assert IrSphere3D().radius is None and IrSphere3D().origin is None
    assert IrCone3D().tip_radius is None and IrCone3D().base_radius is None
    assert IrCylinder3D().axis is None and IrCylinder3D().height is None
    assert IrExtrudedSurface().base_curve is None and IrExtrudedSurface().sweep is None
    assert IrNurbsSurface().control_points == []


def test_reference_geometry_construct():
    cs = IrCoordinateSystem(id="cs1")
    assert cs.name is None and cs.local_origin is None
    assert cs.is_global is False and cs.x_ref_plane_ids == []
    rp = IrRefPlane(id="rp1")
    assert rp.reference_plane is None
    surf = IrSurface(id="s1")
    assert surf.geometry is None and surf.guidref is None
    coll = IrSurfaceCollection(id="sc1")
    assert coll.surfaces == []
