"""Tests for the neutral report data model."""
from ocx_model_validator.reporting.model import Link, Report, ReportSection, ReportTable


def test_report_table_defaults():
    t = ReportTable(title="T", columns=["A", "B"], rows=[["x", 1]])
    assert t.footer_rows == []
    assert t.rows[0] == ["x", 1]


def test_report_defaults():
    r = Report(title="R")
    assert r.metadata == {}
    assert r.sections == []


def test_section_defaults():
    s = ReportSection(title="S")
    assert s.intro is None
    assert s.tables == []
    assert s.notes == []


def test_link_cell():
    link = Link(text="NV A36", target="material-M1")
    assert link.text == "NV A36"
    assert link.target == "material-M1"
    t = ReportTable(title="T", columns=["A"], rows=[[link]])
    assert t.rows[0][0] is link


def test_report_table_row_anchors():
    t = ReportTable(
        title="T",
        columns=["A"],
        rows=[["x"], ["y"]],
        row_anchors=["material-M1", None],
    )
    assert t.row_anchors == ["material-M1", None]


def test_report_table_row_anchors_default_empty():
    t = ReportTable(title="T", columns=["A"], rows=[["x"]])
    assert t.row_anchors == []
