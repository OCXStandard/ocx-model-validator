"""Integration: section create -> JSON -> plot -> SVG on the VLCC model."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

MODEL = Path(r"C:\PythonDev\nh-mcp\examples\D-VLCC_1-HOLD-OCX-simple_v3.3docx")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODEL.exists(), reason="VLCC reference model not present"),
]

runner = CliRunner()


def test_create_then_plot(tmp_path: Path):
    doc_path = tmp_path / "section.json"
    created = runner.invoke(app, ["section", "create", str(MODEL),
                                  "--x", "161300",
                                  "--output", str(doc_path)])
    assert created.exit_code == 0, created.output
    assert doc_path.exists()

    svg_path = tmp_path / "section.svg"
    plotted = runner.invoke(app, ["section", "plot", str(doc_path),
                                  "--output", str(svg_path)])
    assert plotted.exit_code == 0, plotted.output
    svg = svg_path.read_text(encoding="utf-8")
    assert svg.count('class="plate"') > 10
    assert svg.count('class="stiffener"') > 50
    assert "Plate thickness" in svg
