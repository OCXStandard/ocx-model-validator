"""Tests for the bill-of-material report generator."""
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import (
    IrPlate,
    IrStiffener,
    IrVessel,
)
from ocx_model_validator.reporting.generators import bom as bom_gen

_PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    v.plates["P1"] = IrPlate(id="P1", parent_ref=_PARENT, name="P1",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             dry_weight=Quantity(1000.0, "UKg"))
    v.plates["P2"] = IrPlate(id="P2", parent_ref=_PARENT, name="P2",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             dry_weight=Quantity(500.0, "UKg"))
    v.plates["P3"] = IrPlate(id="P3", parent_ref=_PARENT, name="P3",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"))  # no weight
    v.stiffeners["ST1"] = IrStiffener(id="ST1", parent_ref=_PARENT, name="ST1",
                                      material_ref=Ref("M1"),
                                      section_ref=Ref("S1"),
                                      dry_weight=Quantity(250.0, "UKg"))
    v.plates["P4"] = IrPlate(id="P4", parent_ref=_PARENT, name="P4",
                             thickness=Quantity(12.0, "Umm"),
                             dry_weight=Quantity(2000.0, "UKg"))  # no material
    return v


def test_bom_summary_grouping_and_totals():
    report = bom_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.columns == ["Material", "Part type", "Group", "Count",
                             "Weight (t)", "Missing weight"]
    # Sorted: "(no material)" < "NV A36"
    assert table.rows == [
        ["(no material)", "Plate", "t=12.0 mm", 1, 2.0, 0],
        ["Subtotal — (no material)", None, None, 1, 2.0, 0],
        ["NV A36", "Plate", "t=10.0 mm", 3, 1.5, 1],
        ["NV A36", "Stiffener", "FB200x20", 1, 0.25, 0],
        ["Subtotal — NV A36", None, None, 4, 1.75, 1],
    ]
    assert table.footer_rows == [["Grand total", None, None, 5, 3.75, 1]]
    assert any("1 item" in n and "missing" in n for n in report.sections[0].notes)


def test_bom_summary_has_no_items_table():
    report = bom_gen.build(_vessel())
    assert [t.title for t in report.sections[0].tables] == ["Summary"]
