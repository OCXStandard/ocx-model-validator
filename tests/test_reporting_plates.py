"""Tests for the plate report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import IrPoint3D
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrVessel
from ocx_model_validator.reporting.generators import plates as plates_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.panels["PAN1"] = IrPanel(id="PAN1", name="Deck panel",
                               function_type="DECK PART",
                               plate_ids=["P1", "P2"])
    v.plates["P1"] = IrPlate(
        id="P1", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Deck plate", function_type="DECK",
        material_ref=Ref("M1", offset=Quantity(5.0, "Umm")),
        thickness=Quantity(10.0, "Umm"),
        renewal_thickness=Quantity(8.0, "Umm"),
        voluntary_thickness_addition=Quantity(1.0, "Umm"),
        net_area=Quantity(12.5, "Um2"),
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(1000.0, "UKg")),
        point_on_surface=IrPoint3D(x=10.0, y=0.5, z=8.0, unit="Um"),
        cut_by_contours=[object(), object()],
    )
    v.plates["P0"] = IrPlate(
        id="P0", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"),
        name="Bare plate")
    # No own function_type → inherits the panel's, shown in parentheses
    v.plates["P2"] = IrPlate(
        id="P2", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Inner plate")
    return v


def test_plates_report_shape():
    report = plates_gen.build(_vessel(), source_file="model.3docx")
    assert report.title == "Plate report"
    section = report.sections[0]
    assert section.title == "Plates"
    table = section.tables[0]
    assert table.columns == [
        "Id", "Name", "Parent Panel", "Function", "Material",
        "Thickness (mm)", "Renewal thickness (mm)",
        "Voluntary addition (mm)", "Offset (mm)", "Net area (m²)",
        "Dry weight (t)", "Point on surface (m)", "Openings",
    ]


def test_plates_rows_sorted_with_attributes_and_counts():
    report = plates_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.rows == [
        ["P0", "Bare plate", None, None, None,
         None, None, None, None, None, None, None, 0],
        ["P1", "Deck plate", "Deck panel", "DECK", "NV A36",
         10.0, 8.0, 1.0, 5.0, 12.5, 1.0, "(10.0, 0.5, 8.0)", 2],
        ["P2", "Inner plate", "Deck panel", "(DECK PART)", None,
         None, None, None, None, None, None, None, 0],
    ]


def test_plates_empty_vessel():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    report = plates_gen.build(v)
    assert report.sections[0].tables[0].rows == []


def test_plates_unknown_thickness_unit_noted():
    v = _vessel()
    v.plates["P9"] = IrPlate(
        id="P9", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"),
        name="Odd", thickness=Quantity(3.0, "Ucubit"))
    report = plates_gen.build(v)
    assert any("P9" in n and "Ucubit" in n for n in report.sections[0].notes)
