"""Unit tests for new structural IR types and field additions."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrEndCut,
    IrFeatureCope,
    IrMember,
    IrPanel,
    IrPenetration,
    IrPoint3D,
    IrSeam,
    IrStiffener,
    ParentKind,
    ParentRef,
    Quantity,
)


def test_seam_defaults_and_plate_refs():
    s = IrSeam(id="seam1")
    assert s.name is None
    assert s.plate_refs == []
    assert s.cog is None and s.function_type is None


def test_member_uses_point3d_for_cog():
    parent = ParentRef(kind=ParentKind.VESSEL, id="v1")
    m = IrMember(id="m1", parent_ref=parent)
    assert m.parent_ref is parent
    assert m.start_point is None and m.end_point is None
    m2 = IrMember(
        id="m2",
        parent_ref=parent,
        cog=IrPoint3D(1.0, 2.0, 3.0, "Um"),
    )
    assert isinstance(m2.cog, IrPoint3D)


def test_end_cut_defaults():
    e = IrEndCut()
    assert e.sniped is False
    assert e.cope_height is None
    e2 = IrEndCut(sniped=True, cope_height=Quantity(50.0, "Umm"))
    assert e2.sniped is True and e2.cope_height == Quantity(50.0, "Umm")


def test_feature_cope_defaults():
    fc = IrFeatureCope(id="fc1")
    assert fc.cope_radius is None and fc.name is None


def test_stiffener_new_fields_default_empty():
    parent = ParentRef(kind=ParentKind.PANEL, id="p1")
    st = IrStiffener(id="st1", parent_ref=parent)
    assert st.end_cut_start is None and st.end_cut_end is None
    assert st.penetrations == []
    st2 = IrStiffener(
        id="st2",
        parent_ref=parent,
        end_cut_start=IrEndCut(sniped=True),
        penetrations=[IrPenetration(id="pen1")],
    )
    assert st2.end_cut_start.sniped is True
    assert st2.penetrations[0].id == "pen1"


def test_panel_new_ref_lists_default_empty():
    p = IrPanel(id="panel1")
    assert p.seam_ids == []
    assert p.member_ids == []
    assert p.hole_shape_refs == []
