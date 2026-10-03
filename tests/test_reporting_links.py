"""Tests for internal cross-link emission by report generators."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import IrPlate, IrStiffener, IrVessel
from ocx_model_validator.reporting.generators import bom as bom_gen
from ocx_model_validator.reporting.generators import catalogues as catalogues_gen
from ocx_model_validator.reporting.model import Link

_PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.materials["M2"] = IrMaterial(id="M2", name="AH36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    return v


def test_materials_table_row_anchors_follow_sorted_rows():
    report = catalogues_gen.build(_vessel(), which="material")
    table = report.sections[0].tables[0]
    # rows sorted by name: AH36 (M2) before NV A36 (M1)
    assert [r[0] for r in table.rows] == ["M2", "M1"]
    assert table.row_anchors == ["material-M2", "material-M1"]


def test_sections_table_row_anchors():
    report = catalogues_gen.build(_vessel(), which="section")
    table = report.sections[0].tables[0]
    assert table.row_anchors == ["section-S1"]


def test_openings_table_has_no_anchors():
    report = catalogues_gen.build(_vessel(), which="opening")
    assert report.sections[0].tables[0].row_anchors == []


def _vessel_with_parts() -> IrVessel:
    v = _vessel()
    v.plates["P1"] = IrPlate(id="P1", parent_ref=_PARENT, name="P1",
                             material_ref=Ref("M1"),
                             thickness=Quantity(10.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(1000.0, "UKg")))
    v.stiffeners["ST1"] = IrStiffener(id="ST1", parent_ref=_PARENT, name="ST1",
                                      material_ref=Ref("M1"),
                                      section_ref=Ref("S1"),
                                      mass_properties=IrMassProperties(
                                          moulded_dry_weight=Quantity(250.0, "UKg")))
    v.plates["P2"] = IrPlate(id="P2", parent_ref=_PARENT, name="P2",
                             thickness=Quantity(12.0, "Umm"),
                             mass_properties=IrMassProperties(
                                 moulded_dry_weight=Quantity(2000.0, "UKg")))  # no material
    return v


def test_bom_material_cells_are_links():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    plate_row = next(r for r in table.rows if r[1] == "Plate" and r[2] == "t=10.0 mm")
    assert plate_row[0] == Link("NV A36", "material-M1")


def test_bom_section_group_cells_are_links():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    stiff_row = next(r for r in table.rows if r[1] == "Stiffener")
    assert stiff_row[2] == Link("FB200x20", "section-S1")


def test_bom_unresolved_material_stays_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    no_mat_row = next(r for r in table.rows if r[2] == "t=12.0 mm")
    assert no_mat_row[0] == "(no material)"


def test_bom_thickness_groups_stay_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    plate_row = next(r for r in table.rows if r[1] == "Plate" and r[2] == "t=10.0 mm")
    assert isinstance(plate_row[2], str)


def test_bom_subtotal_and_total_rows_stay_plain():
    report = bom_gen.build(_vessel_with_parts())
    table = report.sections[0].tables[0]
    subtotal = next(r for r in table.rows if isinstance(r[0], str)
                    and r[0].startswith("Subtotal"))
    assert isinstance(subtotal[0], str)
    assert table.footer_rows[0][0] == "Grand total"


def test_bom_detailed_items_are_links_too():
    report = bom_gen.build(_vessel_with_parts(), detailed=True)
    items = report.sections[0].tables[1]
    st1_row = next(r for r in items.rows if r[3] == "ST1")
    assert st1_row[0] == Link("NV A36", "material-M1")
    assert st1_row[2] == Link("FB200x20", "section-S1")
