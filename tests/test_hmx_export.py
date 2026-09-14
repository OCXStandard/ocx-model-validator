from __future__ import annotations

from dataclasses import replace

import pytest

from ocx_model_validator.sections.frame_table import FrameRow, FrameTable
from ocx_model_validator.sections.hmx_export import build_hmx, save_hmx
from ocx_model_validator.sections.section_builder import (
    CrossSection,
    SectionPlate,
    SectionStiffener,
    build_cross_section,
)
from tests.section_fixtures import make_synthetic_vessel


def test_build_hmx_saves_schema_valid_scantling_document(tmp_path, hmx_schema) -> None:
    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)

    root = build_hmx(vessel, cross_section, _frame_table())
    path = tmp_path / "section.hmx"
    save_hmx(root, path)

    errors = list(hmx_schema.iter_errors(str(path)))
    assert errors == []
    assert hmx_schema.is_valid(str(path))
    assert root.tag == "HullModel"

    scantlings = root.findall("./CrossSections/Scantling")
    assert len(scantlings) == 1
    scantling = scantlings[0]
    assert len(scantling.findall("./PANEL")) == 2
    assert len(scantling.findall(".//PLATE")) == 2

    real_stiffeners = [
        stiffener
        for stiffener in scantling.findall(".//LSTIFF")
        if not stiffener.get("Name", "").startswith("__schema_placeholder__")
    ]
    assert len(real_stiffeners) == 3

    material_ids_by_yield = {
        element.get("Yield"): element.get("MaterialId")
        for element in [*scantling.findall(".//PLATE"), *real_stiffeners]
    }
    assert material_ids_by_yield == {"315": "1"}


def test_build_hmx_emits_bilge_segment_for_arc_plate(hmx_schema, tmp_path) -> None:
    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)
    arc_plate = SectionPlate(
        name="Bilge",
        y1_mm=0.0,
        z1_mm=0.0,
        y2_mm=500.0,
        z2_mm=500.0,
        thickness_mm=10.0,
        material_reh_mpa=315.0,
        panel="Bilge Panel",
        radius_mm=500.0,
        arc_center_y_mm=500.0,
        arc_center_z_mm=0.0,
    )
    arc_section = replace(cross_section, plates=[arc_plate], stiffeners=[])

    root = build_hmx(vessel, arc_section, _frame_table())
    path = tmp_path / "arc-section.hmx"
    save_hmx(root, path)

    errors = list(hmx_schema.iter_errors(str(path)))
    assert errors == []
    segment = root.find("./CrossSections/Scantling/PANEL/SHAPE/SEGMENT")
    assert segment is not None
    assert segment.get("Position") == "BILGE"
    assert float(segment.get("Radius", "0")) != pytest.approx(0.0)


def test_build_hmx_sanitizes_warning_comment_text(hmx_schema, tmp_path) -> None:
    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)
    cross_section = replace(cross_section, warnings=["model warning -- from source-"])

    root = build_hmx(vessel, cross_section, _frame_table())
    path = tmp_path / "warnings.hmx"
    save_hmx(root, path)

    assert hmx_schema.is_valid(str(path))
    assert "--" not in root[0].text
    assert not root[0].text.endswith("-")


def test_build_hmx_rejects_plate_less_cross_section() -> None:
    vessel = make_synthetic_vessel()
    cross_section = CrossSection(
        x_mm=5000.0,
        frame=None,
        stiffeners=[
            SectionStiffener(
                name="orphan",
                y_mm=0.0,
                z_mm=0.0,
                panel=None,
                profile_type=None,
                profile_dimensions=None,
                material_reh_mpa=235.0,
                spacing_mm=None,
            )
        ],
        plates=[],
        warnings=[],
    )

    with pytest.raises(ValueError, match="at least one plate"):
        build_hmx(vessel, cross_section, _frame_table())


def _frame_table() -> FrameTable:
    frame0 = FrameRow(label="0", name="X0", x_mm=0.0, display_grid=True)
    frame5 = FrameRow(label="5", name="X5", x_mm=5000.0, display_grid=True)
    frame10 = FrameRow(label="10", name="X10", x_mm=10000.0, display_grid=True)
    return FrameTable(
        frame0_offset_mm=0.0,
        positions=[("0", 0.0), ("5", 5000.0), ("10", 10000.0)],
        entries=[("0", 5000.0)],
        frames=[frame0, frame5, frame10],
        spacing_rows=[(frame0, 5000.0)],
    )
