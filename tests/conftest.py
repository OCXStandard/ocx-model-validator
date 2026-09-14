"""conftest.py — shared pytest fixtures for ocx_model_validator tests.

Provides:
- ``data_dir``: path to tests/data/
- ``ocx_stub_version``: parametrized over all versioned stub directories
- ``stub_dir_310`` / ``declaration_310``: pinned fixtures for OCX 3.1.0
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ocx_model_validator.parsers.dynamic_loader import DeclarationOfOcxImport
from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.model.ir import IrVessel
from ocx_model_validator.parsers.parser import OcxParser
from tests.stubs import version_from_folder

DATA_DIR = Path(__file__).parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"  # agents/models/


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_session(model_file: str) -> tuple[OcxParser, IrVessel]:
    """Parse model_file and return (parser_root, ir)."""
    parser = OcxParser()
    root = parser.parse(model_file)
    builder = get_builder(root.schema_version)
    ir = builder.build(root)
    return root, ir


def _discover_stub_versions() -> dict[str, tuple[Path, DeclarationOfOcxImport]]:
    versions: dict[str, tuple[Path, DeclarationOfOcxImport]] = {}
    if not DATA_DIR.exists():
        return versions
    for folder in sorted(DATA_DIR.iterdir()):
        if folder.is_dir() and re.match(r"ocx_\d+_stubs$", folder.name):
            try:
                version = version_from_folder(folder.name)
            except ValueError:
                continue
            declaration = DeclarationOfOcxImport(name="ocx", version=version)
            versions[version] = (folder, declaration)
    return versions


_STUB_VERSIONS = _discover_stub_versions()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session", params=list(_STUB_VERSIONS.keys()))
def ocx_stub_version(request) -> tuple[str, Path, DeclarationOfOcxImport]:
    """Parametrized fixture — one entry per discovered stub directory."""
    version = request.param
    stub_dir, declaration = _STUB_VERSIONS[version]
    return version, stub_dir, declaration


@pytest.fixture(scope="session")
def stub_dir_310() -> Path:
    return DATA_DIR / "ocx_310_stubs"


@pytest.fixture(scope="session")
def declaration_310() -> DeclarationOfOcxImport:
    return DeclarationOfOcxImport(name="ocx", version="3.1.0")


@pytest.fixture(scope="session")
def hmx_schema():
    import xmlschema

    xsd = Path(__file__).parent / "data" / "hmx_schema" / "HullModel_HMX.xsd"
    return xmlschema.XMLSchema11(str(xsd))
