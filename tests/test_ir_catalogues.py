"""Unit tests for hole-shape catalogue IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrCircle3D,
    IrHole2D,
    IrHoleShapeCatalogue,
    Quantity,
)


def test_hole2d_defaults():
    h = IrHole2D(id="h1")
    assert h.name is None and h.guidref is None and h.contour is None


def test_hole2d_holds_contour_curve():
    contour = IrCircle3D(curve_length=Quantity(1.0, "Um"))
    h = IrHole2D(id="h2", contour=contour)
    assert h.contour is contour


def test_hole_shape_catalogue_defaults_and_population():
    cat = IrHoleShapeCatalogue(id="cat1")
    assert cat.name is None and cat.holes == {}
    cat.holes["h1"] = IrHole2D(id="h1")
    assert cat.holes["h1"].id == "h1"
