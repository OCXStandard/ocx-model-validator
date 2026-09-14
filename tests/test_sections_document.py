from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Ref
from ocx_model_validator.sections.document import (
    build_compartments_block,
    build_document,
    load_document,
    save_document,
)
from tests.section_fixtures import make_synthetic_vessel, q


@pytest.fixture
def vessel():
    return make_synthetic_vessel()


def test_document_has_schema_and_top_level_blocks(vessel) -> None:
    doc = build_document(vessel, "model.ocx", x_mm=5000.0)

    assert doc["schema"] == "nh-cross-section/1"
    assert set(doc) == {"schema", "source", "frame_table", "cross_section", "compartments", "warnings"}
    assert doc["source"]["file"] == "model.ocx"
    assert doc["source"]["vessel_id"] == "vessel-1"
    assert doc["frame_table"]["positions"][1] == {"frame_no": "5", "x_mm": 5000.0}
    assert doc["cross_section"]["stiffeners"][0]["orientation"] == "Longitudinal"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({}, "Exactly one"), ({"x_mm": 5000.0, "frame": "5"}, "Exactly one")],
)
def test_build_document_requires_exactly_one_location(vessel, kwargs, message) -> None:
    with pytest.raises(SectionError, match=message):
        build_document(vessel, "model.ocx", **kwargs)


def test_frame_resolves_to_x_and_is_reported(vessel) -> None:
    doc = build_document(vessel, "model.ocx", frame="5")

    assert doc["cross_section"]["x_mm"] == 5000.0
    assert doc["cross_section"]["frame"] == "5"


@pytest.mark.parametrize(
    ("x_mm", "expected_frame"),
    [(5000.5, "5"), (5001.1, None)],
)
def test_x_location_reports_nearest_frame_only_within_one_mm(vessel, x_mm, expected_frame) -> None:
    doc = build_document(vessel, "model.ocx", x_mm=x_mm)

    assert doc["cross_section"]["frame"] == expected_frame


@pytest.mark.parametrize(
    ("purpose", "expected"),
    [
        ("void space", "VOIDSPACE"),
        ("ballast water", "BALLASTWATERTANK"),
        ("HFO service", "FUELTANK"),
        ("fresh water", "FRESHWATERTANK"),
        ("cargo oil", "CARGOHOLD"),
        ("slop tank", "SLOP TANK"),
        (None, "VOIDSPACE"),
    ],
)
def test_compartment_tank_type_mapping(vessel, purpose, expected) -> None:
    vessel.compartments = {
        "tank": IrCompartment(id="tank", name="Tank", compartment_purpose=purpose)
    }

    compartments, warnings = build_compartments_block(vessel)

    assert compartments[0]["tank_type"] == expected
    if purpose is None:
        assert any("Tank" in warning and "purpose" in warning for warning in warnings)


def test_compartment_cog_volume_and_extent_from_matched_panel(vessel) -> None:
    compartments, warnings = build_compartments_block(vessel)

    ballast = next(c for c in compartments if c["name"] == "Ballast Tank")
    assert ballast["cog_mm"] == [5000.0, 1000.0, 500.0]
    assert ballast["volume_m3"] == 123.46
    assert ballast["extent_mm"] == {
        "min_x": 5000.0,
        "max_x": 5000.0,
        "min_y": 250.0,
        "max_y": 1750.0,
        "min_z": 0.0,
        "max_z": 1000.0,
    }
    assert not any("Ballast Tank" in warning for warning in warnings)


def test_unresolved_compartment_extent_is_null_with_warning(vessel) -> None:
    compartments, warnings = build_compartments_block(vessel)

    empty = next(c for c in compartments if c["name"] == "Unclassified Space")
    assert empty["cog_mm"] is None
    assert empty["extent_mm"] == {
        "min_x": None,
        "max_x": None,
        "min_y": None,
        "max_y": None,
        "min_z": None,
        "max_z": None,
    }
    assert any("Unclassified Space" in warning and "cog" in warning.lower() for warning in warnings)
    assert any("Unclassified Space" in warning and "extent" in warning.lower() for warning in warnings)


def test_extent_matches_panel_guid_and_id(vessel) -> None:
    vessel.compartments["guid-match"] = IrCompartment(
        id="guid-match",
        name="Guid Match",
        compartment_purpose="void",
        face_refs=[Ref("unused", guidref="panel-a-guid")],
        cog=IrCog(5.0, 0.0, 0.0, "Um"),
    )

    compartments, _warnings = build_compartments_block(vessel)

    by_name = {compartment["name"]: compartment for compartment in compartments}
    assert by_name["Ballast Tank"]["extent_mm"] == by_name["Guid Match"]["extent_mm"]


