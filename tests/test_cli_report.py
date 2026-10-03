"""CLI tests for the report subcommands (typer CliRunner)."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

runner = CliRunner()


@pytest.fixture()
def model_310(stub_dir_310: Path) -> Path:
    """A small real model file: the vessel stub for OCX 3.1.0."""
    return stub_dir_310 / "vessel.3docx"


def test_report_frame_table_rich_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310)])
    assert result.exit_code == 0
    assert "Frame table report" in result.output


def test_report_frame_table_markdown_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("# Frame table report")


def test_report_destination_writes_markdown(model_310: Path, tmp_path: Path):
    dest = tmp_path / "out.md"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("# Frame table report")


def test_report_destination_rejects_rich(model_310: Path, tmp_path: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "rich",
                                 "--destination", str(tmp_path / "x.md")])
    assert result.exit_code != 0


def test_report_missing_model_file():
    result = runner.invoke(app, ["report", "frame-table", "no_such.3docx"])
    assert result.exit_code != 0


def test_generate_stubs_command_exists():
    result = runner.invoke(app, ["generate-stubs", "--help"])
    assert result.exit_code == 0


def test_report_compartments(model_310: Path):
    result = runner.invoke(app, ["report", "compartments", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Compartments report" in result.output


def test_report_catalogues_filter(model_310: Path):
    result = runner.invoke(app, ["report", "catalogues", str(model_310),
                                 "--catalogue", "material",
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "## Materials" in result.output
    assert "## Cross sections" not in result.output


def test_report_bom(model_310: Path):
    result = runner.invoke(app, ["report", "bom", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Bill of material report" in result.output
    assert "### Summary" in result.output


def test_report_panels(model_310: Path):
    result = runner.invoke(app, ["report", "panels", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Panel report" in result.output
    assert "## Panels" in result.output
    assert "LimitedBy" in result.output


def test_report_plates(model_310: Path):
    result = runner.invoke(app, ["report", "plates", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Plate report" in result.output
    assert "## Plates" in result.output
    assert "Thickness (mm)" in result.output


def test_report_stiffeners(model_310: Path):
    result = runner.invoke(app, ["report", "stiffeners", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Stiffener report" in result.output
    assert "## Stiffeners" in result.output
    assert "Length (m)" in result.output


def test_report_brackets(model_310: Path):
    result = runner.invoke(app, ["report", "brackets", str(model_310),
                                 "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Bracket report" in result.output
    assert "## Brackets" in result.output
    assert "Arm length U (mm)" in result.output


def test_report_all(model_310: Path, tmp_path: Path):
    dest = tmp_path / "all.md"
    result = runner.invoke(app, ["report", "all", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("# Model report")
    for heading in ["## Model extent", "## Frame table", "## Compartments",
                    "## Panels", "## Plates", "## Stiffeners", "## Brackets",
                    "## Materials", "## Bill of material"]:
        assert heading in text
    # model extent comes first
    assert text.index("## Model extent") < text.index("## Frame table")


def test_report_destination_html_suffix_infers_html(model_310: Path, tmp_path: Path):
    dest = tmp_path / "out.html"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert "<title>Frame table report</title>" in text


def test_report_destination_htm_uppercase_suffix(model_310: Path, tmp_path: Path):
    dest = tmp_path / "OUT.HTM"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_report_format_html_to_stdout(model_310: Path):
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "html"])
    assert result.exit_code == 0
    assert result.output.startswith("<!DOCTYPE html>")


def test_report_explicit_markdown_wins_over_html_suffix(model_310: Path,
                                                        tmp_path: Path):
    dest = tmp_path / "out.html"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "markdown",
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("# Frame table report")


def test_report_format_html_to_md_destination_writes_html(model_310: Path,
                                                          tmp_path: Path):
    dest = tmp_path / "out.md"
    result = runner.invoke(app, ["report", "frame-table", str(model_310),
                                 "--format", "html",
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    assert dest.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_report_all_html_has_tabs_and_links(model_310: Path, tmp_path: Path):
    dest = tmp_path / "all.html"
    result = runner.invoke(app, ["report", "all", str(model_310),
                                 "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    for title in ["Model extent", "Frame table", "Compartments",
                  "Materials", "Bill of material"]:
        assert f">{title}</button>" in text
    # catalogue anchors exist whenever the model declares materials
    if 'id="material-' in text:
        assert "tab-panel" in text
