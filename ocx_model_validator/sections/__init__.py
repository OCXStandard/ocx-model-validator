"""Cross-section extraction from OCX IR models."""
from ocx_model_validator.sections.document import build_document, load_document, save_document
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table
from ocx_model_validator.sections.section_builder import (
    CrossSection,
    SectionPlate,
    SectionStiffener,
    build_cross_section,
)

__all__ = [
    "FrameTable",
    "build_frame_table",
    "CrossSection",
    "SectionPlate",
    "SectionStiffener",
    "build_cross_section",
    "build_document",
    "save_document",
    "load_document",
]
