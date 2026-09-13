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


def test_six_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == {
        "load_model",
        "get_model_info",
        "get_frame_table",
        "get_compartments",
        "build_cross_section",
        "save_cross_section",
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


def test_pipeline_with_synthetic_model(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_load_vessel", lambda path: make_synthetic_vessel())
    assert server.load_model("fake.ocx")["ok"] is True
    info = server.get_model_info()
    assert info["ok"] and info["counts"]["stiffeners"] >= 1
    ft = server.get_frame_table()
    assert ft["ok"] and ft["frame_table"]["positions"]
    cs = server.build_cross_section(x_mm=5000.0)
    assert cs["ok"] and cs["document"]["cross_section"]["plates"]
    assert server.build_cross_section()["ok"] is False
    assert server.build_cross_section(x_mm=1.0, frame="0")["ok"] is False
    out = tmp_path / "sec.json"
    saved = server.save_cross_section(str(out), x_mm=5000.0)
    assert saved["ok"] and out.exists()
