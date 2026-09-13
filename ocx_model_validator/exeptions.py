"""Module exceptions"""
class ConverterError(ValueError):
    """Converter related errors."""


class ConverterWarning(Warning):
    """Converter related warnings."""


class XmlParserError(ValueError):
    """Parser errors."""

class SourceError(ValueError):
    """SourceValidator errors."""

class DynamicLoaderError(AttributeError):
    """Dynamic import errors."""


class GeometryError(XmlParserError):
    """Geometric evaluation failed (unsupported curve, bad units, degenerate input)."""


class SectionError(XmlParserError):
    """Cross-section assembly failed (no frame table, position outside hull, ...)."""
