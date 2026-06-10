"""Unit tests for cargo and design-view IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBulkCargo,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrOccurrence,
    IrOccurrenceGroup,
    IrUnitCargo,
    Quantity,
    Ref,
)


def test_liquid_cargo_fields():
    c = IrLiquidCargo(id="lc1", density=Quantity(1.025, "UKgOverm3"))
    assert c.compartment_ref is None
    assert c.density == Quantity(1.025, "UKgOverm3")
    assert c.cargo_type is None


def test_gaseous_bulk_unit_cargo_defaults():
    g = IrGaseousCargo(id="g1")
    assert g.carriage_pressure is None
    b = IrBulkCargo(id="b1", angle_of_repose=Quantity(30.0, "Udeg"))
    assert b.stowage_factor is None and b.angle_of_repose == Quantity(30.0, "Udeg")
    u = IrUnitCargo(id="u1", compartment_ref=Ref("comp1"))
    assert u.compartment_ref == Ref("comp1")


def test_occurrence_defaults():
    o = IrOccurrence(id="o1")
    assert o.definition_ref is None and o.transformation is None


def test_design_view_is_recursive_tree():
    leaf = IrOccurrence(id="o1", name="part-a")
    inner = IrOccurrenceGroup(id="g-inner", children=[leaf])
    outer = IrOccurrenceGroup(id="g-outer", children=[inner])
    view = IrDesignView(id="dv1", children=[outer])

    assert view.children[0].children[0].children[0] is leaf
    # group can hold both groups and occurrences at the same level
    mixed = IrOccurrenceGroup(id="g", children=[leaf, inner])
    assert mixed.children == [leaf, inner]


def test_design_view_children_default_empty():
    assert IrDesignView(id="dv2").children == []
    assert IrOccurrenceGroup(id="g2").children == []