def test_document_floats_are_rounded_to_two_decimals(vessel) -> None:
    vessel.plates["plate-a1"].cog = IrCog(5.004, 0.2544, 0.0, "Um")
    vessel.compartments["ballast"].cog = IrCog(5.004, 1.0055, 0.5004, "Um")

    doc = build_document(vessel, "model.ocx", x_mm=5000.0)

    ballast = next(c for c in doc["compartments"] if c["name"] == "Ballast Tank")
    assert ballast["cog_mm"] == [5004.0, 1005.5, 500.4]
    assert ballast["extent_mm"]["min_y"] == 254.4


def test_save_load_round_trip_equality(vessel) -> None:
    doc = build_document(vessel, "model.ocx", frame="5")
    path = Path("section-document-round-trip-test.json")

    try:
        save_document(doc, path)

        assert json.loads(path.read_text()) == doc
        assert load_document(path) == doc
    finally:
        path.unlink(missing_ok=True)


def test_load_rejects_missing_cross_section() -> None:
    path = Path("section-document-missing-cross-section-test.json")
    path.write_text(json.dumps({"schema": "nh-cross-section/1", "frame_table": {}, "compartments": []}))

    try:
        with pytest.raises(SectionError, match="cross_section"):
            load_document(path)
    finally:
        path.unlink(missing_ok=True)


def test_load_rejects_wrong_schema() -> None:
    path = Path("section-document-wrong-schema-test.json")
    path.write_text(
        json.dumps(
            {"schema": "wrong", "frame_table": {}, "cross_section": {}, "compartments": []}
        )
    )

    try:
        with pytest.raises(SectionError, match="schema"):
            load_document(path)
    finally:
        path.unlink(missing_ok=True)


def test_extent_from_face_boundary_curves(vessel) -> None:
    from ocx_model_validator.model.ir.geometry import (
        IrCircle3D, IrLine3D, IrPoint3D, IrPolyLine3D,
    )

    vessel.compartments["fbc"] = IrCompartment(
        id="fbc", name="FBC Tank", compartment_purpose="void",
        face_boundary_curves=[
            IrLine3D(curve_length=None,
                     start=IrPoint3D(0.0, 0.0, 0.0, "Um"),
                     end=IrPoint3D(10.0, 0.0, 0.0, "Um")),
            IrPolyLine3D(curve_length=None,
                         vertices=[IrPoint3D(10.0, 2.0, 1.0, "Um"),
                                   IrPoint3D(0.0, 2.0, 3.0, "Um")]),
            IrCircle3D(curve_length=None,
                       center=IrPoint3D(5.0, 1.0, 1.0, "Um"),
                       diameter=q(2.0, "Um")),
        ],
    )

    compartments, warnings = build_compartments_block(vessel)

    row = next(c for c in compartments if c["name"] == "FBC Tank")
    assert row["extent_mm"] == {
        "min_x": 0.0, "max_x": 10000.0,
        "min_y": 0.0, "max_y": 2000.0,
        "min_z": 0.0, "max_z": 3000.0,
    }
    assert not any("FBC Tank" in w and "extent" in w.lower() for w in warnings)


def test_extent_prefers_boundary_curves_over_panel_fallback(vessel) -> None:
    from ocx_model_validator.model.ir.geometry import IrLine3D, IrPoint3D

    # ballast compartment resolves panels today; boundary curves must win
    vessel.compartments["ballast"].face_boundary_curves = [
        IrLine3D(curve_length=None,
                 start=IrPoint3D(1.0, -3.0, 0.5, "Um"),
                 end=IrPoint3D(2.0, 3.0, 2.5, "Um")),
    ]

    compartments, _warnings = build_compartments_block(vessel)

    ballast = next(c for c in compartments if c["name"] == "Ballast Tank")
    assert ballast["extent_mm"] == {
        "min_x": 1000.0, "max_x": 2000.0,
        "min_y": -3000.0, "max_y": 3000.0,
        "min_z": 500.0, "max_z": 2500.0,
    }


def test_compartment_row_includes_compartment_properties(vessel) -> None:
    vessel.compartments["props"] = IrCompartment(
        id="props", name="Props Tank", compartment_purpose="void",
        filling_height=q(9.0, "Um"),
        air_pipe_height=q(10.5, "Um"),
        relief_valve_pressure=q(25000.0, "UPa"),
    )

    compartments, _warnings = build_compartments_block(vessel)

    row = next(c for c in compartments if c["name"] == "Props Tank")
    assert row["filling_height_mm"] == 9000.0
    assert row["air_pipe_height_mm"] == 10500.0
    assert row["relief_valve_pressure_kpa"] == 25.0
