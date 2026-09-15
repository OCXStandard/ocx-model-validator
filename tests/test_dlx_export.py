"""Tests for the Nauticus Hull 2DLX cross-section export."""
from __future__ import annotations

from dataclasses import replace

import pytest

from ocx_model_validator.sections.section_builder import (
    CrossSection,
    SectionPlate,
    SectionStiffener,
    build_cross_section,
)
from tests.section_fixtures import make_synthetic_vessel
from tests.test_hmx_export import (
    _assert_only_nauticus_empty_wrapper_errors,
    _frame_table,
)


def test_dlx_schema_loads(dlx_schema):
    assert dlx_schema is not None
    assert "CROSS_SECTION" in dlx_schema.elements


def test_build_2dlx_saves_schema_valid_document(tmp_path, dlx_schema) -> None:
    from ocx_model_validator.sections.dlx_export import build_2dlx, save_2dlx

    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)

    root = build_2dlx(vessel, cross_section, _frame_table())
    path = tmp_path / "section.2dlx"
    save_2dlx(root, path)

    _assert_only_nauticus_empty_wrapper_errors(dlx_schema, path)
    assert root.tag == "CROSS_SECTION"

    administrative = root.find("./administrative")
    assert administrative is not None
    program = administrative.find("./program")
    assert program.get("name") == "ocx-model-validator"
    assert program.get("version")
    session = administrative.find("./session_info")
    assert session.get("date") and session.get("time")

    assert len(root.findall("./PANEL")) == 2
    assert len(root.findall(".//PLATE")) == 2
    assert len(root.findall(".//LSTIFF")) == 3

    # 2DLX deltas: no HMX-only attributes anywhere
    for segment in root.findall(".//SEGMENT"):
        assert segment.get("LeftCompartment") is None
        assert segment.get("RightCompartment") is None
    for element in [*root.findall(".//PLATE"), *root.findall(".//LSTIFF")]:
        assert element.get("MaterialId") is None
        assert element.get("Yield") == "315"

    # no HMX wrappers leak into the standalone document
    assert root.find("./ShipData") is None
    assert root.find("./FrameTable") is None


def test_build_2dlx_maps_t_section_to_welded_tbar_43() -> None:
    from ocx_model_validator.sections.dlx_export import build_2dlx
    from ocx_model_validator.sections.hmx_export import build_hmx

    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)
    tbar = replace(cross_section.stiffeners[0], section_kind="t_section")
    section = replace(cross_section, stiffeners=[tbar])

    dlx_root = build_2dlx(vessel, section, _frame_table())
    hmx_root = build_hmx(vessel, section, _frame_table())

    assert dlx_root.find(".//LSTIFF").get("Type") == "43"
    assert hmx_root.find(".//LSTIFF").get("Type") == "40"


def test_build_2dlx_unknown_section_kind_falls_back_to_flatbar_10() -> None:
    from ocx_model_validator.sections.dlx_export import build_2dlx

    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)
    odd = replace(cross_section.stiffeners[0], section_kind="zbar")
    section = replace(cross_section, stiffeners=[odd])

    root = build_2dlx(vessel, section, _frame_table())

    assert root.find(".//LSTIFF").get("Type") == "10"
    # fallback is reported in the leading warnings comment
    comment = root[0]
    assert "unsupported section kind" in (comment.text or "")


def test_build_2dlx_emits_bilge_segment_for_arc_plate(dlx_schema, tmp_path) -> None:
    from ocx_model_validator.sections.dlx_export import build_2dlx, save_2dlx

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

    root = build_2dlx(vessel, arc_section, _frame_table())
    path = tmp_path / "arc-section.2dlx"
    save_2dlx(root, path)

    _assert_only_nauticus_empty_wrapper_errors(dlx_schema, path)
    segment = root.find("./PANEL/SHAPE/SEGMENT")
    assert segment.get("Position") == "BILGE"
    assert float(segment.get("Radius", "0")) != pytest.approx(0.0)


def test_build_2dlx_omits_global_data_materials_table() -> None:
    # Nauticus Hull's Paste2dlx importer rejects 2DLX files that carry a
    # GlobalData block ("Verification fail: different number of panels"),
    # even though NH's own exports contain one. Verified empirically against
    # NH 21.2 on 2026-09-15 — do not re-add GlobalData/MaterialId.
    from ocx_model_validator.sections.dlx_export import build_2dlx

    vessel = make_synthetic_vessel()
    cross_section = build_cross_section(vessel, 5000.0)

    root = build_2dlx(vessel, cross_section, _frame_table())

    assert root.find("./GlobalData") is None
    for element in [*root.findall(".//PLATE"), *root.findall(".//LSTIFF")]:
        assert element.get("MaterialId") is None


def test_build_2dlx_rejects_plate_less_cross_section() -> None:
    from ocx_model_validator.sections.dlx_export import build_2dlx

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
        build_2dlx(vessel, cross_section, _frame_table())
