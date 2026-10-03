"""Builder tests for the OCX 3.1.0 extraction extensions.

Uses inline OCX-shaped stub classes (matching the real OCX 3.1.0 field names)
fed directly to the ``OcxV3Builder._build_*`` methods, mirroring the stub style
of ``tests/test_ir_builder.py``.
"""
from __future__ import annotations

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCone3D,
    IrCylinder3D,
    IrEllipse3D,
    IrEndCut,
    IrLine3D,
    IrLSectionOvershootFlange,
    IrNurbs3D,
    IrOccurrence,
    IrOccurrenceGroup,
    IrPlane3D,
    IrPolyLine3D,
    IrSphere3D,
    IrTSection,
    IrVessel,
)


def _b() -> OcxV3Builder:
    return OcxV3Builder()


class _Stub:
    """Generic attribute bag."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _pt(x, y, z, unit="Umm"):
    return _Stub(coordinates=[x, y, z], unit=unit)


def _vec(x, y, z):
    return _Stub(direction=[x, y, z])


def _q(value, unit="Umm"):
    return _Stub(numericvalue=value, unit=unit)


def _enum_stub(value):
    return _Stub(value=value)


def _ref_stub(local, guid=None):
    return _Stub(local_ref=local, guidref=guid)


# --- named curve stubs (dispatch is by class name) ---

class Line3D(_Stub): pass
class Circle3D(_Stub): pass
class CircumArc3D(_Stub): pass
class PolyLine3D(_Stub): pass
class Ellipse3D(_Stub): pass
class Nurbs3D(_Stub): pass
class CompositeCurve3D(_Stub): pass

# --- named section stubs ---

class BarSection(_Stub): pass
class Tbar(_Stub): pass
class LbarOF(_Stub): pass

# --- named surface stubs ---

class Plane3D(_Stub): pass
class Sphere3D(_Stub): pass
class Cone3D(_Stub): pass
class Cylinder3D(_Stub): pass
class ExtrudedSurface(_Stub): pass


# ===========================================================================
# Primitives
# ===========================================================================

def test_pt_unpacks_coordinates():
    ir = _b()._pt(_pt(1.0, 2.0, 3.0, "Um"))
    assert (ir.x, ir.y, ir.z, ir.unit) == (1.0, 2.0, 3.0, "Um")


def test_pt_and_vec_none():
    assert _b()._pt(None) is None
    assert _b()._vec(None) is None


def test_vec_unpacks_direction():
    ir = _b()._vec(_vec(0.0, 0.0, 1.0))
    assert (ir.x, ir.y, ir.z) == (0.0, 0.0, 1.0)


# ===========================================================================
# Curves
# ===========================================================================

def test_build_line():
    ln = Line3D(start_point=_pt(0, 0, 0), end_point=_pt(1, 0, 0), curve_length=None, id="L1")
    ir = _b()._build_curve(ln)
    assert isinstance(ir, IrLine3D)
    assert ir.start.x == 0.0 and ir.end.x == 1.0 and ir.id == "L1"


def test_build_circle_uses_diameter():
    c = Circle3D(center=_pt(0, 0, 0), diameter=_q(2.0), normal=_vec(0, 0, 1), curve_length=None)
    ir = _b()._build_curve(c)
    assert isinstance(ir, IrCircle3D)
    assert ir.diameter.value == 2.0 and ir.normal.z == 1.0


def test_build_circumarc_intermediate():
    a = CircumArc3D(start_point=_pt(0, 0, 0), intermediate_point=_pt(1, 1, 0),
                    end_point=_pt(2, 0, 0), curve_length=None)
    ir = _b()._build_curve(a)
    assert isinstance(ir, IrCircumArc3D)
    assert ir.intermediate.x == 1.0


def test_build_ellipse():
    e = Ellipse3D(center=_pt(0, 0, 0), major_diameter=_q(4.0), minor_diameter=_q(2.0),
                  major_axis=_vec(1, 0, 0), minor_axis=_vec(0, 1, 0), normal=_vec(0, 0, 1),
                  curve_length=None)
    ir = _b()._build_curve(e)
    assert isinstance(ir, IrEllipse3D)
    assert ir.major_diameter.value == 4.0 and ir.minor_diameter.value == 2.0


def test_build_polyline_points_and_closed():
    pl = PolyLine3D(point3_d=[_pt(0, 0, 0), _pt(1, 1, 1)], is_closed=True, curve_length=None)
    ir = _b()._build_curve(pl)
    assert isinstance(ir, IrPolyLine3D)
    assert len(ir.vertices) == 2 and ir.is_closed is True


def test_build_nurbs():
    props = _Stub(degree=3, is_rational=True, form=_enum_stub("Open"))
    kv = _Stub(value=[0.0, 0.0, 1.0, 1.0])
    cpl = _Stub(control_point=[_pt(0, 0, 0), _pt(1, 0, 0)])
    n = Nurbs3D(nurbsproperties=props, knot_vector=kv, control_pt_list=cpl, curve_length=None)
    ir = _b()._build_curve(n)
    assert isinstance(ir, IrNurbs3D)
    assert ir.degree == 3 and ir.is_rational is True and ir.form == "Open"
    assert ir.knot_vector == [0.0, 0.0, 1.0, 1.0] and len(ir.control_points) == 2


def test_build_composite_collects_typed_lists():
    ln = Line3D(start_point=_pt(0, 0, 0), end_point=_pt(1, 0, 0), curve_length=None)
    cc = CompositeCurve3D(line3_d=[ln], poly_line3_d=[], circum_arc3_d=[],
                          circle3_d=[], ellipse3_d=[], nurbs3_d=[], curve_length=None)
    ir = _b()._build_curve(cc)
    assert isinstance(ir, IrCompositeCurve3D)
    assert len(ir.segments) == 1 and isinstance(ir.segments[0], IrLine3D)


def test_build_curve_unknown_and_none():
    class Weird(_Stub): pass
    assert _b()._build_curve(Weird()) is None
    assert _b()._build_curve(None) is None


# ===========================================================================
# Surfaces
# ===========================================================================

def test_build_sphere_origin():
    s = Sphere3D(origin=_pt(1, 2, 3), radius=_q(5.0), id="S1")
    ir = _b()._build_surface(s)
    assert isinstance(ir, IrSphere3D)
    assert ir.origin.x == 1.0 and ir.radius.value == 5.0


def test_build_cone_base_tip_radius():
    c = Cone3D(origin=_pt(0, 0, 0), tip=_pt(0, 0, 10), base_radius=_q(3.0), tip_radius=_q(1.0))
    ir = _b()._build_surface(c)
    assert isinstance(ir, IrCone3D)
    assert ir.base_radius.value == 3.0 and ir.tip_radius.value == 1.0 and ir.tip.z == 10.0


def test_build_cylinder_height():
    cy = Cylinder3D(origin=_pt(0, 0, 0), axis=_vec(0, 0, 1), radius=_q(2.0), height=_q(8.0))
    ir = _b()._build_surface(cy)
    assert isinstance(ir, IrCylinder3D)
    assert ir.height.value == 8.0 and ir.radius.value == 2.0


def test_build_plane_udirection():
    p = Plane3D(origin=_pt(0, 0, 0), normal=_vec(0, 0, 1), udirection=_vec(1, 0, 0))
    ir = _b()._build_surface(p)
    assert isinstance(ir, IrPlane3D)
    assert ir.point_on_surface.x == 0.0
    assert ir.udirection.x == 1.0


# ===========================================================================
# Reference surfaces + coordinate system
# ===========================================================================

def test_build_reference_surfaces_populates_vessel():
    v = IrVessel(id="v1")
    rs = _Stub(plane3_d=[Plane3D(origin=_pt(0, 0, 0), normal=_vec(0, 0, 1),
                                 udirection=_vec(1, 0, 0), id="P1")],
               sphere3_d=[Sphere3D(origin=_pt(0, 0, 0), radius=_q(1.0), id="SPH1")],
               surface_collection=[_Stub(id="SC1", name="coll",
                                         plane3_d=[Plane3D(origin=_pt(0, 0, 0), id="P2")])])
    _b()._build_reference_surfaces(rs, v)
    assert "P1" in v.surfaces and isinstance(v.surfaces["P1"].geometry, IrPlane3D)
    assert "SPH1" in v.surfaces and isinstance(v.surfaces["SPH1"].geometry, IrSphere3D)
    assert "SC1" in v.surface_collections
    assert len(v.surface_collections["SC1"].surfaces) == 1


def test_build_coordinate_system():
    v = IrVessel(id="v1")
    cs = _Stub(id="CS1", name="global", is_global=True,
               local_cartesian=_Stub(origin=_pt(1, 2, 3)),
               xref_planes=_Stub(ref_plane=[_Stub(id="RPX", name="x0")]),
               yref_planes=_Stub(ref_plane=[_Stub(id="RPY", name="y0")]),
               zref_planes=None)
    _b()._build_coordinate_system(cs, v)
    cms = v.coordinate_systems["CS1"]
    assert cms.is_global is True and cms.local_origin.x == 1.0
    assert cms.x_ref_plane_ids == ["RPX"] and cms.y_ref_plane_ids == ["RPY"]
    assert cms.z_ref_plane_ids == []
    assert "RPX" in v.ref_planes and "RPY" in v.ref_planes


def test_build_coordinate_system_accepts_list_and_single_ref_plane():
    v = IrVessel(id="v1")
    cs = [
        _Stub(
            id="CS1",
            is_global=True,
            xref_planes=_Stub(ref_plane=_Stub(id="RPX", name="X0")),
            yref_planes=None,
            zref_planes=None,
        )
    ]

    _b()._build_coordinate_system(cs, v)

    assert v.coordinate_systems["CS1"].x_ref_plane_ids == ["RPX"]
    assert v.ref_planes["RPX"].name == "X0"


def test_build_section_unwraps_bar_section_choice():
    raw = BarSection(
        id="S1",
        name="500X11 + 150X25 TEE",
        guidref="g-s1",
        tbar=Tbar(
            height=_q(0.5, "Um"),
            width=_q(0.15, "Um"),
            web_thickness=_q(0.011, "Um"),
            flange_thickness=_q(0.025, "Um"),
        ),
    )

    section = _b()._build_section(raw)

    assert isinstance(section, IrTSection)
    assert section.id == "S1"
    assert section.name == "500X11 + 150X25 TEE"
    assert section.height.value == 0.5
    assert section.flange_thickness.value == 0.025


def test_build_section_unwraps_lbar_of_choice():
    """xsdata field names for L-bar overshoot choices are lbar_of / lbar_ow."""
    raw = BarSection(
        id="S2",
        name="L300x90 OF",
        guidref="g-s2",
        lbar_of=LbarOF(
            height=_q(0.3, "Um"),
            width=_q(0.09, "Um"),
            web_thickness=_q(0.012, "Um"),
            flange_thickness=_q(0.016, "Um"),
        ),
    )

    section = _b()._build_section(raw)

    assert isinstance(section, IrLSectionOvershootFlange)
    assert section.id == "S2"
    assert section.height.value == 0.3


# ===========================================================================
# Metadata
# ===========================================================================

def test_build_metadata_typed():
    v = IrVessel(id="v1")
    pp = _Stub(lpp=_q(200.0, "Um"), moulded_breadth=_q(32.0, "Um"),
               block_coefficient=_q(0.85), freeboard_type=_enum_stub("TypeB"))
    vessel_raw = _Stub(
        ship_designation=_Stub(ship_name="MV Test", call_sign="LXYZ",
                               number_imo="1234567", ship_type="Bulk"),
        tonnage_data=_Stub(tonnage=_q(50000.0, "UGT"), dead_weight=_q(80000.0, "Ut")),
        statutory_data=_Stub(port_registration="Oslo", flag_state="NO"),
        builder_information=_Stub(yard="Yard X", designer="D", owner="O", year_of_build="2026"),
        classification_data=_Stub(society_name="DNV", principal_particulars=pp),
    )
    _b()._build_metadata(vessel_raw, v)
    assert v.ship_designation.ship_name == "MV Test"
    assert v.ship_designation.number_imo == "1234567"
    assert v.tonnage_data.tonnage.value == 50000.0 and v.tonnage_data.dead_weight.value == 80000.0
    assert v.statutory_data.flag_state == "NO"
    assert v.builder_info.yard == "Yard X" and v.builder_info.year_of_build == "2026"
    assert v.principal_particulars.lpp.value == 200.0
    assert v.principal_particulars.freeboard_type == "TypeB"
    assert v.classification["classification_society"] == "DNV"


def test_build_header():
    v = IrVessel(id="v1")
    root = _Stub(header=_Stub(
        time_stamp="2024-09-18T21:48:11+03:00", name="D-VLCC/A", author="MJ",
        organization="NAPA LTD", originating_system="NAPA Steel",
        application_version="B9999", documentation="OCX Export"))
    _b()._build_header(root, v)
    assert v.header.time_stamp == "2024-09-18T21:48:11+03:00"
    assert v.header.author == "MJ"
    assert v.header.organization == "NAPA LTD"
    assert v.header.originating_system == "NAPA Steel"


def test_build_header_missing_is_none():
    v = IrVessel(id="v1")
    _b()._build_header(_Stub(header=None), v)
    assert v.header is None


# ===========================================================================
# Cargoes
# ===========================================================================

def test_build_cargoes_for_compartment():
    v = IrVessel(id="v1")
    comp = _Stub(
        id="C1", guidref="g-c1",
        liquid_cargo=[_Stub(density=_q(1.025, "UKgOverm3"),
                            carriage_pressure=_q(0.0),
                            liquid_cargo_type=_enum_stub("Ballast"))],
        bulk_cargo=[_Stub(stowage_factor=_q(1.2), permeability=_q(0.95),
                          angle_of_repose=_q(30.0, "Udeg"),
                          bulk_cargo_type=_enum_stub("Grain"))],
        unit_cargo=[_Stub(unit_cargo_type=_enum_stub("Container"))],
    )
    _b()._build_cargoes_for_compartment(comp, v)
    assert "C1/liquid/0" in v.liquid_cargoes
    lc = v.liquid_cargoes["C1/liquid/0"]
    assert lc.density.value == 1.025 and lc.cargo_type == "Ballast"
    assert lc.compartment_ref.local_ref == "C1" and lc.compartment_ref.guidref == "g-c1"
    bc = v.bulk_cargoes["C1/bulk/0"]
    assert bc.permeability.value == 0.95 and bc.cargo_type == "Grain"
    assert v.unit_cargoes["C1/unit/0"].cargo_type == "Container"


def test_build_cargoes_for_compartment_accepts_single_cargo_objects():
    v = IrVessel(id="v1")
    comp = _Stub(
        id="C1",
        liquid_cargo=_Stub(liquid_cargo_type=_enum_stub("Ballast")),
        bulk_cargo=_Stub(bulk_cargo_type=_enum_stub("Grain")),
        unit_cargo=_Stub(unit_cargo_type=_enum_stub("Container")),
    )

    _b()._build_cargoes_for_compartment(comp, v)

    assert v.liquid_cargoes["C1/liquid/0"].cargo_type == "Ballast"
    assert v.bulk_cargoes["C1/bulk/0"].cargo_type == "Grain"
    assert v.unit_cargoes["C1/unit/0"].cargo_type == "Container"


# ===========================================================================
# Seams + end cuts
# ===========================================================================

def test_build_seams_for_panel():
    v = IrVessel(id="v1")
    seg = Line3D(start_point=_pt(0, 0, 0), end_point=_pt(1, 0, 0), curve_length=None)
    composite = CompositeCurve3D(line3_d=[seg], poly_line3_d=[], circum_arc3_d=[],
                                 circle3_d=[], ellipse3_d=[], nurbs3_d=[], curve_length=None)
    panel_raw = _Stub(split_by=_Stub(seam=[_Stub(id="SE1", name="seam-1", guidref="g1",
                                                  trace_line=_Stub(composite_curve3_d=composite))]))
    ids = _b()._build_seams_for_panel(panel_raw, v)
    assert ids == ["SE1"]
    assert "SE1" in v.seams
    assert isinstance(v.seams["SE1"].trace_line, IrCompositeCurve3D)


def test_build_seams_none_split():
    v = IrVessel(id="v1")
    assert _b()._build_seams_for_panel(_Stub(split_by=None), v) == []


def test_build_end_cut():
    ec = _Stub(id="EC1", name="cut", cutback_distance=_q(50.0), web_cut_back_angle=_q(30.0, "Udeg"),
               web_nose_height=_q(10.0), flange_cut_back_angle=_q(20.0, "Udeg"),
               flange_nose_height=_q(5.0), symmetric_flange=True, sniped=True,
               feature_cope=_Stub(id="FC1", name="cope"))
    ir = _b()._build_end_cut(ec)
    assert isinstance(ir, IrEndCut)
    assert ir.sniped is True and ir.symmetric_flange is True
    assert ir.cutback_distance.value == 50.0
    assert ir.feature_cope.id == "FC1"
    assert _b()._build_end_cut(None) is None


# ===========================================================================
# Design view
# ===========================================================================

def test_build_design_view_recursive():
    v = IrVessel(id="v1")
    occ = _Stub(id="O1", name="occ", type_value="plate",
                plate_ref=_ref_stub("P1", "g-p1"))
    inner = _Stub(id="G-inner", name="inner", type_value=None,
                  occurrence=[occ], occurrence_group=[])
    dv = _Stub(id="DV1", name="view", vessel_ref=_ref_stub("v1"),
               occurrence_group=[inner], occurrence=[])
    _b()._build_design_view(dv, v)
    assert "DV1" in v.design_views
    view = v.design_views["DV1"]
    assert view.vessel_ref.local_ref == "v1"
    grp = view.children[0]
    assert isinstance(grp, IrOccurrenceGroup)
    leaf = grp.children[0]
    assert isinstance(leaf, IrOccurrence)
    assert leaf.plate_ref.local_ref == "P1" and leaf.type_value == "plate"


# ===========================================================================
# Hole catalogue
# ===========================================================================

def test_build_hole_catalogue():
    v = IrVessel(id="v1")
    circle = Circle3D(center=_pt(0, 0, 0), diameter=_q(100.0), normal=_vec(0, 0, 1),
                      curve_length=None)
    cat = _Stub(id="HC1", name="holes",
                hole2_d=[_Stub(id="H1", name="hole-1", guidref="g-h1",
                               contour=_Stub(circle3_d=[circle]),
                               rectangular_hole=None, super_elliptical=None,
                               symmetrical_hole=None, parametric_circle=None)])
    _b()._build_hole_catalogue(cat, v)
    assert v.hole_shape_catalogue is not None
    hole = v.hole_shape_catalogue.holes["H1"]
    assert isinstance(hole.contour, IrCircle3D)
    assert hole.contour.diameter.value == 100.0


def test_build_hole_catalogue_parametric_variant():
    v = IrVessel(id="v1")
    cat = _Stub(id="HC2", name=None,
                hole2_d=[_Stub(id="H2", name=None, guidref=None, contour=None,
                               rectangular_hole=_Stub(), super_elliptical=None,
                               symmetrical_hole=None, parametric_circle=None)])
    _b()._build_hole_catalogue(cat, v)
    assert v.hole_shape_catalogue.holes["H2"].parametric == {"variant": "rectangular_hole"}
