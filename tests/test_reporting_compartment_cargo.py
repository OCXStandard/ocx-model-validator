"""Tests for cargo information in the compartments report."""
from ocx_model_validator.model.ir.arrangement import (
    IrBulkCargo,
    IrCompartment,
    IrGaseousCargo,
    IrLiquidCargo,
    IrUnitCargo,
)
from ocx_model_validator.model.ir.base import Quantity, Ref
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators import compartments as compartments_gen


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.2.0")
    v.compartments["C1"] = IrCompartment(
        id="C1", name="No.1 Cargo Tank", compartment_purpose="cargo")
    v.compartments["C2"] = IrCompartment(
        id="C2", name="No.2 Hold", compartment_purpose="cargo")
    v.liquid_cargoes["C1/liquid/0"] = IrLiquidCargo(
        id="C1/liquid/0", compartment_ref=Ref("C1"),
        cargo_type="Crude Oil",
        density=Quantity(850.0, ""),
        carriage_pressure=Quantity(200000.0, "UPa"))
    v.gaseous_cargoes["C1/gas/0"] = IrGaseousCargo(
        id="C1/gas/0", compartment_ref=Ref("C1"),
        cargo_type="LNG", liquid_state=True)
    v.bulk_cargoes["C2/bulk/0"] = IrBulkCargo(
        id="C2/bulk/0", compartment_ref=Ref("C2"),
        cargo_type="Iron Ore",
        density=Quantity(2500.0, ""),
        stowage_factor=Quantity(0.4, "Um3PerKg"),
        permeability=Quantity(0.3, ""),
        angle_of_repose=Quantity(35.0, "Udeg"))
    v.unit_cargoes["C2/unit/0"] = IrUnitCargo(
        id="C2/unit/0", compartment_ref=Ref("C2"), cargo_type="Container")
    return v


def test_compartments_table_has_cargo_type_column():
    report = compartments_gen.build(_vessel(), source_file="m.3docx")
    table = report.sections[0].tables[0]
    assert table.columns[:3] == ["Name", "Tank type", "Cargo type"]
    rows = {r[0]: r for r in table.rows}
    assert rows["No.1 Cargo Tank"][2] == "Crude Oil, LNG"
    assert rows["No.2 Hold"][2] == "Iron Ore, Container"


def test_cargoes_table_shape_and_rows():
    report = compartments_gen.build(_vessel(), source_file="m.3docx")
    section = report.sections[0]
    cargo_table = section.tables[1]
    assert cargo_table.title == "Cargoes"
    assert cargo_table.columns == [
        "Compartment", "Kind", "Cargo type", "Density (t/m³)",
        "Carriage pressure (kPa)", "Liquid state", "Stowage factor",
        "Permeability", "Angle of repose",
    ]
    assert cargo_table.rows == [
        ["No.1 Cargo Tank", "Liquid", "Crude Oil", 0.85, 200.0,
         None, None, None, None],
        ["No.1 Cargo Tank", "Gaseous", "LNG", None, None,
         "yes", None, None, None],
        ["No.2 Hold", "Bulk", "Iron Ore", 2.5, None,
         None, "0.4 Um3PerKg", 0.3, "35.0 Udeg"],
        ["No.2 Hold", "Unit", "Container", None, None,
         None, None, None, None],
    ]


def test_no_cargoes_gives_empty_cargo_table():
    v = IrVessel(id="V1", name="Empty", schema_version="3.2.0")
    v.compartments["C1"] = IrCompartment(
        id="C1", name="Void", compartment_purpose="void")
    report = compartments_gen.build(v)
    table = report.sections[0].tables[0]
    rows = {r[0]: r for r in table.rows}
    assert rows["Void"][2] is None
    assert report.sections[0].tables[1].rows == []
