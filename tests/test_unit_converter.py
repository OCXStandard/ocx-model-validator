"""Tests for IrUnit, build_unit_registry, and UnitConverter.
Covers:
- IrUnit dataclass construction and immutability
- _compute_to_si_factor for all common OCX units
- build_unit_registry with stub UnitsMl objects
- UnitConverter.to_si and .convert_quantity
- IrVessel.unit_registry populated by OcxV3Builder
- Graceful degradation when units_ml is None or unit id is unknown
"""
from __future__ import annotations
import math
import pytest
from ocx_model_validator.builders import OcxV3Builder
from ocx_model_validator.model import IrUnit, Quantity
from ocx_model_validator.model.units import (
    UnitConverter,
    _compute_to_si_factor,
    build_unit_registry,
)
from tests.object_stubs import (
    StubEnumeratedRootUnit,
    StubRootUnits,
    StubRoot,
    StubUnit,
    StubUnitSet,
    StubUnitsMl,
    StubVessel,
)
def _make_length_unit(uid, name, symbol, base, prefix=None, power=1):
    eru = StubEnumeratedRootUnit(unit=base, prefix=prefix, power_numerator=power)
    return StubUnit(id=uid, name=name, symbol=symbol, dimension_url="D_L",
                    root_units=StubRootUnits([eru]))
def _make_compound_unit(uid, name, symbol, dim_url, root_units):
    return StubUnit(id=uid, name=name, symbol=symbol, dimension_url=dim_url,
                    root_units=StubRootUnits(root_units))
def _units_ml_with(*units):
    return StubUnitsMl(StubUnitSet(list(units)))
def _make_converter(*units):
    reg = build_unit_registry(_units_ml_with(*units))
    return UnitConverter(reg)
class TestIrUnit:
    def test_construction(self):
        u = IrUnit(id="Um", name="meter", symbol="m",
                   dimension_url="D_L", to_si_factor=1.0, si_symbol="m")
        assert u.id == "Um"
        assert u.to_si_factor == 1.0
        assert u.si_symbol == "m"
    def test_immutable(self):
        u = IrUnit(id="Um", name="meter", symbol="m",
                   dimension_url="D_L", to_si_factor=1.0, si_symbol="m")
        with pytest.raises((AttributeError, TypeError)):
            u.to_si_factor = 99.0
    def test_repr_contains_id(self):
        u = IrUnit(id="Umm", name="millimeter", symbol="mm",
                   dimension_url="D_L", to_si_factor=1e-3, si_symbol="m")
        assert "Umm" in repr(u)
