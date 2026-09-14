from __future__ import annotations

from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Quantity
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrPolyLine3D
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.sections.frame_table import FrameTable, FrameRow
from ocx_model_validator.sections.hmx_export import (
    _MaterialIds,
    _compartments,
    _frame_table,
    _segment_compartments,
    _ship_data,
)


def test_ship_data_builds_schema_specific_rule_child_and_required_placeholders() -> None:
    extent = {
        "min_x": 0.0,
        "max_x": 100000.0,
        "min_y": -10000.0,
        "max_y": 15000.0,
        "min_z": 0.0,
        "max_z": 20000.0,
    }
    materials = _MaterialIds()
    materials.id_for(315.0)
    materials.id_for(355.0)

    for rule_set, rule_child, rules_attrs, general_tag in [
        ("DNV", "DNV", {"RuleSet": "DNV-1A1", "RuleEdition": "2024"}, "GeneralShipDataType"),
        ("RV5", "RV5", {"RuleEdition": "2024"}, "GeneralShipData"),
        ("CSR-H", "CSR-H", {"RuleEdition": "2024"}, "GeneralShipData"),
    ]:
        warnings: list[str] = []

        ship_data = _ship_data(rule_set, extent, materials, warnings)

        assert ship_data.tag == "ShipData"
        assert ship_data.attrib == {"VesselId": "", "ShipType": "Other"}
        assert [child.tag for child in ship_data] == [rule_child]
        rule = ship_data[0]
        assert [child.tag for child in rule] == [
            "ApplicableRules",
            "MainDimensions",
            general_tag,
            "MaterialData",
            *([] if rule_set == "DNV" else ["IceClassData"]),
        ]
        assert dict(rule.find("ApplicableRules").attrib) == rules_attrs
        assert dict(rule.find("MainDimensions").attrib) == {
            "Lbp": "100",
            "B": "25",
            "D": "20",
            "T": "14",
        }
        assert dict(rule.find(general_tag).attrib) == {
            "MaxServiceSpeed": "0",
            "MinNormBalDraught": "0",
            "HeavyBalDraught": "0",
            "DeepestEqWLDamaged": "0",
            "SlammingDraughtEmpty": "0",
            "SlammingDraughtFull": "0",
            "DeadWeightLT50000": "false",
            "FreeboardType": "B",
            "BilgKeel": "false",
        }
        assert dict(rule.find("MaterialData").attrib) == {
            "E": "206000",
            "SigmaFBott": "315",
            "SigmaFDeck": "315",
            "SigmaFMid": "315",
        }
        assert any("draught T uses placeholder" in warning for warning in warnings)
        assert any("GeneralShipData" in warning for warning in warnings)
        assert any("RuleEdition" in warning and "placeholder" in warning for warning in warnings)
        assert any("MaterialData" in warning and "Sigma" in warning for warning in warnings)


def test_ship_data_with_missing_extent_omits_main_dimension_attrs_and_warns() -> None:
    warnings: list[str] = []

    ship_data = _ship_data("RV5", None, _MaterialIds(), warnings)

    main_dimensions = ship_data.find("RV5/MainDimensions")
    assert main_dimensions is not None
    assert main_dimensions.attrib == {}
    assert any("extent is missing" in warning for warning in warnings)


def test_frame_table_emits_offset_and_spacing_rows_in_metres() -> None:
    frame0 = FrameRow(label="FR0", name="FR0", x_mm=0.0, display_grid=True)
    frame1 = FrameRow(label="FR1", name="FR1", x_mm=800.0, display_grid=True)
    ft = FrameTable(
        frame0_offset_mm=1200.0,
        positions=[("FR0", 0.0), ("FR1", 800.0)],
        entries=[("FR0", 800.0)],
        spacing_rows=[(frame0, 800.0), (frame1, 900.0)],
    )

    warnings: list[str] = []

    frame_table = _frame_table(ft, warnings)

    assert frame_table.tag == "FrameTable"
    assert frame_table.attrib == {"FrameOffset": "1.2", "FrameRef": "AP"}
    assert [dict(row.attrib) for row in frame_table] == [
        {"FrameNo": "Stern", "Spacing": "0.8"},
        {"FrameNo": "FR1", "Spacing": "0.9"},
    ]
    assert warnings == []


