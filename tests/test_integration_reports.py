"""Integration test: BOM report against the real VLCC reference model."""
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ocx_model_validator.cli import app

MODEL = Path(os.environ.get("OCX_VLCC_MODEL",
                            r"C:\PythonDev\models\D-VLCC_1-HOLD-OCX-simple_v3.3docx"))

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
