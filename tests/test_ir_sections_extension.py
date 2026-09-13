"""IR extensions for cross-section extraction (spec §3)."""
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, ParentKind, ParentRef, Quantity
from ocx_model_validator.model.ir.geometry import (
    IrLine3D,
    IrPlane3D,
    IrRefPlane,
    IrUnboundedGeometry,
)
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener

PARENT = ParentRef(kind=ParentKind.PANEL, id="panel1")


def test_plate_outer_contour_defaults_none():
    plate = IrPlate(id="p1", parent_ref=PARENT)
    assert plate.outer_contour is None


def test_plate_outer_contour_holds_curve():
    curve = IrLine3D(curve_length=None)
    plate = IrPlate(id="p1", parent_ref=PARENT, outer_contour=curve)
    assert plate.outer_contour is curve


def test_stiffener_trace_defaults_none():
    stiff = IrStiffener(id="s1", parent_ref=PARENT)
    assert stiff.trace is None


def test_panel_unbounded_geometry():
    panel = IrPanel(id="pn1")
    assert panel.unbounded_geometry is None
    ug = IrUnboundedGeometry(surface=IrPlane3D())
    panel2 = IrPanel(id="pn2", unbounded_geometry=ug)
    assert panel2.unbounded_geometry.grid_ref is None
    assert panel2.unbounded_geometry.surface_ref is None


def test_ref_plane_location():
    rp = IrRefPlane(id="X59", name="X59", location=Quantity(59.2, "Um"))
    assert rp.location.value == 59.2
    assert IrRefPlane(id="X0").location is None


def test_compartment_cog_is_ircog():
    c = IrCompartment(id="c1", cog=IrCog(100.0, 0.0, 5.0, "Um"))
    assert c.cog.x == 100.0
    assert IrCompartment(id="c2").cog is None
