"""Tests for the Nauticus Hull 2DLX cross-section export."""
from __future__ import annotations

from dataclasses import replace

import pytest

from ocx_model_validator.sections.section_builder import (
    CrossSection,
    SectionPlate,
    SectionStiffener,
    build_cross_section,
)
from tests.section_fixtures import make_synthetic_vessel
from tests.test_hmx_export import (
    _assert_only_nauticus_empty_wrapper_errors,
    _frame_table,
)


def test_dlx_schema_loads(dlx_schema):
    assert dlx_schema is not None
    assert "CROSS_SECTION" in dlx_schema.elements
