from __future__ import annotations

import math

import pytest

from ocx_model_validator.sections.hmx_export import (
    _LSTIFF_TYPE,
    _MaterialIds,
    _angles,
    _arc_length_of,
    _arc_position,
    _chain_segments,
    _level1_code,
    _side,
    _signed_radius,
    _panel_chains,
    _split_closed_chains,
)
from ocx_model_validator.sections.section_builder import (
    SectionPlate,
    SectionStiffener,
    build_cross_section,
)
from tests.section_fixtures import make_synthetic_vessel


def plate(
    name: str,
    y1: float,
    z1: float,
    y2: float,
    z2: float,
    *,
    radius: float | None = None,
    center: tuple[float, float] | None = None,
    panel: str = "Panel",
) -> SectionPlate:
    return SectionPlate(
        name=name,
        y1_mm=y1,
        z1_mm=z1,
        y2_mm=y2,
        z2_mm=z2,
        thickness_mm=10.0,
        material_reh_mpa=315.0,
        panel=panel,
        radius_mm=radius,
        arc_center_y_mm=None if center is None else center[0],
        arc_center_z_mm=None if center is None else center[1],
    )


def stiffener(web_y: float | None, web_z: float | None) -> SectionStiffener:
    return SectionStiffener(
        name="S",
        y_mm=0.0,
        z_mm=0.0,
        panel="Panel",
        profile_type=None,
        profile_dimensions=None,
        material_reh_mpa=None,
        spacing_mm=None,
        web_dir_y=web_y,
        web_dir_z=web_z,
    )


def test_chaining_two_touching_plates_keeps_vertices_and_plate_order() -> None:
    first = plate("first", 0.0, 0.0, 1000.0, 0.0)
    second = plate("second", 1000.0, 0.0, 1000.0, 500.0)

    chains = _chain_segments([first, second])

    assert len(chains) == 1
    assert chains[0].points == pytest.approx([(0.0, 0.0), (1000.0, 0.0), (1000.0, 500.0)])
    assert chains[0].plates == [first, second]


def test_chaining_flips_reversed_plate_to_continue_chain() -> None:
    first = plate("first", 0.0, 0.0, 1000.0, 0.0)
    reversed_second = plate("second", 1000.0, 500.0, 1000.0, 0.0)

    chains = _chain_segments([first, reversed_second])

    assert len(chains) == 1
    assert chains[0].points == pytest.approx([(0.0, 0.0), (1000.0, 0.0), (1000.0, 500.0)])
    assert chains[0].plates == [first, reversed_second]


def test_chaining_disjoint_groups_returns_two_chains() -> None:
    plates = [
        plate("a1", 0.0, 0.0, 100.0, 0.0),
        plate("b1", 1000.0, 0.0, 1100.0, 0.0),
        plate("a2", 100.0, 0.0, 200.0, 0.0),
    ]

    chains = _chain_segments(plates)

    assert [len(chain.plates) for chain in chains] == [2, 1]
    assert [p.name for p in chains[0].plates] == ["a1", "a2"]
    assert chains[1].points == pytest.approx([(1000.0, 0.0), (1100.0, 0.0)])


def test_chaining_closed_loop_keeps_closing_vertex_and_invariant() -> None:
    plates = [
        plate("bottom", 0.0, 0.0, 100.0, 0.0),
        plate("side", 100.0, 0.0, 50.0, 80.0),
        plate("closing", 50.0, 80.0, 0.0, 0.0),
    ]

    chain = _chain_segments(plates)[0]

    assert len(chain.plates) == 3
    assert len(chain.points) == len(chain.plates) + 1
    assert chain.points[0] == pytest.approx(chain.points[-1])
    assert chain.points == pytest.approx([(0.0, 0.0), (100.0, 0.0), (50.0, 80.0), (0.0, 0.0)])


def test_split_closed_chains_opens_ring_at_centerline_crossings() -> None:
    # Closed ring crossing the centerline in the bottom (vertex at Y=0) and
    # in the deck (crossing between vertices) — like a full outer shell.
    plates = [
        plate("bot-s", 0.0, 0.0, 100.0, 0.0),
        plate("side-s", 100.0, 0.0, 100.0, 100.0),
        plate("deck", 100.0, 100.0, -100.0, 100.0),
        plate("side-p", -100.0, 100.0, -100.0, 0.0),
        plate("bot-p", -100.0, 0.0, 0.0, 0.0),
    ]
    ring = _chain_segments(plates)[0]
    assert ring.points[0] == pytest.approx(ring.points[-1])

    chains = _split_closed_chains([ring])

    assert len(chains) == 2
    for chain in chains:
        # Open, starting at the bottom centerline point, ending at deck CL.
        assert chain.points[0] == pytest.approx((0.0, 0.0))
        assert chain.points[-1] == pytest.approx((0.0, 100.0))
        assert len(chain.points) == len(chain.plates) + 1
    sides = sorted(sum(y for y, _ in chain.points) for chain in chains)
    assert sides[0] < 0 < sides[1]
    # The deck plate crossing the CL is shared by both halves.
    assert [p.name for p in chains[0].plates].count("deck") == 1
    assert [p.name for p in chains[1].plates].count("deck") == 1


