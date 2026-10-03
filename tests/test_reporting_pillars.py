"""Tests for the pillar report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.connections import IrPenetration
from ocx_model_validator.model.ir.geometry import IrCurve3D
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import (
    IrInclination,
    IrPanel,
    IrPillar,
    IrVessel,
)
from ocx_model_validator.reporting.generators import pillars as pillars_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    v.panels["PAN1"] = IrPanel(id="PAN1", name="Deck panel",
                               function_type="DECK PART",
                               pillar_ids=["PIL1"])
    v.pillars["PIL1"] = IrPillar(
        id="PIL1", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Hold pillar", function_type="PILLAR",
        material_ref=Ref("M1", offset=Quantity(5.0, "Umm")),
        section_ref=Ref("S1"),
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(500.0, "UKg")),
        trace=IrCurve3D(curve_length=Quantity(4.5, "Um")),
        inclinations=[IrInclination()],
        penetrations=[IrPenetration(id="PEN1")],
    )
    # No own function_type → inherits the panel's, shown in parentheses
    v.pillars["PIL2"] = IrPillar(
        id="PIL2", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Bare pillar")
    return v


def test_pillars_report_shape():
    report = pillars_gen.build(_vessel(), source_file="model.3docx")
    assert report.title == "Pillar report"
    section = report.sections[0]
    assert section.title == "Pillars"
    table = section.tables[0]
    assert table.columns == [
        "Id", "Name", "Parent Panel", "Function", "Material", "Profile",
        "Offset (mm)", "Length (m)", "Dry weight (t)", "Inclinations",
        "Penetrations",
    ]


def test_pillars_rows_sorted_with_attributes_and_counts():
    report = pillars_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.rows == [
        ["PIL2", "Bare pillar", "Deck panel", "(DECK PART)", None, None,
         None, None, None, 0, 0],
        ["PIL1", "Hold pillar", "Deck panel", "PILLAR", "NV A36", "FB200x20",
         5.0, 4.5, 0.5, 1, 1],
    ]


def test_pillars_empty_vessel():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    report = pillars_gen.build(v)
    assert report.sections[0].tables[0].rows == []


def test_pillars_unknown_length_unit_noted():
    v = IrVessel(id="V1", name="Odd", schema_version="3.2.0")
    v.pillars["PIL9"] = IrPillar(
        id="PIL9", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"),
        name="Odd", trace=IrCurve3D(curve_length=Quantity(3.0, "Ucubit")))
    report = pillars_gen.build(v)
    assert any("PIL9" in n and "Ucubit" in n for n in report.sections[0].notes)
