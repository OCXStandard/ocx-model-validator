"""Builder population of cross-section IR fields (spec §3)."""
from types import SimpleNamespace as NS

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir.base import ParentKind, ParentRef
from ocx_model_validator.model.ir.geometry import IrCircle3D, IrCompositeCurve3D, IrLine3D
from ocx_model_validator.model.ir.structural import IrVessel

PARENT = ParentRef(kind=ParentKind.PANEL, id="panel1")


class Line3D:  # class name drives _build_curve dispatch
    def __init__(self, start, end):
        self.id = None
        self.curve_length = None
        self.start_point = start
        self.end_point = end


class CompositeCurve3D:
    def __init__(self, lines):
        self.id = "cc1"
        self.curve_length = None
        self.line3_d = lines
        self.poly_line3_d = []
        self.circum_arc3_d = []
        self.circle3_d = []
        self.ellipse3_d = []
        self.nurbs3_d = []


class Nurbs3D:
    def __init__(self):
        self.id = None
        self.curve_length = None
        self.nurbsproperties = NS(degree=1, is_rational=True, form=None)
        self.knot_vector = NS(value=[0.0, 0.0, 1.0, 1.0])
        self.control_pt_list = NS(control_point=[
            NS(coordinates=[0.0, 0.0, 0.0], unit="Um", weight=1.0),
            NS(coordinates=[1.0, 0.0, 0.0], unit="Um", weight=0.5),
        ])


class CircumCircle3D:
    def __init__(self, points):
        self.id = None
        self.curve_length = None
        self.positions = NS(point3_d=points)


def _pt(x, y, z):
    return NS(coordinates=[x, y, z], unit="Um")


def _line(x1, x2):
    return Line3D(_pt(x1, 0.0, 0.0), _pt(x2, 0.0, 0.0))


def test_stiffener_trace_populated():
    raw = NS(id="st1", name="L1", guidref=None, physical_properties=None,
             material_ref=None, section_ref=None, function_type=None,
             end_cut_end1=None, end_cut_end2=None,
             trace_line=NS(composite_curve3_d=CompositeCurve3D([_line(0.0, 10.0)])))
    stiff = OcxV3Builder()._build_stiffener(raw, PARENT)
    assert isinstance(stiff.trace, IrCompositeCurve3D)
    assert isinstance(stiff.trace.segments[0], IrLine3D)


def test_plate_outer_contour_single_curve():
    raw = NS(id="pl1", name=None, guidref=None, plate_material=None,
             physical_properties=None, net_area=None, function_type=None,
             outer_contour=NS(composite_curve3_d=CompositeCurve3D([_line(0.0, 1.0)]),
                              nurbs3_d=None, line3_d=None, poly_line3_d=None,
                              circum_arc3_d=None, ellipse3_d=None, circle3_d=None))
    plate = OcxV3Builder()._build_plate(raw, PARENT)
    assert isinstance(plate.outer_contour, IrCompositeCurve3D)


def test_plate_outer_contour_absent():
    raw = NS(id="pl2", name=None, guidref=None, plate_material=None,
             physical_properties=None, net_area=None, function_type=None,
             outer_contour=None)
    assert OcxV3Builder()._build_plate(raw, PARENT).outer_contour is None


def test_nurbs_weights_populated():
    curve = OcxV3Builder()._build_curve(Nurbs3D())
    assert curve.weights == [1.0, 0.5]


def test_circum_circle_contour_does_not_build_degenerate_circle():
    contour = NS(composite_curve3_d=None, nurbs3_d=None, line3_d=None,
                 poly_line3_d=None, circum_arc3_d=None, ellipse3_d=None,
                 circle3_d=None,
                 circum_circle3_d=CircumCircle3D([
                     _pt(0.0, 0.0, 0.0),
                     _pt(1.0, 0.0, 0.0),
                     _pt(0.0, 1.0, 0.0),
                 ]))

    curve = OcxV3Builder()._build_contour(contour)

    assert curve is None or not (
        isinstance(curve, IrCircle3D)
        and curve.center is None
        and curve.diameter is None
        and curve.normal is None
    )


def test_ref_plane_location_populated():
    ir = IrVessel(id="v1")
    cs = NS(id="cs1", name=None, is_global=True, local_cartesian=None,
            xref_planes=NS(ref_plane=[
                NS(id="X0", name="X0",
                   reference_location=NS(numericvalue=0.0, unit="Um")),
                NS(id="X59", name="X59.2",
                   reference_location=NS(numericvalue=59.2, unit="Um")),
            ]),
            yref_planes=None, zref_planes=None)
    OcxV3Builder()._build_coordinate_system(cs, ir)
    assert ir.ref_planes["X59"].location.value == 59.2
    assert ir.ref_planes["X59"].location.unit == "Um"


def test_panel_unbounded_geometry_grid_ref():
    builder = OcxV3Builder()
    ug = builder._build_unbounded(NS(
        plane3_d=None, nurbssurface=None, extruded_surface=None,
        sphere3_d=None, cone3_d=None, cylinder3_d=None,
        grid_ref=NS(local_ref="X59", guidref=None), surface_ref=None))
    assert ug.grid_ref == "X59"
    assert ug.surface is None


def test_compartment_cog_populated():
    ir = IrVessel(id="v1")
    arrangement = NS(compartment=[NS(
        id="c1", name="WB1", guidref=None, compartment_purpose=None,
        compartment_face=[],
        compartment_properties=NS(
            center_of_gravity=NS(coordinates=[100.0, 0.0, 5.0], unit="Um"),
            volume=NS(numericvalue=1000.0, unit="Um3"), filling_height=None),
        liquid_cargo=[], bulk_cargo=[], unit_cargo=[])])
    OcxV3Builder()._build_compartments(arrangement, ir)
    assert ir.compartments["c1"].cog.x == 100.0
