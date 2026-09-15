from __future__ import annotations

import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.base import Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCurve3D,
    IrLine3D,
    IrNurbs3D,
    IrPolyLine3D,
    IrVector3D,
)
from ocx_model_validator.model.ir.sections import (
    IrBulbFlatSection,
    IrFlatBarSection,
    IrLSection,
    IrLSectionOvershootFlange,
    IrLSectionOvershootWeb,
    IrTSection,
)
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener, IrVessel
from ocx_model_validator.sections.section_builder import _profile, build_cross_section
from tests.section_fixtures import four_hit_plate_contour, line, make_synthetic_vessel, p, parent, q, rectangle


@pytest.fixture
def vessel() -> IrVessel:
    return make_synthetic_vessel()


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
    assert stiffener.section_kind == "bulb_flat"
    assert stiffener.h_mm == pytest.approx(300.0)
    assert stiffener.bf_mm is None
    assert stiffener.tw_mm == pytest.approx(11.0)
    assert stiffener.tf_mm is None
    assert stiffener.material_reh_mpa == pytest.approx(315.0)
    assert stiffener.orientation == "Longitudinal"
    assert stiffener.web_angle_deg == pytest.approx(90.0)


def test_missing_section_ref_warns_but_stiffener_is_emitted(vessel: IrVessel) -> None:
    section = build_cross_section(vessel, 5000.0)

    stiffener = next(s for s in section.stiffeners if s.name == "A missing profile")
    assert stiffener.profile_type is None
    assert stiffener.profile_dimensions is None
    assert stiffener.section_kind is None
    assert stiffener.h_mm is None
    assert stiffener.bf_mm is None
    assert stiffener.tw_mm is None
    assert stiffener.tf_mm is None
    assert stiffener.material_reh_mpa == pytest.approx(315.0)
    assert any("A missing profile" in warning and "section" in warning.lower() for warning in section.warnings)


def test_profile_returns_numeric_dimensions_for_flat_bar() -> None:
    vessel = IrVessel(id="vessel")
    vessel.sections["fb"] = IrFlatBarSection(id="fb", height=q(250.0, "Umm"), width=q(12.0, "Umm"))
    stiffener = IrStiffener(id="stiff", parent_ref=parent("panel"), section_ref=Ref("fb"))
    warnings: list[str] = []

    assert _profile(stiffener, vessel, warnings, "Flat") == (
        "FlatBar",
        "250 x 12",
        "flat_bar",
        pytest.approx(250.0),
        None,
        pytest.approx(12.0),
        None,
    )
    assert warnings == []


def test_profile_returns_numeric_dimensions_for_t_section() -> None:
    vessel = IrVessel(id="vessel")
    vessel.sections["t"] = IrTSection(
        id="t",
        height=q(400.0, "Umm"),
        width=q(150.0, "Umm"),
        web_thickness=q(9.0, "Umm"),
        flange_thickness=q(14.0, "Umm"),
    )
    stiffener = IrStiffener(id="stiff", parent_ref=parent("panel"), section_ref=Ref("t"))

    profile_type, dims, section_kind, h_mm, bf_mm, tw_mm, tf_mm = _profile(stiffener, vessel, [], "T")

    assert profile_type == "TBar"
    assert dims == "400 x 150 x 9 x 14"
    assert section_kind == "t_section"
    assert (h_mm, bf_mm, tw_mm, tf_mm) == pytest.approx((400.0, 150.0, 9.0, 14.0))


