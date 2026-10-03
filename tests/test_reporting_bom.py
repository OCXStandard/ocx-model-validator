"""Tests for the bill-of-material report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import (
    IrPillar,
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
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(1000.0, "UKg")))
    v.plates["P2"] = IrPlate(id="P2", parent_ref=_PARENT, name="P2",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(500.0, "UKg")))
    v.plates["P3"] = IrPlate(id="P3", parent_ref=_PARENT, name="P3",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"))  # no weight
    v.stiffeners["ST1"] = IrStiffener(id="ST1", parent_ref=_PARENT, name="ST1",
                                      material_ref=Ref("M1"),
                                      section_ref=Ref("S1"),
                                      mass_properties=IrMassProperties(
                                          moulded_dry_weight=Quantity(250.0, "UKg")))
    v.pillars["PI1"] = IrPillar(id="PI1", parent_ref=_PARENT, name="PI1",
                                material_ref=Ref("M1"),
                                section_ref=Ref("S1"),
                                mass_properties=IrMassProperties(
                                    moulded_dry_weight=Quantity(300.0, "UKg")))
    v.plates["P4"] = IrPlate(id="P4", parent_ref=_PARENT, name="P4",
                             thickness=Quantity(12.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(2000.0, "UKg")))  # no material
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
        ["NV A36", "Pillar", "FB200x20", 1, 0.3, 0],
        ["NV A36", "Plate", "t=10.0 mm", 3, 1.5, 1],
        ["NV A36", "Stiffener", "FB200x20", 1, 0.25, 0],
        ["Subtotal — NV A36", None, None, 5, 2.05, 1],
    ]
    assert table.footer_rows == [["Grand total", None, None, 6, 4.05, 1]]
    assert any("1 item" in n and "missing" in n for n in report.sections[0].notes)


def test_bom_summary_has_no_items_table():
    report = bom_gen.build(_vessel())
    assert [t.title for t in report.sections[0].tables] == ["Summary"]


def test_bom_unknown_thickness_unit_group_key():
    v = _vessel()
    v.plates["P5"] = IrPlate(id="P5", parent_ref=_PARENT, name="P5",
                             material_ref=Ref("M1"),
                             thickness=Quantity(12.5, "Ubogus"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(100.0, "UKg")))
    report = bom_gen.build(v)
    table = report.sections[0].tables[0]
    keys = [r[2] for r in table.rows]
    assert "t=12.5 Ubogus" in keys
    assert not any(isinstance(k, str) and k.endswith("Ubogus mm") for k in keys)


def test_bom_unknown_weight_unit_is_noted():
    v = _vessel()
    v.plates["P6"] = IrPlate(id="P6", parent_ref=_PARENT, name="P6",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(3.0, "Ustone")))
    report = bom_gen.build(v)
    notes = report.sections[0].notes
    assert any("P6" in n and "Ustone" in n for n in notes)


def test_bom_notes_deduplicated():
    v = _vessel()
    for i in (7, 8):
        v.plates[f"P{i}"] = IrPlate(id=f"P{i}", parent_ref=_PARENT, name=f"P{i}",
                                    material_ref=Ref("M1"),
                                    thickness=Quantity(12.5, "Ubogus"),
                                    mass_properties=IrMassProperties(
                                        moulded_dry_weight=Quantity(100.0, "UKg")))
    report = bom_gen.build(v)
    notes = report.sections[0].notes
    assert len(notes) == len(set(notes))


def test_bom_detailed_items_table():
    report = bom_gen.build(_vessel(), detailed=True)
    tables = report.sections[0].tables
    assert [t.title for t in tables] == ["Summary", "Items"]
    items = tables[1]
    assert items.columns == ["Material", "Part type", "Group", "Id", "Name", "Weight (t)"]
    p3_row = next(r for r in items.rows if r[3] == "P3")
    assert p3_row[5] is None  # missing weight renders None


def test_bom_detailed_item_count():
    report = bom_gen.build(_vessel(), detailed=True)
    assert len(report.sections[0].tables[1].rows) == 6