def test_split_closed_chains_leaves_open_chain_unchanged() -> None:
    chain = _chain_segments([plate("a", 0.0, 0.0, 100.0, 0.0)])[0]

    assert _split_closed_chains([chain]) == [chain]


def test_split_closed_chains_leaves_off_centre_loop_unchanged() -> None:
    plates = [
        plate("a", 10.0, 0.0, 110.0, 0.0),
        plate("b", 110.0, 0.0, 60.0, 80.0),
        plate("c", 60.0, 80.0, 10.0, 0.0),
    ]
    ring = _chain_segments(plates)[0]

    assert _split_closed_chains([ring]) == [ring]


def test_chaining_t_junction_branch_starts_second_chain() -> None:
    plates = [
        plate("main-1", 0.0, 0.0, 100.0, 0.0),
        plate("main-2", 100.0, 0.0, 200.0, 0.0),
        plate("branch", 100.0, 0.0, 100.0, 80.0),
    ]

    chains = _chain_segments(plates)

    assert [[p.name for p in chain.plates] for chain in chains] == [["main-1", "main-2"], ["branch"]]
    assert chains[1].points == pytest.approx([(100.0, 0.0), (100.0, 80.0)])


def test_signed_radius_uses_center_side_of_segment_travel() -> None:
    arc_above = plate("arc", 0.0, 0.0, 100.0, 0.0, radius=25.0, center=(50.0, 10.0))
    arc_below = plate("arc", 0.0, 0.0, 100.0, 0.0, radius=25.0, center=(50.0, -10.0))

    assert _signed_radius(arc_above, (0.0, 0.0), (100.0, 0.0)) == pytest.approx(25.0)
    assert _signed_radius(arc_below, (0.0, 0.0), (100.0, 0.0)) == pytest.approx(-25.0)
    assert (
        _signed_radius(plate("straight", 0.0, 0.0, 100.0, 0.0), (0.0, 0.0), (100.0, 0.0))
        is None
    )


def test_panel_chains_do_not_merge_touching_plates_from_different_panels() -> None:
    # Nauticus keeps one PANEL per source panel: the deck touching the shell
    # at the sheer must not be swallowed into the SHELLP chain.
    plates = [
        plate("shell", 0.0, 0.0, 100.0, 0.0, panel="SHELLP"),
        plate("deck", 100.0, 0.0, 100.0, 80.0, panel="DECK"),
    ]

    named = _panel_chains(plates)

    assert sorted(item.name for item in named) == ["DECK", "SHELLP"]
    assert all(len(item.chain.plates) == 1 for item in named)


def test_panel_chains_split_full_breadth_panel_at_centerline_vertex() -> None:
    plates = [
        plate("d-port", -200.0, 100.0, 0.0, 100.0, panel="DECK"),
        plate("d-stbd", 0.0, 100.0, 200.0, 100.0, panel="DECK"),
    ]

    named = _panel_chains(plates)

    assert [item.name for item in named] == ["DECK", "DECK_2"]
    # both halves start at the centerline; positive-Y half keeps the base name
    assert named[0].chain.points == pytest.approx([(0.0, 100.0), (200.0, 100.0)])
    assert named[1].chain.points == pytest.approx([(0.0, 100.0), (-200.0, 100.0)])
    assert all(item.panel == "DECK" for item in named)


def test_panel_chains_split_crossing_plate_at_interpolated_centerline_point() -> None:
    plates = [plate("d", -100.0, 100.0, 300.0, 100.0, panel="DECK")]

    named = _panel_chains(plates)

    assert [item.name for item in named] == ["DECK", "DECK_2"]
    assert named[0].chain.points == pytest.approx([(0.0, 100.0), (300.0, 100.0)])
    assert named[1].chain.points == pytest.approx([(0.0, 100.0), (-100.0, 100.0)])
    # the crossing plate is shared by both halves
    assert named[0].chain.plates[0] is plates[0]
    assert named[1].chain.plates[0] is plates[0]


