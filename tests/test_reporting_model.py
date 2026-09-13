"""Tests for the neutral report data model."""
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable


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
