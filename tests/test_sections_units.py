"""sections.units: Quantity/point conversion to mm / MPa / m3."""
import pytest

from ocx_model_validator.exeptions import GeometryError, OcxParserError, SectionError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
from ocx_model_validator.model.ir.geometry import IrPoint3D
from ocx_model_validator.sections.units import point_mm, qty_m3, qty_mm, qty_mpa, to_si

REGISTRY = {
    "Um": IrUnit(
        id="Um", name="meter", symbol="m", dimension_url="D_L", to_si_factor=1.0, si_symbol="m"
    ),
    "Umm": IrUnit(
        id="Umm", name="millimeter", symbol="mm", dimension_url="D_L", to_si_factor=0.001, si_symbol="m"
    ),
}


def test_exceptions_subclass_parser_error():
    assert issubclass(GeometryError, OcxParserError)
    assert issubclass(SectionError, OcxParserError)


def test_to_si_uses_registry():
    assert to_si(Quantity(59.2, "Um"), REGISTRY) == pytest.approx(59.2)
    assert to_si(Quantity(500.0, "Umm"), REGISTRY) == pytest.approx(0.5)


def test_to_si_fallback_without_registry():
    assert to_si(Quantity(2.0, "Um"), {}) == pytest.approx(2.0)
    assert to_si(Quantity(15.0, "Umm"), {}) == pytest.approx(0.015)
    assert to_si(Quantity(3.0, ""), {}) == pytest.approx(3.0)  # blank = SI


def test_to_si_unknown_unit_raises():
    with pytest.raises(GeometryError):
        to_si(Quantity(1.0, "Ufurlong"), REGISTRY)


def test_qty_mm_mpa_m3():
    assert qty_mm(Quantity(59.2, "Um"), REGISTRY) == pytest.approx(59200.0)
    assert qty_mm(None, REGISTRY) is None
    assert qty_mpa(Quantity(315e6, "UPa"), {}) == pytest.approx(315.0)
    assert qty_m3(Quantity(1000.0, "Um3"), {}) == pytest.approx(1000.0)


def test_point_mm():
    p = IrPoint3D(x=1.0, y=2.0, z=3.0, unit="Um")
    assert point_mm(p, REGISTRY) == pytest.approx((1000.0, 2000.0, 3000.0))
