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