@pytest.mark.parametrize(
    ("section", "expected_kind"),
    [
        (
            IrLSection(
                id="l",
                height=q(300.0, "Umm"),
                width=q(100.0, "Umm"),
                web_thickness=q(8.0, "Umm"),
                flange_thickness=q(12.0, "Umm"),
            ),
            "l_section",
        ),
        (
            IrLSectionOvershootFlange(
                id="lof",
                height=q(310.0, "Umm"),
                width=q(110.0, "Umm"),
                web_thickness=q(9.0, "Umm"),
                flange_thickness=q(13.0, "Umm"),
            ),
            "l_overshoot_flange",
        ),
        (
            IrLSectionOvershootWeb(
                id="low",
                height=q(320.0, "Umm"),
                width=q(120.0, "Umm"),
                web_thickness=q(10.0, "Umm"),
                flange_thickness=q(14.0, "Umm"),
            ),
            "l_overshoot_web",
        ),
    ],
)
def test_profile_distinguishes_l_section_variants(section, expected_kind: str) -> None:
    vessel = IrVessel(id="vessel")
    vessel.sections[section.id] = section
    stiffener = IrStiffener(id="stiff", parent_ref=parent("panel"), section_ref=Ref(section.id))

    profile_type, _, section_kind, h_mm, bf_mm, tw_mm, tf_mm = _profile(stiffener, vessel, [], "L")

    assert profile_type == "AngleBar"
    assert section_kind == expected_kind
    assert (h_mm, bf_mm, tw_mm, tf_mm) == pytest.approx(
        (
            section.height.value,
            section.width.value,
            section.web_thickness.value,
            section.flange_thickness.value,
        )
    )


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


def _bilge_profile_mm() -> list[tuple[float, float]]:
    """Bottom-arc-side profile with the arc discretized on a R=500 circle."""
    from math import cos, radians, sin

    points = [(0.0, 0.0), (1000.0, 0.0)]
    for deg in (-67.5, -45.0, -22.5):
        points.append((1000.0 + 500.0 * cos(radians(deg)), 500.0 + 500.0 * sin(radians(deg))))
    points += [(1500.0, 500.0), (1500.0, 1500.0)]
    return points


def test_prismatic_polyline_contour_decomposes_into_bottom_arc_and_side(vessel: IrVessel) -> None:
    # OCX models often tessellate the bilge arc into a polyline (or a
    # polygon-encoded NURBS). The section trace must keep the full profile —
    # straight bottom, canonical-radius bilge arc, straight side — instead of
    # collapsing the plate to a single corner-cutting chord.
    profile = _bilge_profile_mm()
    forward = [p(4.0, y / 1000.0, z / 1000.0) for y, z in profile]
    aft = [p(6.0, y / 1000.0, z / 1000.0) for y, z in reversed(profile)]
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["shell-plate"])
    vessel.plates["shell-plate"] = IrPlate(
        id="shell-plate",
        parent_ref=parent("panel-c"),
        name="Shell plate",
        material_ref=Ref("mat315"),
        thickness=q(15.0, "Umm"),
        outer_contour=IrPolyLine3D(curve_length=None, vertices=forward + aft, is_closed=True),
    )

    section = build_cross_section(vessel, 5000.0)

    plates = [pl for pl in section.plates if pl.name == "Shell plate"]
    assert len(plates) == 3

    def endpoints(pl) -> set[tuple[float, float]]:
        return {(round(pl.y1_mm, 1), round(pl.z1_mm, 1)), (round(pl.y2_mm, 1), round(pl.z2_mm, 1))}

    bottom = next(pl for pl in plates if endpoints(pl) == {(0.0, 0.0), (1000.0, 0.0)})
    arc = next(pl for pl in plates if endpoints(pl) == {(1000.0, 0.0), (1500.0, 500.0)})
    side = next(pl for pl in plates if endpoints(pl) == {(1500.0, 500.0), (1500.0, 1500.0)})
    assert bottom.radius_mm is None
    assert side.radius_mm is None
    assert arc.radius_mm == pytest.approx(500.0, abs=0.5)
    assert arc.arc_center_y_mm == pytest.approx(1000.0, abs=0.5)
    assert arc.arc_center_z_mm == pytest.approx(500.0, abs=0.5)
    assert all(pl.thickness_mm == pytest.approx(15.0) for pl in plates)
    assert all(pl.panel == "Panel C" for pl in plates)


