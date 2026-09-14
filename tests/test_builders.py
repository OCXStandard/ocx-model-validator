"""Tests for builders — factory, IOcxBuilder contract, OcxV3Builder."""
from __future__ import annotations

import pytest

from ocx_model_validator.builders.factory import get_builder
from ocx_model_validator.builders.base import UnsupportedSchemaVersionError
from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import IrVessel, ParentKind, ParentRef


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


class _StubVector3D:
    def __init__(self, direction):
        self.direction = direction


class _StubPoint3D:
    def __init__(self, coordinates, unit="Um"):
        self.coordinates = coordinates
        self.unit = unit


class _StubInclination:
    def __init__(self, web_direction=None, flange_direction=None, position=None):
        self.web_direction = web_direction
        self.flange_direction = flange_direction
        self.position = position


class _StubStiffenerWithInclination:
    id = "S1"
    name = "L1"
    guidref = None
    physical_properties = None
    material_ref = None
    section_ref = None
    function_type = None
    end_cut_end1 = None
    end_cut_end2 = None
    trace_line = None
    inclination = [
        _StubInclination(
            web_direction=_StubVector3D([0.0, 0.0, 1.0]),
            position=_StubPoint3D([10.0, 0.0, 5.0]),
        )
    ]


def test_build_stiffener_extracts_inclinations():
    builder = OcxV3Builder()
    parent = ParentRef(kind=ParentKind.VESSEL, id="V1")
    s = builder._build_stiffener(_StubStiffenerWithInclination(), parent)
    assert len(s.inclinations) == 1
    inc = s.inclinations[0]
    assert inc.web_direction.z == 1.0
    assert inc.flange_direction is None
    assert inc.position.x == 10.0


def test_build_stiffener_without_inclination_defaults_empty():
    class _Bare(_StubStiffenerWithInclination):
        inclination = None

    builder = OcxV3Builder()
    parent = ParentRef(kind=ParentKind.VESSEL, id="V1")
    s = builder._build_stiffener(_Bare(), parent)
    assert s.inclinations == []


class _StubQuantity:
    numericvalue = 10.0
    unit = "Um"


class _StubRefPlane:
    def __init__(self, pid, display_grid=None):
        self.id = pid
        self.name = f"plane-{pid}"
        self.reference_location = _StubQuantity()
        self.display_grid = display_grid


class _StubXRefPlanes:
    def __init__(self, planes):
        self.ref_plane = planes


class _StubCoordinateSystem:
    id = "cs1"
    name = None
    is_global = True
    local_cartesian = None
    yref_planes = None
    zref_planes = None

    def __init__(self, planes):
        self.xref_planes = _StubXRefPlanes(planes)


def test_build_coordinate_system_extracts_display_grid():
    builder = OcxV3Builder()
    ir = IrVessel(id="V1")
    cs = _StubCoordinateSystem([
        _StubRefPlane("rp1", display_grid=True),
        _StubRefPlane("rp2", display_grid=False),
        _StubRefPlane("rp3"),
    ])
    builder._build_coordinate_system(cs, ir)
    assert ir.ref_planes["rp1"].display_grid is True
    assert ir.ref_planes["rp2"].display_grid is False
    assert ir.ref_planes["rp3"].display_grid is None
