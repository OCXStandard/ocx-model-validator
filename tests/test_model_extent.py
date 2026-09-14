from __future__ import annotations

from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators.model_extent import extent_mm

from .section_fixtures import make_synthetic_vessel


def test_extent_mm_returns_bounding_box():
    vessel = make_synthetic_vessel()

    extent = extent_mm(vessel)

    assert extent is not None
    for key in ("min_x", "max_x", "min_y", "max_y", "min_z", "max_z"):
        assert key in extent
        assert isinstance(extent[key], float)

    assert extent["min_x"] <= extent["max_x"]
    assert extent["min_y"] <= extent["max_y"]
    assert extent["min_z"] <= extent["max_z"]

    # Points are gathered in mm; smallest x-coordinate comes from stiffener
    # traces starting at x=0.0 m, largest from the line() traces of
    # stiff-a1/stiff-a2/stiff-b1, which end at the default x=10.0 m.
    assert extent["min_x"] == 0.0
    assert extent["max_x"] == 10000.0


def test_extent_mm_returns_none_for_empty_vessel():
    vessel = IrVessel(id="empty-vessel")

    assert extent_mm(vessel) is None
