from __future__ import annotations

import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import IrCurve3D, IrLine3D, IrPoint3D, IrPolyLine3D
from ocx_model_validator.model.ir.sections import IrBulbFlatSection
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener, IrVessel
from ocx_model_validator.sections.section_builder import build_cross_section


def q(value: float, unit: str) -> Quantity:
    return Quantity(value, unit)


def p(x: float, y: float, z: float, unit: str = "Um") -> IrPoint3D:
    return IrPoint3D(x=x, y=y, z=z, unit=unit)


def line(y: float, z: float, start_x: float = 0.0, end_x: float = 10.0) -> IrLine3D:
    return IrLine3D(curve_length=None, start=p(start_x, y, z), end=p(end_x, y, z))


def rectangle(y1: float, y2: float, z: float) -> IrPolyLine3D:
    return IrPolyLine3D(
        curve_length=None,
        vertices=[p(4.0, y1, z), p(6.0, y1, z), p(6.0, y2, z), p(4.0, y2, z)],
        is_closed=True,
    )


def parent(panel_id: str) -> ParentRef:
    return ParentRef(ParentKind.PANEL, panel_id)


@pytest.fixture
def vessel() -> IrVessel:
    vessel = IrVessel(id="vessel-1")
    vessel.materials["mat315"] = IrMaterial(
        id="mat315",
        name="NV-NS",
        yield_stress=q(315e6, "UPa"),
    )
    vessel.sections["hp300"] = IrBulbFlatSection(
        id="hp300",
        name="HP 300x11",
        height=q(300.0, "Umm"),
        web_thickness=q(11.0, "Umm"),
    )
    vessel.panels["panel-a"] = IrPanel(
        id="panel-a",
        name="Panel A",
        plate_ids=["plate-a1", "plate-a2"],
        stiffener_ids=["stiff-a1", "stiff-a2", "stiff-a-no-cross"],
    )
    vessel.panels["panel-b"] = IrPanel(
        id="panel-b",
        name="Panel B",
        stiffener_ids=["stiff-b1"],
    )
    vessel.plates["plate-a1"] = IrPlate(
        id="plate-a1",
        parent_ref=parent("panel-a"),
        name="Plate A1",
        material_ref=Ref("mat315"),
        thickness=q(12.5, "Umm"),
        outer_contour=rectangle(0.0, 2.0, 0.0),
    )
    vessel.plates["plate-a2"] = IrPlate(
        id="plate-a2",
        parent_ref=parent("panel-a"),
        name="Plate A2",
        material_ref=Ref("mat315"),
        thickness=q(10.0, "Umm"),
        outer_contour=rectangle(0.0, 2.0, 1.0),
    )
    vessel.stiffeners["stiff-a1"] = IrStiffener(
        id="stiff-a1",
        parent_ref=parent("panel-a"),
        name="A bulb",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(0.4, 0.1),
    )
    vessel.stiffeners["stiff-a2"] = IrStiffener(
        id="stiff-a2",
        parent_ref=parent("panel-a"),
        name="A missing profile",
        material_ref=Ref("mat315"),
        trace=line(1.2, 0.1),
    )
    vessel.stiffeners["stiff-a-no-cross"] = IrStiffener(
        id="stiff-a-no-cross",
        parent_ref=parent("panel-a"),
        name="A no cross",
        trace=line(9.0, 9.0, start_x=0.0, end_x=4.0),
    )
    vessel.stiffeners["stiff-b1"] = IrStiffener(
        id="stiff-b1",
        parent_ref=parent("panel-b"),
        name="B alone",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(3.0, 0.2),
    )
    return vessel


def test_build_cross_section_records_x_frame_and_counts(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0, frame="42")

    assert section.x_mm == pytest.approx(5000.0)
    assert section.frame == "42"
    assert len(section.stiffeners) == 3
    assert len(section.plates) == 2


def test_bulb_flat_profile_and_material_are_resolved(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "A bulb")
    assert stiffener.y_mm == pytest.approx(400.0)
    assert stiffener.z_mm == pytest.approx(100.0)
    assert stiffener.panel == "Panel A"
    assert stiffener.profile_type == "HpBulb"
    assert stiffener.profile_dimensions == "300 x 11"
    assert stiffener.material_reh_mpa == pytest.approx(315.0)
    assert stiffener.orientation == "Longitudinal"
    assert stiffener.web_angle_deg == pytest.approx(90.0)


def test_missing_section_ref_warns_but_stiffener_is_emitted(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "A missing profile")
    assert stiffener.profile_type is None
    assert stiffener.profile_dimensions is None
    assert stiffener.material_reh_mpa == pytest.approx(315.0)
    assert any("A missing profile" in warning and "section" in warning.lower() for warning in section.warnings)