class TestComputeToSiFactor:
    def test_meter_no_prefix(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix=None, power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1.0)
    def test_millimeter(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix="m", power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1e-3)
    def test_centimeter(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix="c", power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1e-2)
    def test_kilometer(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix="k", power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1e3)
    def test_kilogram(self):
        eru = StubEnumeratedRootUnit(unit="gram", prefix="k", power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1.0)
    def test_metric_ton(self):
        eru = StubEnumeratedRootUnit(unit="metric_ton", prefix=None, power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1000.0)
    def test_square_meter(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix=None, power_numerator=2)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1.0)
    def test_square_centimeter(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix="c", power_numerator=2)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1e-4)
    def test_cubic_meter(self):
        eru = StubEnumeratedRootUnit(unit="meter", prefix=None, power_numerator=3)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1.0)
    def test_n_per_mm2_to_pascal(self):
        eru_n = StubEnumeratedRootUnit(unit="newton", prefix=None, power_numerator=1)
        eru_m = StubEnumeratedRootUnit(unit="meter",  prefix="m",  power_numerator=-2)
        assert _compute_to_si_factor(StubRootUnits([eru_n, eru_m])) == pytest.approx(1e6)
    def test_n_per_m2_is_pascal(self):
        eru_n = StubEnumeratedRootUnit(unit="newton", prefix=None, power_numerator=1)
        eru_m = StubEnumeratedRootUnit(unit="meter",  prefix=None, power_numerator=-2)
        assert _compute_to_si_factor(StubRootUnits([eru_n, eru_m])) == pytest.approx(1.0)
    def test_kg_per_m3(self):
        eru_kg = StubEnumeratedRootUnit(unit="gram",  prefix="k",  power_numerator=1)
        eru_m  = StubEnumeratedRootUnit(unit="meter", prefix=None, power_numerator=-3)
        assert _compute_to_si_factor(StubRootUnits([eru_kg, eru_m])) == pytest.approx(1.0)
    def test_kilonewton(self):
        eru = StubEnumeratedRootUnit(unit="newton", prefix="k", power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(1e3)
    def test_arc_degree(self):
        eru = StubEnumeratedRootUnit(unit="arc_degree", prefix=None, power_numerator=1)
        assert _compute_to_si_factor(StubRootUnits([eru])) == pytest.approx(math.pi / 180.0)
    def test_none_root_units_returns_one(self):
        assert _compute_to_si_factor(None) == 1.0
    def test_empty_root_units_returns_one(self):
        assert _compute_to_si_factor(StubRootUnits([])) == 1.0
class TestBuildUnitRegistry:
    def test_empty_when_units_ml_none(self):
        assert build_unit_registry(None) == {}
    def test_empty_when_no_unit_set(self):
        assert build_unit_registry(StubUnitsMl(unit_set=None)) == {}
    def test_single_meter_unit(self):
        um = _make_length_unit("Um", "meter", "m", "meter")
        reg = build_unit_registry(_units_ml_with(um))
        assert "Um" in reg
        u = reg["Um"]
        assert isinstance(u, IrUnit)
        assert u.symbol == "m"
        assert u.to_si_factor == pytest.approx(1.0)
        assert u.si_symbol == "m"
        assert u.dimension_url == "D_L"
    def test_millimeter_unit(self):
        umm = _make_length_unit("Umm", "millimeter", "mm", "meter", prefix="m")
        reg = build_unit_registry(_units_ml_with(umm))
        assert reg["Umm"].to_si_factor == pytest.approx(1e-3)
        assert reg["Umm"].si_symbol == "m"
    def test_kilogram_unit(self):
        ukg = StubUnit(id="UKg", name="kilogram", symbol="kg", dimension_url="D_Kg",
                       root_units=StubRootUnits([StubEnumeratedRootUnit("gram", "k", 1)]))
        reg = build_unit_registry(_units_ml_with(ukg))
        assert reg["UKg"].to_si_factor == pytest.approx(1.0)
        assert reg["UKg"].si_symbol == "kg"
    def test_n_per_mm2_unit(self):
        u = _make_compound_unit("UNOvermm2", "N/mm2", "N/mm2", "D_N.MM-2",
                                [StubEnumeratedRootUnit("newton", None, 1),
                                 StubEnumeratedRootUnit("meter",  "m", -2)])
        reg = build_unit_registry(_units_ml_with(u))
        assert reg["UNOvermm2"].to_si_factor == pytest.approx(1e6)
        assert reg["UNOvermm2"].si_symbol == "Pa"
    def test_dimensionless_unit(self):
        u = StubUnit(id="UDimless", name="dimensionless", symbol="",
                     dimension_url="D_None", root_units=None)
        reg = build_unit_registry(_units_ml_with(u))
        assert reg["UDimless"].to_si_factor == pytest.approx(1.0)
        assert reg["UDimless"].si_symbol == ""
    def test_multiple_units(self):
        um  = _make_length_unit("Um",  "meter",      "m",  "meter")
        umm = _make_length_unit("Umm", "millimeter", "mm", "meter", "m")
        ucm = _make_length_unit("Ucm", "centimeter", "cm", "meter", "c")
        reg = build_unit_registry(_units_ml_with(um, umm, ucm))
        assert len(reg) == 3
        assert reg["Um"].to_si_factor  == pytest.approx(1.0)
        assert reg["Umm"].to_si_factor == pytest.approx(1e-3)
        assert reg["Ucm"].to_si_factor == pytest.approx(1e-2)
    def test_unit_without_id_is_skipped(self):
        u = _make_length_unit("Um", "meter", "m", "meter")
        u.id = ""
        reg = build_unit_registry(_units_ml_with(u))
        assert reg == {}
    def test_real_model_unit_set(self):
        from pathlib import Path
        from ocx_model_validator.parsers.load_tools import OcxParser
        model = Path("models/TR03_TC10_nast.3docx")
        if not model.exists():
            pytest.skip("Model not found")
        root = OcxParser().parse(str(model))
        reg = build_unit_registry(getattr(root, "units_ml", None))
        assert "Um"  in reg
        assert "Umm" in reg
        assert "UKg" in reg
        assert reg["Um"].to_si_factor  == pytest.approx(1.0)
        assert reg["Umm"].to_si_factor == pytest.approx(1e-3)
        assert reg["UKg"].to_si_factor == pytest.approx(1.0)
        assert reg["UNOvermm2"].to_si_factor == pytest.approx(1e6)
class TestUnitConverter:
    def test_to_si_meter(self):
        uc = _make_converter(_make_length_unit("Um", "meter", "m", "meter"))
        assert uc.to_si(5.0, "Um") == pytest.approx(5.0)
    def test_to_si_millimeter(self):
        uc = _make_converter(_make_length_unit("Umm", "mm", "mm", "meter", "m"))
        assert uc.to_si(1000.0, "Umm") == pytest.approx(1.0)
    def test_to_si_unknown_unit_returns_value_unchanged(self):
        uc = UnitConverter({})
        assert uc.to_si(42.0, "UUnknown") == pytest.approx(42.0)
    def test_to_si_zero(self):
        uc = _make_converter(_make_length_unit("Umm", "mm", "mm", "meter", "m"))
        assert uc.to_si(0.0, "Umm") == pytest.approx(0.0)
    def test_to_si_negative(self):
        uc = _make_converter(_make_length_unit("Umm", "mm", "mm", "meter", "m"))
        assert uc.to_si(-500.0, "Umm") == pytest.approx(-0.5)
    def test_convert_quantity_none_returns_none(self):
        assert UnitConverter({}).convert_quantity(None) is None
    def test_convert_quantity_mm_to_m(self):
        uc = _make_converter(_make_length_unit("Umm", "mm", "mm", "meter", "m"))
        q = uc.convert_quantity(Quantity(500.0, "Umm"))
        assert q.value == pytest.approx(0.5)
        assert q.unit == "m"
    def test_convert_quantity_unknown_unit_passthrough(self):
        uc = UnitConverter({})
        q = Quantity(99.0, "UMystery")
        assert uc.convert_quantity(q) is q
    def test_convert_quantity_kg_unchanged(self):
        ukg = StubUnit(id="UKg", name="kilogram", symbol="kg", dimension_url="D_Kg",
                       root_units=StubRootUnits([StubEnumeratedRootUnit("gram", "k", 1)]))
        uc = _make_converter(ukg)
        q = uc.convert_quantity(Quantity(7850.0, "UKg"))
        assert q.value == pytest.approx(7850.0)
        assert q.unit == "kg"
    def test_convert_quantity_stress(self):
        u = _make_compound_unit("UNOvermm2", "N/mm2", "N/mm2", "D_N.MM-2",
                                [StubEnumeratedRootUnit("newton", None, 1),
                                 StubEnumeratedRootUnit("meter",  "m", -2)])
        uc = _make_converter(u)
        q = uc.convert_quantity(Quantity(235.0, "UNOvermm2"))
        assert q.value == pytest.approx(235e6)
        assert q.unit == "Pa"
    def test_get_unit_returns_ir_unit(self):
        uc = _make_converter(_make_length_unit("Um", "meter", "m", "meter"))
        assert isinstance(uc.get_unit("Um"), IrUnit)
    def test_get_unit_none_for_missing(self):
        assert UnitConverter({}).get_unit("UMissing") is None
    def test_si_symbol_for_length(self):
        uc = _make_converter(_make_length_unit("Um", "meter", "m", "meter"))
        assert uc.si_symbol("Um") == "m"
    def test_si_symbol_empty_for_missing(self):
        assert UnitConverter({}).si_symbol("UMissing") == ""
class TestBuilderUnitRegistry:
    def _root_with_units(self, *units):
        return StubRoot(schema_version="3.1.0", vessel=StubVessel(id="V1"),
                        units_ml=StubUnitsMl(StubUnitSet(list(units))))
    def test_unit_registry_empty_when_no_units_ml(self):
        root = StubRoot(schema_version="3.1.0", vessel=StubVessel(), units_ml=None)
        ir = OcxV3Builder().build(root)
        assert isinstance(ir.unit_registry, dict)
        assert len(ir.unit_registry) == 0
    def test_unit_registry_populated(self):
        um  = _make_length_unit("Um",  "meter",      "m",  "meter")
        umm = _make_length_unit("Umm", "millimeter", "mm", "meter", "m")
        ir = OcxV3Builder().build(self._root_with_units(um, umm))
        assert "Um"  in ir.unit_registry
        assert "Umm" in ir.unit_registry
        assert ir.unit_registry["Umm"].to_si_factor == pytest.approx(1e-3)
    def test_unit_registry_values_are_ir_unit(self):
        um = _make_length_unit("Um", "meter", "m", "meter")
        ir = OcxV3Builder().build(self._root_with_units(um))
        for u in ir.unit_registry.values():
            assert isinstance(u, IrUnit)
    def test_real_model_vessel_has_registry(self):
        from pathlib import Path
        from ocx_model_validator.builders import get_builder
        from ocx_model_validator.parsers.load_tools import OcxParser
        model = Path("models/TR03_TC10_nast.3docx")
        if not model.exists():
            pytest.skip("Model not found")
        root = OcxParser().parse(str(model))
        ir = get_builder(root.schema_version).build(root)
        assert len(ir.unit_registry) > 0
        assert "Um"  in ir.unit_registry
        assert "Umm" in ir.unit_registry
        assert ir.unit_registry["Um"].si_symbol == "m"
        assert ir.unit_registry["Umm"].to_si_factor == pytest.approx(1e-3)