def test_panel_chains_keep_centerline_girder_whole() -> None:
    plates = [
        plate("g1", 0.0, 0.0, 0.0, 100.0, panel="BGI_CL"),
        plate("g2", 0.0, 100.0, 0.0, 200.0, panel="BGI_CL"),
    ]

    named = _panel_chains(plates)

    assert [item.name for item in named] == ["BGI_CL"]
    assert len(named[0].chain.plates) == 2


def test_panel_chains_orient_horizontal_chain_from_inboard_end() -> None:
    plates = [plate("stg", 300.0, 100.0, 150.0, 100.0, panel="STG_1_P")]

    named = _panel_chains(plates)

    assert named[0].chain.points == pytest.approx([(150.0, 100.0), (300.0, 100.0)])


def test_signed_radius_is_mirror_symmetric_across_centerline() -> None:
    # Nauticus exports the bilge with a positive radius on BOTH sides (see
    # NAPA VLCC_Fr(x=160000).2dlx and ISSCFrame170.hmx): the sign is evaluated
    # in an outboard-positive frame, so port geometry must not flip it.
    stbd = plate("bilge-s", 27400.0, 0.0, 30000.0, 2600.0, radius=2600.0, center=(27400.0, 2600.0))
    port = plate("bilge-p", -27400.0, 0.0, -30000.0, 2600.0, radius=2600.0, center=(-27400.0, 2600.0))

    assert _signed_radius(stbd, (27400.0, 0.0), (30000.0, 2600.0)) == pytest.approx(2600.0)
    assert _signed_radius(port, (-27400.0, 0.0), (-30000.0, 2600.0)) == pytest.approx(2600.0)


def test_signed_radius_uses_positive_radius_for_exact_semicircle() -> None:
    semicircle = plate("semi", 0.0, 0.0, 200.0, 0.0, radius=100.0, center=(100.0, 0.0))

    assert _signed_radius(semicircle, (0.0, 0.0), (200.0, 0.0)) == pytest.approx(100.0)


