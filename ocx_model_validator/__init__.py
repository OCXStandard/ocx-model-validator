"""ocx_model_validator — parse and validate OCX .3docx ship model files.

Public API
----------
OcxParser       — parse a .3docx file into an OCX root dataclass
get_builder     — return the correct IR builder for a schema version
IrVessel        — root IR dataclass (schema-neutral)

Exceptions
----------
XmlParserError, SourceError, DynamicLoaderError, ConverterError
"""
from ocx_model_validator.exeptions import (
    ConverterError,
    ConverterWarning,
    DynamicLoaderError,
    SourceError,
    XmlParserError,
)
from ocx_model_validator.model.ir import IrVessel
from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.parsers.parser import OcxParser
from ocx_model_validator.parsers.dynamic_loader import DeclarationOfOcxImport, DynamicLoader

__version__ = "0.1.0"

__all__ = [
    "OcxParser",
    "get_builder",
    "IrVessel",
    "DeclarationOfOcxImport",
    "DynamicLoader",
    "XmlParserError",
    "SourceError",
    "DynamicLoaderError",
    "ConverterError",
    "ConverterWarning",
]