def test_spacing_is_nearest_neighbour_per_panel(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    by_name = {stiffener.name: stiffener for stiffener in section.stiffeners}
    assert by_name["A bulb"].spacing_mm == pytest.approx(800.0)
    assert by_name["A missing profile"].spacing_mm == pytest.approx(800.0)


def test_single_stiffener_on_panel_has_no_spacing_and_warning(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "B alone")
    assert stiffener.spacing_mm is None
    assert any("Panel B" in warning and "one stiffener" in warning.lower() for warning in section.warnings)


def test_stiffener_trace_that_does_not_cross_is_excluded(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    assert "A no cross" not in {stiffener.name for stiffener in section.stiffeners}


def test_plate_segments_are_paired_with_thickness_and_material(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    plate = next(p for p in section.plates if p.name == "Plate A1")
    assert plate.panel == "Panel A"
    assert plate.thickness_mm == pytest.approx(12.5)
    assert plate.material_reh_mpa == pytest.approx(315.0)
    assert (plate.y1_mm, plate.z1_mm, plate.y2_mm, plate.z2_mm) == pytest.approx(
        (0.0, 0.0, 2000.0, 0.0)
    )


def test_unknown_curve_becomes_warning_and_does_not_abort(vessel: IrVessel) -> None:
    vessel.stiffeners["bad-curve"] = IrStiffener(
        id="bad-curve",
        parent_ref=parent("panel-a"),
        name="Bad curve",
        trace=IrCurve3D(curve_length=None),
    )
    vessel.panels["panel-a"].stiffener_ids.append("bad-curve")

    section = build_cross_section(vessel, 5000.0)

    assert len(section.stiffeners) == 3
    assert any("stiffener Bad curve:" in warning and "Unsupported curve" in warning for warning in section.warnings)


def test_empty_section_raises(vessel: IrVessel) -> None:
    with pytest.raises(SectionError):
        build_cross_section(vessel, 20000.0)


def test_plate_odd_hits_warns_and_drops_leftover(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["odd-plate"])
    vessel.plates["odd-plate"] = IrPlate(
        id="odd-plate",
        parent_ref=parent("panel-c"),
        name="Odd plate",
        outer_contour=IrPolyLine3D(
            curve_length=None,
            vertices=[p(4.0, 0.0, 0.0), p(6.0, 0.0, 0.0), p(4.0, 1.0, 0.0), p(6.0, 2.0, 0.0)],
            is_closed=False,
        ),
    )

    section = build_cross_section(vessel, 5000.0)
    odd_segments = [plate for plate in section.plates if plate.name == "Odd plate"]

    assert len(odd_segments) == 1
    assert any("Odd plate" in warning and "odd" in warning.lower() for warning in section.warnings)


def test_plate_thickness_bad_unit_is_emitted_with_none_and_warning(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["plate-bad-thickness"])
    vessel.plates["plate-bad-thickness"] = IrPlate(
        id="plate-bad-thickness",
        parent_ref=parent("panel-c"),
        name="Bad thickness plate",
        material_ref=Ref("mat315"),
        thickness=q(12.0, "Ubad"),
        outer_contour=rectangle(0.0, 2.0, 0.0),
    )

    section = build_cross_section(vessel, 5000.0)

    plate = next(p for p in section.plates if p.name == "Bad thickness plate")
    assert plate.thickness_mm is None
    assert any("Bad thickness plate" in warning for warning in section.warnings)


def test_stiffener_section_dims_bad_unit_is_emitted_with_none_and_warning(vessel: IrVessel) -> None:
    vessel.sections["bad-bulb"] = IrBulbFlatSection(
        id="bad-bulb",
        name="Bad bulb",
        height=q(300.0, "Ubad"),
        web_thickness=q(11.0, "Umm"),
    )
    vessel.stiffeners["stiff-bad-dims"] = IrStiffener(
        id="stiff-bad-dims",
        parent_ref=parent("panel-a"),
        name="Bad dims stiffener",
        material_ref=Ref("mat315"),
        section_ref=Ref("bad-bulb"),
        trace=line(0.5, 0.1),
    )
    vessel.panels["panel-a"].stiffener_ids.append("stiff-bad-dims")

    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "Bad dims stiffener")
    assert stiffener.profile_type == "HpBulb"
    assert stiffener.profile_dimensions is None
    assert any("Bad dims stiffener" in warning for warning in section.warnings)


def test_stiffener_material_yield_bad_unit_is_emitted_with_none_and_warning(vessel: IrVessel) -> None:
    vessel.materials["bad-mat"] = IrMaterial(
        id="bad-mat",
        name="Bad material",
        yield_stress=q(315e6, "Ubad"),
    )
    vessel.stiffeners["stiff-bad-mat"] = IrStiffener(
        id="stiff-bad-mat",
        parent_ref=parent("panel-a"),
        name="Bad material stiffener",
        material_ref=Ref("bad-mat"),
        section_ref=Ref("hp300"),
        trace=line(1.5, 0.1),
    )
    vessel.panels["panel-a"].stiffener_ids.append("stiff-bad-mat")

    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "Bad material stiffener")
    assert stiffener.material_reh_mpa is None
    assert any("Bad material stiffener" in warning for warning in section.warnings)