def test_frame_table_emits_fallback_spacing_row_when_empty_and_warns() -> None:
    ft = FrameTable(
        frame0_offset_mm=0.0,
        positions=[],
        entries=[],
        spacing_rows=[],
    )
    warnings: list[str] = []

    frame_table = _frame_table(ft, warnings)

    assert [dict(row.attrib) for row in frame_table] == [
        {"FrameNo": "Stern", "Spacing": "0.8"},
    ]
    assert any("fallback" in warning and "FrameTable" in warning for warning in warnings)


def test_compartments_maps_types_emits_bbox_and_skips_unbounded_compartment() -> None:
    vessel = IrVessel(id="vessel")
    vessel.compartments["ballast"] = _compartment(
        "ballast",
        "Ballast Tank",
        "BALLASTWATERTANK",
        [(0.0, -2.0, 0.0), (10.0, -2.0, 0.0), (10.0, 2.0, 3.0), (0.0, 2.0, 3.0)],
        relief_kpa=12.5,
    )
    vessel.compartments["mystery"] = _compartment(
        "mystery",
        "Mystery Space",
        "something else",
        [(5.0, 3.0, 1.0), (7.0, 3.0, 1.0), (7.0, 4.0, 2.0), (5.0, 4.0, 2.0)],
    )
    vessel.compartments["empty"] = IrCompartment(
        id="empty",
        name="Empty Space",
        compartment_purpose="VOIDSPACE",
    )
    warnings: list[str] = []

    compartments, boxes = _compartments(vessel, warnings)

    assert compartments is not None
    assert [child.get("Name") for child in compartments] == ["Ballast Tank", "Mystery Space"]
    assert [child.get("Id") for child in compartments] == ["1", "2"]
    assert [child.get("Type") for child in compartments] == ["BallastWaterTank", "Undefined"]
    ballast = compartments[0]
    assert dict(ballast.find("General").attrib) == {
        "Length": "10000",
        "TopOfAirPipe": "9000",
        "Volume": "123.46",
        "CgX": "5000",
        "CgY": "0",
        "CgZ": "1500",
    }
    assert dict(ballast.find("RV5").attrib) == {
        "OverPressure": "12.5",
        "PressureValveFitted": "true",
    }
    assert dict(ballast.find("Geometry/BoundingBox").attrib) == {
        "MinX": "0",
        "MaxX": "10000",
        "MinY": "-2000",
        "MaxY": "2000",
        "MinZ": "0",
        "MaxZ": "3000",
    }
    assert boxes["Ballast Tank"] == {
        "id": "1",
        "min_x": 0.0,
        "max_x": 10000.0,
        "min_y": -2000.0,
        "max_y": 2000.0,
        "min_z": 0.0,
        "max_z": 3000.0,
    }
    assert any("unsupported tank type" in warning for warning in warnings)
    assert any("extent is empty; skipped" in warning for warning in warnings)


def test_compartments_emits_csrh_choice_child_with_overpressure() -> None:
    vessel = IrVessel(id="vessel")
    vessel.compartments["ballast"] = _compartment(
        "ballast",
        "Ballast Tank",
        "BALLASTWATERTANK",
        [(0.0, -2.0, 0.0), (10.0, -2.0, 0.0), (10.0, 2.0, 3.0), (0.0, 2.0, 3.0)],
        relief_kpa=12.5,
    )
    warnings: list[str] = []

    compartments, _boxes = _compartments(vessel, warnings, rule_set="CSR-H")

    assert compartments is not None
    ballast = compartments[0]
    assert ballast.find("RV5") is None
    csrh = ballast.find("CSRH")
    assert csrh is not None
    assert dict(csrh.attrib) == {"OverPressure": "12.5"}


