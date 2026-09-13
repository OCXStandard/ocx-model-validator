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
