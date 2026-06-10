"""Smoke test: every name in ir.__all__ is importable and matches re-exports."""
from __future__ import annotations

import ocx_model_validator.model.ir as ir


def test_all_names_are_importable():
    for name in ir.__all__:
        assert hasattr(ir, name), f"{name} listed in __all__ but missing"


def test_representative_new_types_present():
    expected = [
        "IrPoint3D", "IrCurve3D", "IrLine3D", "IrSurface3D",
        "IrSeam", "IrMember", "IrEndCut", "IrFeatureCope",
        "IrLiquidCargo", "IrDesignView", "IrOccurrenceGroup",
        "IrHole2D", "IrHoleShapeCatalogue",
        "IrShipDesignation", "IrPrincipalParticulars", "IrStatutoryData",
        "IrConnectionConfiguration", "IrPenetration",
    ]
    for name in expected:
        assert hasattr(ir, name), name


def test_backward_compatible_core_imports_still_work():
    from ocx_model_validator.model.ir import (  # noqa: F401
        IrVessel,
        IrPanel,
        IrPlate,
        IrSection,
        IrMaterial,
        Quantity,
        Ref,
    )
