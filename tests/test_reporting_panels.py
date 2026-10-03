"""Tests for the panel report generator."""
from ocx_model_validator.model.ir import IrMassProperties
from ocx_model_validator.model.ir.base import IrCog, Quantity, Ref
from ocx_model_validator.model.ir.structural import IrLimitedByRef, IrPanel, IrVessel
from ocx_model_validator.reporting.generators import panels as panels_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.panels["PAN1"] = IrPanel(
        id="PAN1", name="Deck panel",
        function_type="DECK", tightness="WaterTight",
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(2000.0, "UKg"),
            moulded_cog=IrCog(x=10.0, y=0.5, z=8.0, unit="Um")),
        plate_ids=["P1", "P2"],
        stiffener_ids=["ST1", "ST2", "ST3"],
        seam_ids=["SM1"],
        edge_reinforcement_ids=["ER1"],
        hole_shape_refs=[Ref("H1"), Ref("H2")],
        limited_by=[
            IrLimitedByRef(ref_type="PanelRef", local_ref="PAN2"),
            IrLimitedByRef(ref_type="GridRef", local_ref="G1"),
        ],
    )
    v.panels["PAN0"] = IrPanel(id="PAN0", name="Aft panel")
    return v


def test_panels_report_shape():
    report = panels_gen.build(_vessel(), source_file="model.3docx")
    assert report.title == "Panel report"
    section = report.sections[0]
    assert section.title == "Panels"
    table = section.tables[0]
    assert table.columns == [
        "Id", "Name", "Function", "Tightness", "Dry weight (t)",
        "COG x (m)", "COG y (m)", "COG z (m)", "LimitedBy",
        "Stiffeners", "Plates", "Seams", "Edge reinforcements", "Openings",
    ]


def test_panels_rows_sorted_with_attributes_and_counts():
    report = panels_gen.build(_vessel())
    table = report.sections[0].tables[0]
    assert table.rows == [
        ["PAN0", "Aft panel", None, None, None,
         None, None, None, 0, 0, 0, 0, 0, 0],
        ["PAN1", "Deck panel", "DECK", "WaterTight", 2.0,
         10.0, 0.5, 8.0, 2, 3, 2, 1, 1, 2],
    ]


def test_panels_empty_vessel():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    report = panels_gen.build(v)
    assert report.sections[0].tables[0].rows == []


def test_panels_unknown_weight_unit_noted():
    v = _vessel()
    v.panels["PAN9"] = IrPanel(
        id="PAN9", name="Odd",
        mass_properties=IrMassProperties(
            moulded_dry_weight=Quantity(3.0, "Ustone")))
    report = panels_gen.build(v)
    assert any("PAN9" in n and "Ustone" in n for n in report.sections[0].notes)
