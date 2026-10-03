"""Tests for the bracket report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
from ocx_model_validator.model.ir.structural import (
    IrBracket,
    IrFeatureCope,
    IrPanel,
    IrVessel,
)
from ocx_model_validator.reporting.generators import brackets as brackets_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.panels["PAN1"] = IrPanel(id="PAN1", name="Deck panel",
                               bracket_ids=["BR1", "BR2"])
    v.brackets["BR1"] = IrBracket(
        id="BR1", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Tripping bracket",
        material_ref=Ref("M1", offset=Quantity(5.0, "Umm")),
        thickness=Quantity(10.0, "Umm"),
        renewal_thickness=Quantity(8.0, "Umm"),
        voluntary_thickness_addition=Quantity(1.0, "Umm"),
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(50.0, "UKg")),
        arm_length_u=Quantity(300.0, "Umm"),
        arm_length_v=Quantity(350.0, "Umm"),
        origin=IrPoint3D(x=10.0, y=2.0, z=8.0, unit="Um"),
        udirection=IrVector3D(x=1.0, y=0.0, z=0.0),
        vdirection=IrVector3D(x=0.0, y=0.0, z=1.0),
        unose=Quantity(50.0, "Umm"),
        vnose=Quantity(60.0, "Umm"),
        free_edge_radius=Quantity(400.0, "Umm"),
        has_edge_reinforcement=True,
        number_of_supports=2,
        reinforcement_type="Flanged",
        feature_cope=IrFeatureCope(
            id="FC1", name="Cope",
            cope_radius=Quantity(30.0, "Umm"),
            cope_length=Quantity(80.0, "Umm"),
            cope_height=Quantity(40.0, "Umm")),
        flange_width=Quantity(100.0, "Umm"),
        flange_radius=Quantity(25.0, "Umm"),
    )
    v.brackets["BR2"] = IrBracket(
        id="BR2", parent_ref=ParentRef(kind=ParentKind.PANEL, id="PAN1"),
        name="Bare bracket")
    return v


def test_brackets_report_shape():
    report = brackets_gen.build(_vessel(), source_file="model.3docx")
    assert report.title == "Bracket report"
    section = report.sections[0]
    assert section.title == "Brackets"
    table = section.tables[0]
    assert table.columns == [
        "Id", "Name", "Parent Panel", "Material",
        "Thickness (mm)", "Renewal thickness (mm)",
        "Voluntary addition (mm)", "Offset (mm)", "Dry weight (t)",
        "Arm length U (mm)", "Arm length V (mm)",
        "Origin (m)", "U direction", "V direction",
        "U nose (mm)", "V nose (mm)", "Free edge radius (mm)",
        "Edge reinforcement", "Supports", "Reinforcement type",
        "Cope radius (mm)", "Cope length (mm)", "Cope height (mm)",
        "Flange width (mm)", "Flange radius (mm)",
    ]


def test_brackets_rows_sorted_with_parameters():
    report = brackets_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.rows == [
        ["BR2", "Bare bracket", "Deck panel", None,
         None, None, None, None, None,
         None, None,
         None, None, None,
         None, None, None,
         None, None, None,
         None, None, None, None, None],
        ["BR1", "Tripping bracket", "Deck panel", "NV A36",
         10.0, 8.0, 1.0, 5.0, 0.05,
         300.0, 350.0,
         "(10.0, 2.0, 8.0)", "[1.0, 0.0, 0.0]", "[0.0, 0.0, 1.0]",
         50.0, 60.0, 400.0,
         "yes", 2, "Flanged",
         30.0, 80.0, 40.0, 100.0, 25.0],
    ]


def test_brackets_empty_vessel():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    report = brackets_gen.build(v)
    assert report.sections[0].tables[0].rows == []


def test_brackets_unknown_unit_noted():
    v = IrVessel(id="V1", name="Odd", schema_version="3.2.0")
    v.brackets["BR9"] = IrBracket(
        id="BR9", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"),
        name="Odd", thickness=Quantity(3.0, "Ucubit"))
    report = brackets_gen.build(v)
    assert any("BR9" in n and "Ucubit" in n for n in report.sections[0].notes)
