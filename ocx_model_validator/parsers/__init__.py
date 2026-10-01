"""OCX parsers package."""
from .dynamic_loader import DeclarationOfOcxImport, DynamicLoader
from .parser import OcxParser, OcxVersion

__all__ = ["OcxParser", "OcxVersion", "DynamicLoader", "DeclarationOfOcxImport"]

