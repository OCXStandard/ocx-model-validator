"""Builder dual-path tests: OCX 3.2.0 names first, 3.1.0 fallback."""
from __future__ import annotations

from types import SimpleNamespace as NS

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import ParentKind, ParentRef

PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _b() -> OcxV3Builder:
    return OcxV3Builder()


def _qty(value, unit):
    return NS(numericvalue=value, unit=unit)


def _cog(x, y, z, unit="Um"):
    return NS(coordinates=[x, y, z], unit=unit)


def test_mass_properties_from_320_element():
    raw = NS(mass_properties=NS(
        moulded_dry_weight=_qty(1200.0, "UKg"),
        physical_dry_weight=_qty(1250.0, "UKg"),
        moulded_center_of_gravity=_cog(1.0, 2.0, 3.0),
        physical_center_of_gravity=_cog(1.1, 2.1, 3.1),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 1200.0
    assert mp.physical_dry_weight.value == 1250.0
    assert mp.moulded_cog.x == 1.0
    assert mp.physical_cog.z == 3.1


def test_mass_properties_falls_back_to_physical_properties():
    raw = NS(physical_properties=NS(
        dry_weight=_qty(300.0, "UKg"),
        center_of_gravity=_cog(5.0, 6.0, 7.0),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 300.0
    assert mp.moulded_cog.y == 6.0
    assert mp.physical_dry_weight is None
    assert mp.physical_cog is None


def test_mass_properties_absent_returns_none():
    assert _b()._mass_properties(NS()) is None


def test_build_plate_populates_mass_properties():
    raw = NS(id="PL1", name="p", guidref=None, plate_material=None,
             net_area=None, function_type=None, outer_contour=None,
             mass_properties=NS(
                 moulded_dry_weight=_qty(42.0, "UKg"),
                 physical_dry_weight=None,
                 moulded_center_of_gravity=None,
                 physical_center_of_gravity=None))
    plate = _b()._build_plate(raw, PARENT)
    assert plate.mass_properties.moulded_dry_weight.value == 42.0
