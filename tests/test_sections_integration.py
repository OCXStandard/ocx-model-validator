"""Integration: real VLCC model end-to-end (parse -> frame table -> section -> JSON)."""
from pathlib import Path

import pytest

MODEL = Path(r"C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODEL.exists(), reason="VLCC reference model not present"),
]


@pytest.fixture(scope="module")
def vessel():
    from ocx_model_validator.builders.factory import get_builder
    from ocx_model_validator.parsers.parser import OcxParser
    root = OcxParser().parse(MODEL)
    return get_builder(getattr(root, "schema_version", "unknown")).build(root)


def test_frame_table(vessel):
    from ocx_model_validator.sections.frame_table import build_frame_table
    ft = build_frame_table(vessel)
    assert len(ft.positions) > 100          # ~402 X planes in the model
    assert ft.entries                        # at least one spacing entry
    xs = [x for _, x in ft.positions]
    assert xs == sorted(xs)


def test_midship_cross_section(vessel):
    from ocx_model_validator.sections.frame_table import build_frame_table
    from ocx_model_validator.sections.section_builder import build_cross_section
    ft = build_frame_table(vessel)
    mid_x = (ft.positions[0][1] + ft.positions[-1][1]) / 2.0
    label, x = ft.nearest_frame(mid_x)
    cs = build_cross_section(vessel, x_mm=x)
    assert len(cs.stiffeners) > 50
    assert len(cs.plates) > 10
    assert all(s.orientation == "Longitudinal" for s in cs.stiffeners)


def test_document_round_trip(vessel, tmp_path):
    from ocx_model_validator.sections import (
        build_document, load_document, save_document)
    from ocx_model_validator.sections.frame_table import build_frame_table
    ft = build_frame_table(vessel)
    label, x = ft.nearest_frame(
        (ft.positions[0][1] + ft.positions[-1][1]) / 2.0)
    doc = build_document(vessel, str(MODEL), x_mm=x)
    assert doc["schema"] == "nh-cross-section/2"
    assert doc["compartments"]
    p = tmp_path / "section.json"
    save_document(doc, p)
    assert load_document(p)["cross_section"]["stiffeners"]
