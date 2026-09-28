"""Tests for user-supplied hull-girder cross-section properties."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.sections.document import build_document
from ocx_model_validator.sections.properties import (
    derive_section_properties,
    load_section_properties,
    match_properties,
)
from ocx_model_validator.sections.section_builder import SectionPlate
from tests.section_fixtures import make_synthetic_vessel

SAMPLE_ENTRY = {
    "x_pos": 5000.0,
    "z_n": 11.065,
    "iy_n50": 1002.0,
    "iz_n50": 2990.0,
    "z_vd": 22.0,
}


@pytest.fixture
def props_file(tmp_path: Path) -> Path:
    path = tmp_path / "props.json"
    path.write_text(json.dumps([SAMPLE_ENTRY]), encoding="utf-8")
    return path


class TestLoadSectionProperties:
    def test_loads_list_of_entries(self, props_file: Path) -> None:
        entries = load_section_properties(props_file)
        assert entries == [SAMPLE_ENTRY]

    def test_rejects_non_list_root(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"x_pos": 1.0}), encoding="utf-8")
        with pytest.raises(SectionError, match="list"):
            load_section_properties(path)

    def test_rejects_entry_without_numeric_x_pos(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([{"z_n": 1.0}]), encoding="utf-8")
        with pytest.raises(SectionError, match="x_pos"):
            load_section_properties(path)

    @pytest.mark.parametrize("key", ["ibh", "z_deck_corner", "bx"])
    def test_rejects_model_derived_keys(self, tmp_path: Path, key: str) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([{"x_pos": 1.0, key: 2.0}]), encoding="utf-8")
        with pytest.raises(SectionError, match="derived"):
            load_section_properties(path)


def _plate(y1: float, z1: float, y2: float, z2: float,
           function_type: str | None = None) -> SectionPlate:
    return SectionPlate(
        name="P", y1_mm=y1, z1_mm=z1, y2_mm=y2, z2_mm=z2,
        thickness_mm=10.0, material_reh_mpa=None, panel=None,
        function_type=function_type,
    )


class TestDeriveSectionProperties:
    def test_bx_is_full_breadth_over_both_sides(self) -> None:
        plates = [_plate(-29_000.0, 0.0, 29_000.0, 0.0)]
        derived, _ = derive_section_properties(plates)
        assert derived["bx"] == 58.0

    def test_bx_doubles_half_model(self) -> None:
        plates = [_plate(0.0, 0.0, 29_000.0, 0.0)]
        derived, _ = derive_section_properties(plates)
        assert derived["bx"] == 58.0

    def test_z_deck_corner_is_outboard_deck_edge(self) -> None:
        plates = [
            _plate(20_000.0, 23_500.0, 29_000.0, 23_000.0, "DECK: Strength deck"),
            _plate(0.0, 30_000.0, 5_000.0, 30_000.0, "DECK: Platform deck"),
        ]
        derived, _ = derive_section_properties(plates)
        assert derived["z_deck_corner"] == 23.0

    def test_ibh_is_max_z_of_inner_bottom_plates(self) -> None:
        plates = [
            _plate(0.0, 2_400.0, 10_000.0, 2_400.0, "LONGITUDINAL: Inner bottom"),
            _plate(0.0, 0.0, 10_000.0, 0.0, "SHELL: Bottom shell"),
        ]
        derived, _ = derive_section_properties(plates)
        assert derived["ibh"] == 2.4

    def test_ibh_matches_double_bottom_type(self) -> None:
        plates = [_plate(0.0, 2_100.0, 10_000.0, 2_100.0,
                         "LONGITUDINAL: Double bottom")]
        derived, _ = derive_section_properties(plates)
        assert derived["ibh"] == 2.1

    def test_ibh_fallback_second_intersection_at_y50(self) -> None:
        # no inner-bottom typed plates: intersect the section at y=50 mm
        plates = [
            _plate(-30_000.0, 0.0, 30_000.0, 0.0, "SHELL"),           # bottom
            _plate(-30_000.0, 3_000.0, 30_000.0, 3_000.0, "DECK"),    # inner btm
            _plate(-30_000.0, 23_000.0, 30_000.0, 23_000.0, "DECK"),  # deck
        ]
        derived, warnings = derive_section_properties(plates)
        assert derived["ibh"] == 3.0
        assert not any("ibh" in w for w in warnings)

    def test_ibh_fallback_ignores_plates_not_crossing_y50(self) -> None:
        plates = [
            _plate(-30_000.0, 0.0, 30_000.0, 0.0, "SHELL"),
            _plate(2_000.0, 3_000.0, 30_000.0, 3_000.0, None),  # starts outboard
            _plate(-30_000.0, 23_000.0, 30_000.0, 23_000.0, "DECK"),
        ]
        derived, _ = derive_section_properties(plates)
        assert derived["ibh"] is None or derived["ibh"] != 3.0

    def test_ibh_fallback_rejects_second_intersection_near_max_z(self) -> None:
        # only bottom + deck cross y=50: the "inner bottom" would be the deck
        plates = [
            _plate(-30_000.0, 0.0, 30_000.0, 0.0, "SHELL"),
            _plate(-30_000.0, 23_000.0, 30_000.0, 23_000.0, "DECK"),
        ]
        derived, warnings = derive_section_properties(plates)
        assert derived["ibh"] is None
        assert any("ibh" in w for w in warnings)

    def test_ibh_fallback_dedupes_coincident_intersections(self) -> None:
        # bottom split into two plates meeting exactly at z=0
        plates = [
            _plate(-30_000.0, 0.0, 50.0, 0.0),
            _plate(50.0, 0.0, 30_000.0, 0.0),
            _plate(-30_000.0, 2_400.0, 30_000.0, 2_400.0),
            _plate(-30_000.0, 23_000.0, 30_000.0, 23_000.0, "DECK"),
        ]
        derived, _ = derive_section_properties(plates)
        assert derived["ibh"] == 2.4

    def test_underivable_values_are_none_with_warnings(self) -> None:
        derived, warnings = derive_section_properties(
            [_plate(0.0, 0.0, 1_000.0, 0.0)])
        assert derived["ibh"] is None
        assert derived["z_deck_corner"] is None
        assert any("ibh" in w for w in warnings)
        assert any("z_deck_corner" in w for w in warnings)

    def test_no_plates_yields_all_none(self) -> None:
        derived, warnings = derive_section_properties([])
        assert derived == {"ibh": None, "z_deck_corner": None, "bx": None}
        assert warnings


class TestMatchProperties:
    def test_matches_within_one_mm(self) -> None:
        assert match_properties([SAMPLE_ENTRY], 5000.9) == SAMPLE_ENTRY

    def test_no_match_outside_tolerance(self) -> None:
        assert match_properties([SAMPLE_ENTRY], 5001.1) is None

    def test_no_match_on_empty_list(self) -> None:
        assert match_properties([], 5000.0) is None


class TestBuildDocumentWithProperties:
    def test_user_and_derived_properties_merged(self) -> None:
        vessel = make_synthetic_vessel()
        doc = build_document(vessel, "model.ocx", x_mm=5000.0,
                             section_props=[SAMPLE_ENTRY])
        props = doc["cross_section"]["sect_props"]
        assert props["z_n"] == 11.065  # user values preserved verbatim
        assert props["z_vd"] == 22.0
        assert "x_pos" not in props
        # derived from the model: synthetic plates span y 0..2000 mm (half model)
        assert props["bx"] == 4.0
        # no deck / inner-bottom function types in the synthetic model
        assert props["ibh"] is None
        assert props["z_deck_corner"] is None
        assert any("ibh" in w for w in doc["warnings"])

    def test_no_match_keeps_derived_and_warns(self) -> None:
        vessel = make_synthetic_vessel()
        doc = build_document(vessel, "model.ocx", x_mm=7000.0,
                             section_props=[SAMPLE_ENTRY])
        props = doc["cross_section"]["sect_props"]
        assert "z_n" not in props
        assert "bx" in props
        assert any("section properties" in w for w in doc["warnings"])

    def test_no_props_supplied_keeps_derived_and_warns(self) -> None:
        vessel = make_synthetic_vessel()
        doc = build_document(vessel, "model.ocx", x_mm=5000.0)
        props = doc["cross_section"]["sect_props"]
        assert "z_n" not in props
        assert props["bx"] == 4.0
        assert any("section properties" in w for w in doc["warnings"])


class TestCliSectionProps:
    def test_section_create_with_section_props(
        self, props_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        import ocx_model_validator.cli as cli

        monkeypatch.setattr(cli, "_load_vessel",
                            lambda model: make_synthetic_vessel())
        out = tmp_path / "section.json"
        result = CliRunner().invoke(cli.app, [
            "section", "create", str(props_file),  # any existing file path
            "--x", "5000", "--section-props", str(props_file),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["cross_section"]["sect_props"]["z_n"] == 11.065

    def test_section_create_with_invalid_props_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        import ocx_model_validator.cli as cli

        monkeypatch.setattr(cli, "_load_vessel",
                            lambda model: make_synthetic_vessel())
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        result = CliRunner().invoke(cli.app, [
            "section", "create", str(bad),
            "--x", "5000", "--section-props", str(bad),
        ])
        assert result.exit_code == 1