def test_prismatic_polygon_encoded_nurbs_contour_decomposes_into_bottom_arc_and_side(
    vessel: IrVessel,
) -> None:
    # Real OCX models encode the tessellated contour as a NURBS whose knot
    # spans are all straight. Sampling inside those spans puts points on the
    # polygon chords (off the true circle), so the trace must collapse straight
    # spans to their endpoints before arc decomposition.
    profile = _bilge_profile_mm()
    ring = [p(4.0, y / 1000.0, z / 1000.0) for y, z in profile]
    ring += [p(6.0, y / 1000.0, z / 1000.0) for y, z in reversed(profile)]
    ring.append(ring[0])
    count = len(ring)
    knots = [0.0, 0.0] + [float(i) for i in range(1, count - 1)] + [float(count - 1)] * 2
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["shell-plate"])
    vessel.plates["shell-plate"] = IrPlate(
        id="shell-plate",
        parent_ref=parent("panel-c"),
        name="Shell plate",
        material_ref=Ref("mat315"),
        thickness=q(15.0, "Umm"),
        outer_contour=IrNurbs3D(
            curve_length=None,
            degree=1,
            knot_vector=knots,
            control_points=ring,
        ),
    )

    section = build_cross_section(vessel, 5000.0)

    plates = [pl for pl in section.plates if pl.name == "Shell plate"]
    assert len(plates) == 3
    arc = next(pl for pl in plates if pl.radius_mm is not None)
    assert arc.radius_mm == pytest.approx(500.0, abs=0.5)
    assert arc.arc_center_y_mm == pytest.approx(1000.0, abs=0.5)
    assert arc.arc_center_z_mm == pytest.approx(500.0, abs=0.5)


def test_decompose_trace_merges_arc_runs_split_by_vertex_noise() -> None:
    # Real tessellations carry ~0.5 mm radial noise on the arc vertices, which
    # breaks the greedy arc fit mid-arc. Adjacent arc runs on the same circle
    # must be merged back into a single canonical arc.
    from math import cos, radians, sin

    from ocx_model_validator.sections.section_builder import _decompose_trace

    trace = [(0.0, 0.0), (1000.0, 0.0)]
    for index in range(1, 26):
        deg = -90.0 + 90.0 * index / 26.0
        radius = 2600.0 + 0.5 * sin(radians(360.0 * index / 9.0))
        trace.append((1000.0 + radius * cos(radians(deg)), 2600.0 + radius * sin(radians(deg))))
    trace += [(3600.0, 2600.0), (3600.0, 5000.0)]

    segments = _decompose_trace(trace)
    arcs = [seg for seg in segments if seg[2] is not None]
    assert len(arcs) == 1
    assert arcs[0][2] == pytest.approx(2600.0, abs=2.0)


def test_plate_records_transverse_arc_radius_and_center(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["bilge-plate"])
    vessel.plates["bilge-plate"] = IrPlate(
        id="bilge-plate",
        parent_ref=parent("panel-c"),
        name="Bilge plate",
        material_ref=Ref("mat315"),
        thickness=q(10.0, "Umm"),
        outer_contour=IrCompositeCurve3D(
            curve_length=None,
            segments=[
                IrLine3D(curve_length=None, start=p(4.0, 0.0, 0.0), end=p(6.0, 0.0, 0.0)),
                IrLine3D(curve_length=None, start=p(4.0, 2.0, 0.0), end=p(6.0, 2.0, 0.0)),
                IrCircumArc3D(
                    curve_length=None,
                    start=p(5.0, 1.0, 1.0),
                    intermediate=p(5.0, 0.5 + 0.5 / 2**0.5, 1.0 + 0.5 / 2**0.5),
                    end=p(5.0, 0.5, 1.5),
                ),
            ],
        ),
    )

    section = build_cross_section(vessel, 5000.0)

    plate = next(p for p in section.plates if p.name == "Bilge plate")
    assert plate.radius_mm == pytest.approx(500.0)
    assert plate.arc_center_y_mm == pytest.approx(500.0)
    assert plate.arc_center_z_mm == pytest.approx(1000.0)


def test_plate_ignores_longitudinal_arc_radius_and_center(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["longitudinal-arc-plate"])
    vessel.plates["longitudinal-arc-plate"] = IrPlate(
        id="longitudinal-arc-plate",
        parent_ref=parent("panel-c"),
        name="Longitudinal arc plate",
        material_ref=Ref("mat315"),
        thickness=q(10.0, "Umm"),
        outer_contour=IrCompositeCurve3D(
            curve_length=None,
            segments=[
                IrLine3D(curve_length=None, start=p(4.0, 0.0, 0.0), end=p(6.0, 0.0, 0.0)),
                IrLine3D(curve_length=None, start=p(4.0, 2.0, 0.0), end=p(6.0, 2.0, 0.0)),
                IrCircumArc3D(
                    curve_length=None,
                    start=p(5.5, 0.5, 1.0),
                    intermediate=p(5.0 + 0.5 / 2**0.5, 0.5 + 0.5 / 2**0.5, 1.0),
                    end=p(5.0, 1.0, 1.0),
                ),
            ],
        ),
    )

    section = build_cross_section(vessel, 5000.0)

    plate = next(p for p in section.plates if p.name == "Longitudinal arc plate")
    assert plate.radius_mm is None
    assert plate.arc_center_y_mm is None
    assert plate.arc_center_z_mm is None


