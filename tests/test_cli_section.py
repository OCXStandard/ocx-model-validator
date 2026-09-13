"""CLI tests for the section subcommands."""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

runner = CliRunner()


@pytest.fixture()
def model_310(stub_dir_310: Path) -> Path:
    return stub_dir_310 / "vessel.3docx"


@pytest.fixture()
def section_json(tmp_path: Path) -> Path:
    doc = {
        "schema": "nh-cross-section/1",
        "source": {"file": "ship.3docx", "vessel_id": "V1", "generated": "t"},
        "frame_table": {"frame0_offset_mm": 0.0, "entries": [], "positions": []},
        "cross_section": {
            "x_mm": 50_000.0,
            "frame": "FR20",
            "stiffeners": [{
                "name": "L1", "y_mm": 2_000.0, "z_mm": 0.0, "panel": None,
                "profile_type": "FlatBar", "profile_dimensions": "200 x 20",
                "material_reh_mpa": None, "spacing_mm": None,
                "orientation": "Longitudinal", "web_angle_deg": 90.0,
                "web_dir_y": 0.0, "web_dir_z": 1.0,
            }],
            "plates": [{
                "name": "P1", "y1_mm": 0.0, "z1_mm": 0.0,
                "y2_mm": 10_000.0, "z2_mm": 0.0, "thickness_mm": 12.5,
                "material_reh_mpa": None, "panel": None,
            }],
        },
        "compartments": [],
        "warnings": [],
    }
    path = tmp_path / "section.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


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


def test_section_plot_writes_svg(section_json: Path, tmp_path: Path):
    dest = tmp_path / "out.svg"
    result = runner.invoke(app, ["section", "plot", str(section_json),
                                 "--output", str(dest)])
    assert result.exit_code == 0
    svg = dest.read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert "Cross section at x=50000.0 mm (frame FR20)" in svg


def test_section_plot_default_output_is_svg_suffix(section_json: Path):
    result = runner.invoke(app, ["section", "plot", str(section_json)])
    assert result.exit_code == 0
    assert section_json.with_suffix(".svg").exists()


def test_section_plot_invalid_document_exits_1(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "wrong"}', encoding="utf-8")
    result = runner.invoke(app, ["section", "plot", str(bad)])
    assert result.exit_code == 1
