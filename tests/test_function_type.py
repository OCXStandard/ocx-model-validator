"""functionType propagation: IR panel -> section rows -> EPP rows."""
from dataclasses import replace

from ocx_model_validator.sections.epp import split_plates_to_epps
from ocx_model_validator.sections.section_builder import (
    SectionPlate,
    build_cross_section,
)
from tests.section_fixtures import make_synthetic_vessel


def test_build_cross_section_carries_panel_function_type():
    vessel = make_synthetic_vessel()
    vessel.panels["panel-a"] = replace(
        vessel.panels["panel-a"], function_type="DECK PLATING"
    )

    section = build_cross_section(vessel, x_mm=5000.0)

    plate_types = {p.name: p.function_type for p in section.plates}
    assert plate_types["Plate A1"] == "DECK PLATING"
    stiff_types = {s.name: s.function_type for s in section.stiffeners}
    assert stiff_types["A bulb"] == "DECK PLATING"
    assert stiff_types["B alone"] is None  # panel-b has no functionType


def test_epp_split_carries_function_type():
    plate = SectionPlate(
        name="P1",
        y1_mm=0.0,
        z1_mm=0.0,
        y2_mm=1000.0,
        z2_mm=0.0,
        thickness_mm=10.0,
        material_reh_mpa=235.0,
        panel="DECK",
        function_type="DECK PLATING",
    )

    epps = split_plates_to_epps([plate], [])

    assert epps
    assert all(e.function_type == "DECK PLATING" for e in epps)
