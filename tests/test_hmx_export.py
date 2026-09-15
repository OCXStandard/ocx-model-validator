from __future__ import annotations

import math
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

    _assert_only_nauticus_empty_wrapper_errors(hmx_schema, path)
    assert root.tag == "HullModel"

    scantlings = root.findall("./CrossSections/Scantling")
    assert len(scantlings) == 1
    scantling = scantlings[0]
    assert len(scantling.findall("./PANEL")) == 2
    assert len(scantling.findall(".//PLATE")) == 2

    real_stiffeners = scantling.findall(".//LSTIFF")
    assert len(real_stiffeners) == 3
    assert all(not stiffener.get("Name", "").startswith("__schema_placeholder__") for stiffener in real_stiffeners)
    assert not scantling.findall(".//CUTOUT")
    assert not scantling.findall(".//TSTIFF")

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

    _assert_only_nauticus_empty_wrapper_errors(hmx_schema, path)
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

    _assert_only_nauticus_empty_wrapper_errors(hmx_schema, path)
    assert "--" not in root[0].text
    assert not root[0].text.endswith("-")


def test_build_hmx_splits_closed_shell_ring_into_two_open_panels(hmx_schema, tmp_path) -> None:
    # Nauticus Hull cannot import a PANEL whose SHAPE is a closed loop
    # ("Could not find start of panel"); the shell must be two open panels
    # split at the centerline, each starting at the bottom-CL node.
    vessel = make_synthetic_vessel()
    ring_plates = [
        SectionPlate(
            name=name,
            y1_mm=y1,
            z1_mm=z1,
            y2_mm=y2,
            z2_mm=z2,
            thickness_mm=10.0,
            material_reh_mpa=315.0,
            panel="SHELL",
        )
        for name, y1, z1, y2, z2 in [
            ("bot-s", 0.0, 0.0, 10000.0, 0.0),
            ("side-s", 10000.0, 0.0, 10000.0, 8000.0),
            ("deck", 10000.0, 8000.0, -10000.0, 8000.0),
            ("side-p", -10000.0, 8000.0, -10000.0, 0.0),
            ("bot-p", -10000.0, 0.0, 0.0, 0.0),
        ]
    ]
    cross_section = replace(
        build_cross_section(vessel, 5000.0), plates=ring_plates, stiffeners=[]
    )

    root = build_hmx(vessel, cross_section, _frame_table())
    path = tmp_path / "ring-section.hmx"
    save_hmx(root, path)

    _assert_only_nauticus_empty_wrapper_errors(hmx_schema, path)
    panels = root.findall("./CrossSections/Scantling/PANEL")
    assert len(panels) == 2
    for panel in panels:
        node = panel.find("./SHAPE/NODE")
        segments = panel.findall("./SHAPE/SEGMENT")
        assert (float(node.get("Y")), float(node.get("Z"))) == pytest.approx((0.0, 0.0))
        last = segments[-1]
        assert (float(last.get("Y")), float(last.get("Z"))) == pytest.approx((0.0, 8000.0))
        # No seams in the synthetic vessel: each chain merges into one PLATE.
        plate_elements = panel.findall("./PLATES/PLATE")
        assert len(plate_elements) == 1
        expected_length = sum(
            math.hypot(
                float(b.get("Y")) - float(a.get("Y")),
                float(b.get("Z")) - float(a.get("Z")),
            )
            for a, b in zip([node, *segments], segments)
        )
        assert float(plate_elements[0].get("Width")) == pytest.approx(expected_length)


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


def _assert_only_nauticus_empty_wrapper_errors(hmx_schema, path) -> None:
    # Nauticus Hull's own docs/ISSCFrame170.hmx leaves these wrappers empty,
    # producing the same strict-schema cardinality pattern pinned in
    # tests/test_hmx_schema.py. We allow only those compatibility errors.
    allowed_tags = {"CUTOUTS", "TRVSTIFFS", "LONGS"}
    errors = list(hmx_schema.iter_errors(str(path)))

    assert errors, "strict schema should report the known empty-wrapper cardinality errors"
    for error in errors:
        elem_tag = getattr(getattr(error, "elem", None), "tag", "")
        reason = getattr(error, "reason", "")
        path_text = getattr(error, "path", "")
        message = " ".join(str(part) for part in (elem_tag, reason, path_text))

        assert elem_tag in allowed_tags or any(tag in message for tag in allowed_tags), (
            f"unexpected schema error outside Nauticus empty wrappers: {error}"
        )
        assert "content" in reason.lower() or "expected" in reason.lower(), (
            f"unexpected non-cardinality schema error: {error}"
        )
