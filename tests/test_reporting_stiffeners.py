"""Tests for the stiffener report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.connections import IrPenetration
from ocx_model_validator.model.ir.geometry import IrCurve3D
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import (
    IrEndCut,
    IrInclination,
    IrPanel,
    IrStiffener,
    IrVessel,
)
from ocx_model_validator.reporting.generators import stiffeners as stiffeners_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    v.panels["PAN1"] = IrPanel(id="PAN1", name="Deck panel",
                               function_type="DECK PART",
                               stiffener_ids=["ST1", "ST2"])
    v.stiffeners["ST1"] = IrStiffener(
        id="ST1", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Deck long", function_type="STIFFENER",
        material_ref=Ref("M1", offset=Quantity(5.0, "Umm")), section_ref=Ref("S1"),
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(250.0, "UKg")),
        trace=IrCurve3D(curve_length=Quantity(12.5, "Um")),
        inclinations=[IrInclination(), IrInclination()],
        penetrations=[IrPenetration(id="PEN1")],
        end_cut_end1=IrEndCut(name="EC-A"),
        end_cut_end2=IrEndCut(sniped=True),
    )
    # No own function_type → inherits the panel's, shown in parentheses
    v.stiffeners["ST2"] = IrStiffener(
        id="ST2", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Bare stiffener")
    return v


def test_stiffeners_report_shape():
    report = stiffeners_gen.build(_vessel(), source_file="model.3docx")
    assert report.title == "Stiffener report"
    section = report.sections[0]
    assert section.title == "Stiffeners"
    table = section.tables[0]
    assert table.columns == [
        "Id", "Name", "Parent Panel", "Function", "Material", "Profile",
        "Offset (mm)", "Length (m)", "Dry weight (t)", "Inclinations",
        "Penetrations", "End cut 1", "End cut 2",
    ]


def test_stiffeners_rows_sorted_with_attributes_and_counts():
    report = stiffeners_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.rows == [
        ["ST2", "Bare stiffener", "Deck panel", "(DECK PART)", None, None,
         None, None, None, 0, 0, None, None],
        ["ST1", "Deck long", "Deck panel", "STIFFENER", "NV A36", "FB200x20",
         5.0, 12.5, 0.25, 2, 1, "EC-A", "sniped"],
    ]


def test_stiffeners_empty_vessel():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    report = stiffeners_gen.build(v)
    assert report.sections[0].tables[0].rows == []


def test_stiffeners_unknown_length_unit_noted():
    v = _vessel()
    v.stiffeners["ST9"] = IrStiffener(
        id="ST9", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"),
        name="Odd", trace=IrCurve3D(curve_length=Quantity(3.0, "Ucubit")))
    report = stiffeners_gen.build(v)
    assert any("ST9" in n and "Ucubit" in n for n in report.sections[0].notes)
