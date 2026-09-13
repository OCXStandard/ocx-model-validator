"""CLI tests for the section subcommands."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

runner = CliRunner()


@pytest.fixture()
def model_310(stub_dir_310: Path) -> Path:
    return stub_dir_310 / "vessel.3docx"


def test_section_create_requires_exactly_one_position(model_310: Path):
    both = runner.invoke(app, ["section", "create", str(model_310),
                               "--frame", "FR20", "--x", "1000"])
    neither = runner.invoke(app, ["section", "create", str(model_310)])
    assert both.exit_code != 0
    assert neither.exit_code != 0


def test_section_create_no_geometry_exits_1(model_310: Path, tmp_path: Path):
    # the vessel stub has no intersectable geometry -> SectionError -> exit 1
    result = runner.invoke(app, ["section", "create", str(model_310),
                                 "--x", "1000",
                                 "--output", str(tmp_path / "s.json")])
    assert result.exit_code == 1


def test_section_create_missing_model_exits_nonzero():
    result = runner.invoke(app, ["section", "create", "no_such.3docx",
                                 "--x", "1000"])
    assert result.exit_code != 0


def test_default_output_name():
    from ocx_model_validator.cli import _default_section_output

    assert _default_section_output(Path("a/ship.3docx"), frame="FR20", x_mm=None) \
        == Path("ship-FR20.json")
    assert _default_section_output(Path("ship.3docx"), frame=None, x_mm=50_000.0) \
        == Path("ship-x50000.json")
    assert _default_section_output(Path("s.3docx"), frame="FR 2/b", x_mm=None) \
        == Path("s-FR_2_b.json")
