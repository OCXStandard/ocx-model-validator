"""ocx-mcp server tools (unit level, synthetic vessel via monkeypatched loader)."""
import asyncio

import pytest

from ocx_model_validator.mcp import server, state
from tests.section_fixtures import make_synthetic_vessel


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()
    yield
    state.reset()


def test_five_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {
        "load_model",
        "get_model_info",
        "get_frame_table",
        "get_compartments",
        "apply_scantlings",
    }


def test_all_tools_have_descriptions():
    """Verify all tools have non-empty descriptions for LLM clients."""
    tools = asyncio.run(server.mcp.list_tools())
    for tool in tools:
        assert tool.description, f"Tool '{tool.name}' has empty description"
        assert len(tool.description.strip()) > 0, f"Tool '{tool.name}' has whitespace-only description"


def test_tools_require_loaded_model():
    for fn in (
        server.get_model_info,
        server.get_frame_table,
        server.get_compartments,
    ):
        out = fn()
        assert out["ok"] is False and "load_model" in out["error"]


def test_load_model_missing_file():
    out = server.load_model(r"C:\nope\missing.ocx")
    assert out["ok"] is False


def test_pipeline_with_synthetic_model(monkeypatch):
    monkeypatch.setattr(server, "_load_vessel", lambda path: make_synthetic_vessel())
    assert server.load_model("fake.ocx")["ok"] is True
    info = server.get_model_info()
    assert info["ok"] and info["counts"]["stiffeners"] >= 1
    ft = server.get_frame_table()
    assert ft["ok"] and ft["frame_table"]["positions"]
    comp = server.get_compartments()
    assert comp["ok"]


def test_apply_scantlings_ok(tmp_path):
    # reuse the writeback test fixture model
    import json

    from tests.test_writeback import make_model, make_report, plate_row

    model = make_model(tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(make_report(plates=[plate_row()])),
                           encoding="utf-8")
    out = tmp_path / "patched.3docx"
    result = server.apply_scantlings(str(model), str(report_path), str(out))
    assert result["ok"] is True
    assert result["plates_updated"] == 1
    assert out.exists()


def test_apply_scantlings_error_dict():
    result = server.apply_scantlings("no-such.3docx", "no-such.json",
                                     "out.3docx")
    assert result["ok"] is False
    assert "error" in result