def test_plate_records_transverse_circle_radius_and_center(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["circle-plate"])
    vessel.plates["circle-plate"] = IrPlate(
        id="circle-plate",
        parent_ref=parent("panel-c"),
        name="Circle plate",
        material_ref=Ref("mat315"),
        thickness=q(10.0, "Umm"),
        outer_contour=IrCompositeCurve3D(
            curve_length=None,
            segments=[
                IrLine3D(curve_length=None, start=p(4.0, 0.0, 0.0), end=p(6.0, 0.0, 0.0)),
                IrLine3D(curve_length=None, start=p(4.0, 2.0, 0.0), end=p(6.0, 2.0, 0.0)),
                IrCircle3D(
                    curve_length=None,
                    center=p(5.0, 0.75, 1.25),
                    diameter=q(1.2, "Um"),
                    normal=IrVector3D(1.0, 0.0, 0.0),
                ),
            ],
        ),
    )

    section = build_cross_section(vessel, 5000.0)

    plate = next(p for p in section.plates if p.name == "Circle plate")
    assert plate.radius_mm == pytest.approx(600.0)
    assert plate.arc_center_y_mm == pytest.approx(750.0)
    assert plate.arc_center_z_mm == pytest.approx(1250.0)


def test_plate_segments_with_non_monotonic_z_are_paired_along_principal_axis(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Panel C", plate_ids=["cambered-plate"])
    vessel.plates["cambered-plate"] = IrPlate(
        id="cambered-plate",
        parent_ref=parent("panel-c"),
        name="Cambered hatch plate",
        material_ref=Ref("mat315"),
        thickness=q(14.0, "Umm"),
        outer_contour=four_hit_plate_contour(),
    )

    section = build_cross_section(vessel, 5000.0)

    segments = [plate for plate in section.plates if plate.name == "Cambered hatch plate"]
    assert [(s.y1_mm, s.z1_mm, s.y2_mm, s.z2_mm) for s in segments] == pytest.approx(
        [
            (0.0, 0.0, 2000.0, 50.0),
            (3000.0, 45.0, 6000.0, 0.0),
        ]
    )


def test_stiffeners_without_panel_do_not_get_spacing_from_each_other(vessel: IrVessel) -> None:
    vessel.stiffeners["orphan-1"] = IrStiffener(
        id="orphan-1",
        parent_ref=parent("missing-panel"),
        name="Orphan 1",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(10.0, 0.1),
    )
    vessel.stiffeners["orphan-2"] = IrStiffener(
        id="orphan-2",
        parent_ref=parent("missing-panel"),
        name="Orphan 2",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(11.0, 0.1),
    )

    section = build_cross_section(vessel, 5000.0)

    by_name = {stiffener.name: stiffener for stiffener in section.stiffeners}
    assert by_name["Orphan 1"].spacing_mm is None
    assert by_name["Orphan 2"].spacing_mm is None
    assert any("stiffener Orphan 1:" in warning and "panel" in warning.lower() for warning in section.warnings)
    assert any("stiffener Orphan 2:" in warning and "panel" in warning.lower() for warning in section.warnings)


def test_stiffener_spacing_uses_panel_id_not_display_name(vessel: IrVessel) -> None:
    vessel.panels["panel-c"] = IrPanel(id="panel-c", name="Repeated", stiffener_ids=["same-name-c"])
    vessel.panels["panel-d"] = IrPanel(id="panel-d", name="Repeated", stiffener_ids=["same-name-d"])
    vessel.stiffeners["same-name-c"] = IrStiffener(
        id="same-name-c",
        parent_ref=parent("panel-c"),
        name="Same name C",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(12.0, 0.1),
    )
    vessel.stiffeners["same-name-d"] = IrStiffener(
        id="same-name-d",
        parent_ref=parent("panel-d"),
        name="Same name D",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(13.0, 0.1),
    )

    section = build_cross_section(vessel, 5000.0)

    by_name = {stiffener.name: stiffener for stiffener in section.stiffeners}
    assert by_name["Same name C"].panel == "Repeated"
    assert by_name["Same name D"].panel == "Repeated"
    assert by_name["Same name C"].spacing_mm is None
    assert by_name["Same name D"].spacing_mm is None


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
    assert any(
        "plate Bad thickness plate:" in warning and "Ubad" in warning
        for warning in section.warnings
    )


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
    assert any(
        "stiffener Bad dims stiffener:" in warning and "Ubad" in warning
        for warning in section.warnings
    )


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
    assert any(
        "stiffener Bad material stiffener:" in warning and "Ubad" in warning
        for warning in section.warnings
    )


def _vessel_with_seam(seam_trace):
    from dataclasses import replace as dc_replace
    from ocx_model_validator.model.ir.structural import IrSeam

    vessel = make_synthetic_vessel()
    vessel.seams["seam-1"] = IrSeam(id="seam-1", name="SM1", trace_line=seam_trace)
    vessel.panels["panel-a"] = dc_replace(vessel.panels["panel-a"], seam_ids=["seam-1"])
    return vessel


def test_build_cross_section_collects_seam_intersections() -> None:
    # line(1.0, 0.0) runs x=0..10 m at y=1 m, z=0: crosses the x=5000 mm plane once.
    vessel = _vessel_with_seam(line(1.0, 0.0))

    section = build_cross_section(vessel, 5000.0)

    assert len(section.seams) == 1
    seam = section.seams[0]
    assert seam.name == "SM1"
    assert seam.panel == "Panel A"
    assert seam.y_mm == pytest.approx(1000.0)
    assert seam.z_mm == pytest.approx(0.0)


def test_build_cross_section_skips_seam_missing_the_plane() -> None:
    vessel = _vessel_with_seam(line(1.0, 0.0, start_x=0.0, end_x=4.0))  # ends before x=5 m

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []


def test_build_cross_section_warns_on_seam_geometry_error() -> None:
    from ocx_model_validator.model.ir.geometry import IrLine3D

    # IrLine3D without a start point makes intersect_curve_plane raise GeometryError.
    vessel = _vessel_with_seam(IrLine3D(curve_length=None, start=None, end=p(10.0, 1.0, 0.0)))

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []
    assert any(w.startswith("seam SM1:") for w in section.warnings)


def test_build_cross_section_skips_seam_without_trace_line() -> None:
    vessel = _vessel_with_seam(None)

    section = build_cross_section(vessel, 5000.0)

    assert section.seams == []
    assert not any("seam" in w for w in section.warnings)


def test_build_cross_section_collects_multiple_hits_per_seam() -> None:
    from ocx_model_validator.model.ir.geometry import IrPolyLine3D

    zigzag = IrPolyLine3D(
        curve_length=None,
        vertices=[p(0.0, 1.0, 0.0), p(6.0, 1.0, 0.0), p(6.0, 2.0, 0.0), p(0.0, 2.0, 0.0)],
        is_closed=False,
    )
    vessel = _vessel_with_seam(zigzag)

    section = build_cross_section(vessel, 5000.0)

    assert len(section.seams) == 2
    assert sorted((s.y_mm, s.z_mm) for s in section.seams) == [(1000.0, 0.0), (2000.0, 0.0)]


def test_section_plates_and_stiffeners_carry_guidref() -> None:
    vessel = make_synthetic_vessel()

    section = build_cross_section(vessel, 5000.0)

    plates = {plate.name: plate for plate in section.plates}
    assert plates["Plate A1"].guidref == "plate-a1-guid"
    assert plates["Plate A2"].guidref is None
    stiffeners = {stiffener.name: stiffener for stiffener in section.stiffeners}
    assert stiffeners["A bulb"].guidref == "stiff-a1-guid"
    assert stiffeners["B alone"].guidref is None
