"""Tests for elementary plate panel (EPP) splitting."""
from math import isclose, pi, sqrt

from ocx_model_validator.sections.epp import EppPlate, split_plates_to_epps
from ocx_model_validator.sections.section_builder import SectionPlate, SectionStiffener


def _plate(
    name="PL1",
    p1=(0.0, 0.0),
    p2=(3000.0, 0.0),
    panel="deck",
    thickness=12.0,
    radius=None,
    cy=None,
    cz=None,
) -> SectionPlate:
    return SectionPlate(
        name=name,
        y1_mm=p1[0],
        z1_mm=p1[1],
        y2_mm=p2[0],
        z2_mm=p2[1],
        thickness_mm=thickness,
        material_reh_mpa=315.0,
        panel=panel,
        radius_mm=radius,
        arc_center_y_mm=cy,
        arc_center_z_mm=cz,
        guidref="guid-1",
    )


def _stiff(name, y, z, panel="deck") -> SectionStiffener:
    return SectionStiffener(
        name=name,
        y_mm=y,
        z_mm=z,
        panel=panel,
        profile_type=None,
        profile_dimensions=None,
        material_reh_mpa=None,
        spacing_mm=None,
    )


def test_two_interior_stiffeners_give_three_epps() -> None:
    stiffs = [_stiff("S1", 1000.0, 0.0), _stiff("S2", 2000.0, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)

    assert [e.name for e in epps] == ["PL1_EPP1", "PL1_EPP2", "PL1_EPP3"]
    assert [(e.bound_lower, e.bound_upper) for e in epps] == [
        (None, "S1"),
        ("S1", "S2"),
        ("S2", None),
    ]
    assert all(isclose(e.breadth_mm, 1000.0) for e in epps)
    assert isclose(epps[0].y1_mm, 0.0) and isclose(epps[0].y2_mm, 1000.0)
    assert isclose(epps[1].y1_mm, 1000.0) and isclose(epps[1].y2_mm, 2000.0)
    assert isclose(epps[2].y1_mm, 2000.0) and isclose(epps[2].y2_mm, 3000.0)


def test_epps_inherit_plate_attributes() -> None:
    epps = split_plates_to_epps([_plate()], [_stiff("S1", 1000.0, 0.0)])
    for e in epps:
        assert isinstance(e, EppPlate)
        assert e.thickness_mm == 12.0
        assert e.material_reh_mpa == 315.0
        assert e.panel == "deck"
        assert e.guidref == "guid-1"


def test_plate_without_stiffeners_is_single_epp() -> None:
    epps = split_plates_to_epps([_plate()], [])
    assert len(epps) == 1
    assert epps[0].name == "PL1_EPP1"
    assert epps[0].bound_lower is None and epps[0].bound_upper is None
    assert isclose(epps[0].breadth_mm, 3000.0)


def test_stiffener_at_plate_end_bounds_without_splitting() -> None:
    stiffs = [_stiff("S0", 0.0, 0.0), _stiff("S3", 3000.0, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 1
    assert epps[0].bound_lower == "S0"
    assert epps[0].bound_upper == "S3"


def test_other_panel_and_far_stiffeners_are_ignored() -> None:
    stiffs = [
        _stiff("OTHER", 1000.0, 0.0, panel="side"),
        _stiff("FAR", 1500.0, 100.0),  # 100 mm off the plate > snap_tol
    ]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 1


def test_coincident_stations_collapse_to_one_split() -> None:
    stiffs = [_stiff("A", 1500.0, 0.0), _stiff("B", 1500.5, 0.0)]
    epps = split_plates_to_epps([_plate()], stiffs)
    assert len(epps) == 2
    assert epps[0].bound_upper == "A"
    assert epps[1].bound_lower == "A"


def test_arc_plate_splits_by_arclength_and_keeps_arc_data() -> None:
    # Quarter bilge arc: center (0, 0), radius 1000, (1000, 0) -> (0, 1000).
    arc = _plate(
        name="BILGE",
        p1=(1000.0, 0.0),
        p2=(0.0, 1000.0),
        panel="shell",
        radius=1000.0,
        cy=0.0,
        cz=0.0,
    )
    r = 1000.0 / sqrt(2.0)
    epps = split_plates_to_epps([arc], [_stiff("S1", r, r, panel="shell")])

    assert len(epps) == 2
    quarter = pi / 2.0 * 1000.0
    assert isclose(epps[0].breadth_mm, quarter / 2.0, rel_tol=1e-6)
    assert isclose(epps[1].breadth_mm, quarter / 2.0, rel_tol=1e-6)
    # Split vertex lies on the arc at 45 degrees.
    assert isclose(epps[0].y2_mm, r, rel_tol=1e-6)
    assert isclose(epps[0].z2_mm, r, rel_tol=1e-6)
    # Sub-arcs keep radius and center.
    for e in epps:
        assert e.radius_mm == 1000.0
        assert e.arc_center_y_mm == 0.0 and e.arc_center_z_mm == 0.0
    assert (epps[0].bound_upper, epps[1].bound_lower) == ("S1", "S1")


def test_zero_length_plate_passes_through() -> None:
    degenerate = _plate(p1=(100.0, 100.0), p2=(100.0, 100.0))
    epps = split_plates_to_epps([degenerate], [_stiff("S1", 100.0, 100.0)])
    assert len(epps) == 1
    assert epps[0].breadth_mm == 0.0
