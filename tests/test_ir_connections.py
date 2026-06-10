"""Unit tests for connection placeholder IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrConnectionConfiguration,
    IrPenetration,
)


def test_connection_configuration_minimal():
    c = IrConnectionConfiguration(id="cc1")
    assert c.id == "cc1" and c.name is None


def test_penetration_is_connection_configuration_subtype():
    p = IrPenetration(id="p1", name="hole")
    assert isinstance(p, IrConnectionConfiguration)
    assert p.id == "p1" and p.name == "hole"
