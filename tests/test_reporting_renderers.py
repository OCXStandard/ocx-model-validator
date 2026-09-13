"""Tests for report renderers."""
from ocx_model_validator.reporting.model import Report, ReportSection, ReportTable
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer


def _sample_report() -> Report:
    table = ReportTable(
        title="Parts",
        columns=["Id", "Weight (t)"],
        rows=[["P1", 1.5], ["P2", None]],
        footer_rows=[["Total", 1.5]],
    )
    section = ReportSection(title="BOM", intro="Grouped by material.",
                            tables=[table], notes=["1 item missing weight"])
    return Report(title="Test report",
                  metadata={"Vessel": "MV Test", "Schema version": "3.1.0"},
                  sections=[section])


def test_markdown_full_document():
    out = MarkdownRenderer().render(_sample_report())
    assert out == (
        "# Test report\n"
        "\n"
        "- **Vessel:** MV Test\n"
        "- **Schema version:** 3.1.0\n"
        "\n"
        "## BOM\n"
        "\n"
        "Grouped by material.\n"
        "\n"
        "### Parts\n"
        "\n"
        "| Id | Weight (t) |\n"
        "|---|---|\n"
        "| P1 | 1.5 |\n"
        "| P2 | N/A |\n"
        "| **Total** | **1.5** |\n"
        "\n"
        "> 1 item missing weight\n"
    )


def test_markdown_empty_table_renders_empty_marker():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[ReportTable("T", ["A", "B"], [])])
    ])
    out = MarkdownRenderer().render(report)
    assert "| (empty) |  |" in out
