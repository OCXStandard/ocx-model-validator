"""OCX parsers package."""
from .parser import OcxParser, OcxVersion
from .dynamic_loader import DynamicLoader, DeclarationOfOcxImport

__all__ = ["OcxParser", "OcxVersion", "DynamicLoader", "DeclarationOfOcxImport"]

