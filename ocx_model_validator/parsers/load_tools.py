"""Compatibility shim — ``parsers.load_tools`` re-exports from canonical modules.

Historic code (mcp_server.py, conftest.py) referenced this path before the
parser and loader were split into ``parser.py`` / ``dynamic_loader.py``.
Import from the canonical modules directly for new code.
"""
from ocx_model_validator.exeptions import DynamicLoaderError  # noqa: F401
from ocx_model_validator.parsers.dynamic_loader import (  # noqa: F401
    DeclarationOfOcxImport,
    DynamicLoader,
    ModuleDeclaration,
)
from ocx_model_validator.parsers.parser import OcxParser, OcxVersion  # noqa: F401
from ocx_model_validator.utils import MetaData  # noqa: F401

__all__ = [
    "OcxParser",
    "OcxVersion",
    "DynamicLoader",
    "DeclarationOfOcxImport",
    "DynamicLoaderError",
    "ModuleDeclaration",
    "MetaData",
]