def test_arc_length_uses_circular_arc_and_straight_chord_length() -> None:
    arc = plate("arc", 0.0, 0.0, 200.0, 0.0, radius=100.0, center=(100.0, 0.0))
    straight = plate("straight", 0.0, 0.0, 3.0, 4.0)

    assert _arc_length_of(arc, (0.0, 0.0), (200.0, 0.0)) == pytest.approx(math.pi * 100.0)
    assert _arc_length_of(straight, (0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


def test_arc_position_projects_to_nearest_segment_with_arc_aware_prefix() -> None:
    arc = plate("arc", 0.0, 0.0, 200.0, 0.0, radius=100.0, center=(100.0, 0.0))
    straight = plate("straight", 200.0, 0.0, 200.0, 100.0)
    chain = _chain_segments([arc, straight])[0]

    assert _arc_position(chain, 205.0, 50.0) == pytest.approx(math.pi * 100.0 + 50.0)


def test_arc_position_uses_true_arc_station_for_curved_segment() -> None:
    arc = plate("arc", 100.0, 0.0, 0.0, 100.0, radius=100.0, center=(0.0, 0.0))
    chain = _chain_segments([arc])[0]
    query_y = 100.0 * math.cos(math.radians(30.0))
    query_z = 100.0 * math.sin(math.radians(30.0))

    assert _arc_position(chain, query_y, query_z) == pytest.approx(100.0 * math.radians(30.0))


def test_station_and_distance_uses_radial_distance_on_arcs() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    # Quarter circle R=1000 centered at origin, from (1000, 0) to (0, 1000).
    arc = plate("bilge", 1000.0, 0.0, 0.0, 1000.0, radius=1000.0, center=(0.0, 0.0))
    chain = _Chain(points=[(1000.0, 0.0), (0.0, 1000.0)], plates=[arc])

    # Point exactly on the arc at 45 degrees: chord distance would be the
    # sagitta (~293 mm) but the radial distance is 0.
    on_arc = (1000.0 * math.cos(math.pi / 4), 1000.0 * math.sin(math.pi / 4))
    station, dist = _station_and_distance(chain, on_arc)

    assert dist == pytest.approx(0.0, abs=1e-6)
    assert station == pytest.approx(1000.0 * math.pi / 4, rel=1e-6)


def test_station_and_distance_on_straight_segment() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    chain = _Chain(
        points=[(0.0, 0.0), (1000.0, 0.0), (1000.0, 500.0)],
        plates=[plate("a", 0.0, 0.0, 1000.0, 0.0), plate("b", 1000.0, 0.0, 1000.0, 500.0)],
    )

    station, dist = _station_and_distance(chain, (1000.0, 200.0))

    assert station == pytest.approx(1200.0)
    assert dist == pytest.approx(0.0, abs=1e-9)


def test_station_and_distance_reports_offset_distance() -> None:
    from ocx_model_validator.sections.hmx_export import _Chain, _station_and_distance

    chain = _Chain(points=[(0.0, 0.0), (1000.0, 0.0)], plates=[plate("a", 0.0, 0.0, 1000.0, 0.0)])

    station, dist = _station_and_distance(chain, (500.0, 80.0))

    assert station == pytest.approx(500.0)
    assert dist == pytest.approx(80.0)


def test_level1_code_classifies_bottom_deck_side_bilge_and_undefined() -> None:
    extent = {"min_y": -1000.0, "max_y": 1000.0, "min_z": 0.0, "max_z": 1000.0}

    assert (
        _level1_code(plate("bottom", -500.0, 0.0, 500.0, 0.0), (-500.0, 0.0), (500.0, 0.0), extent)
        == "GBOTTOM"
    )
    assert (
        _level1_code(
            plate("deck", -500.0, 1000.0, 500.0, 1000.0),
            (-500.0, 1000.0),
            (500.0, 1000.0),
            extent,
        )
        == "STRDECK"
    )
    assert (
        _level1_code(plate("side", 980.0, 100.0, 980.0, 900.0), (980.0, 100.0), (980.0, 900.0), extent)
        == "SIDE"
    )
    assert (
        _level1_code(plate("bilge", 0.0, 0.0, 100.0, 100.0, radius=100.0), (0.0, 0.0), (100.0, 100.0), {})
        == "BILGE"
    )
    assert (
        _level1_code(plate("slanted", 0.0, 200.0, 100.0, 300.0), (0.0, 200.0), (100.0, 300.0), extent)
        == "Undefined"
    )
    assert (
        _level1_code(plate("no-extent", 0.0, 0.0, 100.0, 0.0), (0.0, 0.0), (100.0, 0.0), None)
        == "Undefined"
    )


def test_side_uses_mean_y_of_chain_vertices() -> None:
    assert _side(_chain_segments([plate("left", 10.0, 0.0, 20.0, 0.0)])[0]) == "LEFT"
    assert _side(_chain_segments([plate("right", -10.0, 0.0, -20.0, 0.0)])[0]) == "RIGHT"
    assert _side(_chain_segments([plate("center", -1.0, 0.0, 1.0, 0.0)])[0]) == "CENTER"


def test_angles_use_web_direction_with_fallback() -> None:
    assert _angles(stiffener(0.0, 1.0)) == pytest.approx((90.0, 270.0))
    assert _angles(stiffener(1.0, 0.5)) == pytest.approx((26.56505117707799, 90.0))
    assert _angles(stiffener(-1.0, 0.0)) == pytest.approx((180.0, 270.0))
    assert _angles(stiffener(None, 1.0)) == pytest.approx((90.0, 270.0))


def test_material_ids_are_sequential_and_stable() -> None:
    ids = _MaterialIds()

    assert ids.id_for(315.0) == "1"
    assert ids.id_for(355.0) == "2"
    assert ids.id_for(315.0) == "1"
    assert list(ids.items()) == [(315.0, "1"), (355.0, "2")]


def test_lstiff_type_constant_contains_expected_hmx_codes() -> None:
    assert _LSTIFF_TYPE == {
        "flat_bar": 10,
        "bulb_flat": 20,
        "l_section": 31,
        "l_overshoot_flange": 35,
        "l_overshoot_web": 36,
        "t_section": 40,
    }


def test_synthetic_vessel_plates_chain_sensibly() -> None:
    section = build_cross_section(make_synthetic_vessel(), 5000.0)

    assert [(p.name, p.y1_mm, p.z1_mm, p.y2_mm, p.z2_mm) for p in section.plates] == [
        ("Plate A1", 0.0, 0.0, 2000.0, 0.0),
        ("Plate A2", 0.0, 1000.0, 2000.0, 1000.0),
    ]
    chains = _chain_segments(section.plates)

    assert len(chains) == 2
    assert [chain.points for chain in chains] == [
        [(0.0, 0.0), (2000.0, 0.0)],
        [(0.0, 1000.0), (2000.0, 1000.0)],
    ]
    assert [[p.name for p in chain.plates] for chain in chains] == [["Plate A1"], ["Plate A2"]]
