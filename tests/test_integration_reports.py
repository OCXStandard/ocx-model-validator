"""Integration test: BOM report against the real VLCC reference model."""
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

MODEL = Path(os.environ.get("OCX_VLCC_MODEL",
                            r"models\D-VLCC_1-HOLD-OCX-simple_v3.3docx"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODEL.exists(), reason="VLCC reference model not present"),
]

runner = CliRunner()


def test_bom_report_on_reference_model(tmp_path: Path):
    dest = tmp_path / "bom.md"
    result = runner.invoke(
        app,
        ["report", "bom", str(MODEL), "--detailed", "--destination", str(dest)],
    )
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert "### Summary" in text
    assert "### Items" in text
    assert "**Grand total**" in text
    total_line = next(ln for ln in text.splitlines() if "Grand total" in ln)
    weight = float(total_line.split("|")[5].strip().strip("*"))
    assert weight > 0


TR05_MODEL = Path("models/TR05/tr05_tc04a_mbrh.3docx")


@pytest.mark.skipif(not TR05_MODEL.exists(),
                    reason="TR05 reference model not present")
def test_report_all_html_links_resolve_on_tr05(tmp_path: Path):
    dest = tmp_path / "all.html"
    result = runner.invoke(
        app, ["report", "all", str(TR05_MODEL), "--destination", str(dest)])
    assert result.exit_code == 0
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    # BOM material links resolve to materials-catalogue row anchors
    assert 'href="#material-' in text
    assert 'id="material-' in text
