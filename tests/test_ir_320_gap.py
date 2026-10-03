"""Tests for OCX 3.2.0 IR gap closure additions."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrCog,
    IrMassProperties,
    IrVector3D,
    Quantity,
    Ref,
)


def test_mass_properties_defaults():
    mp = IrMassProperties()
    assert mp.moulded_dry_weight is None
    assert mp.physical_dry_weight is None
    assert mp.moulded_cog is None
    assert mp.physical_cog is None


def test_mass_properties_populated():
    mp = IrMassProperties(
        moulded_dry_weight=Quantity(1000.0, "UKg"),
        moulded_cog=IrCog(1.0, 2.0, 3.0, "Um"),
    )
    assert mp.moulded_dry_weight.value == 1000.0
    assert mp.moulded_cog.z == 3.0


def test_ref_offset_defaults_and_population():
    r = Ref(local_ref="x1")
    assert r.offset is None and r.offset_direction is None
    r2 = Ref(local_ref="x2", offset=Quantity(5.0, "Umm"),
             offset_direction=IrVector3D(0.0, 0.0, 1.0))
    assert r2.offset.value == 5.0
    assert r2.offset_direction.z == 1.0


def test_vector3d_importable_from_base_and_geometry():
    from ocx_model_validator.model.ir.base import IrVector3D as V1
    from ocx_model_validator.model.ir.geometry import IrVector3D as V2
    assert V1 is V2
