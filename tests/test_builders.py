"""Tests for builders — factory, IOcxBuilder contract, OcxV3Builder."""
from __future__ import annotations

import pytest

from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.builders.base import UnsupportedSchemaVersionError
from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import IrVessel


class TestBuilderFactory:

    def test_get_builder_300_returns_v3(self):
        b = get_builder("3.0.0")
        assert isinstance(b, OcxV3Builder)

    def test_get_builder_310_returns_v3(self):
        b = get_builder("3.1.0")
        assert isinstance(b, OcxV3Builder)

    def test_get_builder_320_returns_v3(self):
        b = get_builder("3.2.0")
        assert isinstance(b, OcxV3Builder)

    def test_get_builder_unknown_major_raises(self):
        with pytest.raises(UnsupportedSchemaVersionError):
            get_builder("9.0.0")

    def test_get_builder_junk_string_raises(self):
        with pytest.raises(UnsupportedSchemaVersionError):
            get_builder("not-a-version")

    def test_get_builder_empty_string_raises(self):
        with pytest.raises(UnsupportedSchemaVersionError):
            get_builder("")

    def test_each_call_returns_new_instance(self):
        b1 = get_builder("3.0.0")
        b2 = get_builder("3.0.0")
        assert b1 is not b2


class TestOcxV3BuilderContract:

    def test_supported_versions(self):
        b = OcxV3Builder()
        versions = b.supported_versions()
        assert (3, 0) in versions
        assert (3, 1) in versions

    def test_build_raises_on_missing_vessel(self):
        class FakeRoot:
            schema_version = "3.0.0"
            vessel = None
        b = OcxV3Builder()
        with pytest.raises(ValueError, match="no <Vessel>"):
            b.build(FakeRoot())


class TestOcxV3BuilderFromStub:
    """Builder primitive helper unit tests."""

    def test_v3_builder_qty_returns_none_for_none(self):
        from ocx_model_validator.model.ir import Quantity
        b = OcxV3Builder()
        assert b._qty(None) is None

    def test_v3_builder_qty_valid(self):
        from ocx_model_validator.model.ir import Quantity
        b = OcxV3Builder()

        class _Q:
            numericvalue = 12.5
            unit = "Umm"
        result = b._qty(_Q())
        assert isinstance(result, Quantity)
        assert result.value == 12.5
        assert result.unit == "Umm"

    def test_v3_builder_qty_non_numeric_returns_none(self):
        b = OcxV3Builder()

        class _Q:
            numericvalue = "not-a-number"
            unit = "Umm"
        assert b._qty(_Q()) is None

    def test_v3_builder_qty_none_value_returns_none(self):
        b = OcxV3Builder()

        class _Q:
            numericvalue = None
            unit = "Umm"
        assert b._qty(_Q()) is None
