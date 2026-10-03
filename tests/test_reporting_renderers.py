"""Tests for report renderers."""
import pytest

from ocx_model_validator.reporting.model import Link, Report, ReportSection, ReportTable
from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer


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


def test_markdown_escapes_pipes_and_newlines():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[
            ReportTable("T", ["A|B"], [["x|y"], ["line1\nline2"]])
        ])
    ])
    out = MarkdownRenderer().render(report)
    assert "| A\\|B |" in out
    assert "| x\\|y |" in out
    assert "| line1 line2 |" in out


def test_markdown_multiline_note_stays_in_blockquote():
    report = Report(title="R", sections=[
        ReportSection(title="S", notes=["first\nsecond"])
    ])
    out = MarkdownRenderer().render(report)
    assert "> first\n> second" in out


def test_markdown_empty_footer_cell_not_bolded():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[
            ReportTable("T", ["A", "B"], [["x", "y"]], footer_rows=[["Total", ""]])
        ])
    ])
    out = MarkdownRenderer().render(report)
    assert "| **Total** |  |" in out


def test_rich_renderer_smoke():
    out = RichRenderer().render(_sample_report())
    assert "Test report" in out
    assert "P1" in out
    assert "N/A" in out
    assert "Total" in out


def test_get_renderer_dispatch():
    assert isinstance(get_renderer("markdown").render(_sample_report()), str)
    assert isinstance(get_renderer("rich"), RichRenderer)


def test_get_renderer_unknown_format():
    with pytest.raises(ValueError, match="markdown, rich"):
        get_renderer("pdf")


def test_rich_renderer_escapes_markup_in_titles_and_notes():
    report = Report(
        title="Model [/bold] weird",
        metadata={"Key [x]": "value [/]"},
        sections=[ReportSection(title="S [/]", intro="intro [/]",
                                tables=[ReportTable("T [/]", ["A"], [["v"]])],
                                notes=["note [/bold]"])],
    )
    out = RichRenderer().render(report)  # must not raise MarkupError
    assert "weird" in out


def _link_report() -> Report:
    return Report(title="R", sections=[
        ReportSection(title="S", tables=[
            ReportTable("T", ["Material"],
                        [[Link("NV A36", "material-M1")]])
        ])
    ])


def test_markdown_link_renders_as_plain_text():
    out = MarkdownRenderer().render(_link_report())
    assert "| NV A36 |" in out
    assert "material-M1" not in out


def test_rich_link_renders_as_plain_text():
    out = RichRenderer().render(_link_report())
    assert "NV A36" in out
    assert "material-M1" not in out


def _grouped_report() -> Report:
    table = ReportTable(
        title="T",
        columns=["Group", "Count"],
        rows=[["G1", 2], ["Subtotal", 2]],
        row_children=[[["item-a", None], ["item-b", None]], []],
    )
    return Report(title="R", sections=[ReportSection(title="S", tables=[table])])


def test_markdown_child_rows_follow_parent():
    out = MarkdownRenderer().render(_grouped_report())
    lines = [ln for ln in out.splitlines() if ln.startswith("|")]
    assert lines[2] == "| **G1** | **2** |"  # group rows are bold
    assert lines[3] == "| item-a | N/A |"
    assert lines[4] == "| item-b | N/A |"
    assert lines[5] == "| Subtotal | 2 |"


def test_rich_child_rows_render():
    out = RichRenderer().render(_grouped_report())
    assert "item-a" in out
    assert "item-b" in out