def test_compartments_warns_and_keeps_first_box_for_duplicate_names() -> None:
    vessel = IrVessel(id="vessel")
    vessel.compartments["first"] = _compartment(
        "first",
        "Same Name",
        "VOIDSPACE",
        [(0.0, -2.0, 0.0), (10.0, -2.0, 0.0), (10.0, 2.0, 3.0), (0.0, 2.0, 3.0)],
    )
    vessel.compartments["second"] = _compartment(
        "second",
        "Same Name",
        "VOIDSPACE",
        [(20.0, 5.0, 1.0), (30.0, 5.0, 1.0), (30.0, 6.0, 2.0), (20.0, 6.0, 2.0)],
    )
    warnings: list[str] = []

    compartments, boxes = _compartments(vessel, warnings)

    assert compartments is not None
    assert [child.get("Name") for child in compartments] == ["Same Name", "Same Name"]
    assert [child.get("Id") for child in compartments] == ["1", "2"]
    assert boxes["Same Name"] == {
        "id": "1",
        "min_x": 0.0,
        "max_x": 10000.0,
        "min_y": -2000.0,
        "max_y": 2000.0,
        "min_z": 0.0,
        "max_z": 3000.0,
    }
    assert any("duplicate compartment name" in warning and "Same Name" in warning for warning in warnings)


def test_compartments_returns_none_when_no_rows_survive() -> None:
    vessel = IrVessel(id="vessel")
    vessel.compartments["empty"] = IrCompartment(id="empty", name="Empty")

    compartments, boxes = _compartments(vessel, [])

    assert compartments is None
    assert boxes == {}


def test_segment_compartments_samples_left_and_right_of_segment() -> None:
    boxes = {
        "port": {"id": "1", "min_x": 0.0, "max_x": 10000.0, "min_y": -500.0, "max_y": 500.0, "min_z": 100.0, "max_z": 500.0},
        "starboard": {"id": "2", "min_x": 0.0, "max_x": 10000.0, "min_y": -500.0, "max_y": 500.0, "min_z": -500.0, "max_z": -100.0},
    }

    assert _segment_compartments((0.0, 0.0), (1.0, 0.0), boxes, 5000.0) == ("port", "starboard")
    assert _segment_compartments((2000.0, 0.0), (1.0, 0.0), boxes, 5000.0) == (None, None)


def test_segment_compartments_normalizes_non_unit_direction() -> None:
    boxes = {
        "port": {"id": "1", "min_x": 0.0, "max_x": 10000.0, "min_y": -500.0, "max_y": 500.0, "min_z": 100.0, "max_z": 500.0},
        "starboard": {"id": "2", "min_x": 0.0, "max_x": 10000.0, "min_y": -500.0, "max_y": 500.0, "min_z": -500.0, "max_z": -100.0},
    }

    assert _segment_compartments((0.0, 0.0), (1000.0, 0.0), boxes, 5000.0) == ("port", "starboard")


def _compartment(
    cid: str,
    name: str,
    purpose: str,
    vertices_m: list[tuple[float, float, float]],
    *,
    relief_kpa: float | None = None,
) -> IrCompartment:
    return IrCompartment(
        id=cid,
        name=name,
        compartment_purpose=purpose,
        volume=Quantity(123.456, "Um3"),
        filling_height=Quantity(4.0, "Um"),
        air_pipe_height=Quantity(9.0, "Um"),
        relief_valve_pressure=None if relief_kpa is None else Quantity(relief_kpa * 1000.0, "UPa"),
        cog=IrCog(5.0, 0.0, 1.5, "Um"),
        face_boundary_curves=[
            IrPolyLine3D(
                curve_length=None,
                vertices=[IrPoint3D(x=x, y=y, z=z, unit="Um") for x, y, z in vertices_m],
                is_closed=True,
            )
        ],
    )
