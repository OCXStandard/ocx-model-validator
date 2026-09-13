"""Tests for report generators."""
from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Quantity
from ocx_model_validator.model.ir.geometry import IrCoordinateSystem, IrRefPlane
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators import compartments as compartments_gen
from ocx_model_validator.reporting.generators import frame_table as frame_table_gen
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_mpa_cell,
    qty_tonnes_cell,
    report_metadata,
)


def test_qty_mm_cell_converts():
    notes: list[str] = []
    assert qty_mm_cell(Quantity(0.5, "Um"), {}, notes, "x") == 500.0
    assert notes == []


def test_qty_cell_none_passthrough():
    notes: list[str] = []
    assert qty_mm_cell(None, {}, notes, "x") is None
    assert notes == []


def test_qty_cell_unknown_unit_falls_back_to_raw():
    notes: list[str] = []
    cell = qty_mm_cell(Quantity(12.5, "Ubogus"), {}, notes, "plate P1 thickness")
    assert cell == "12.5 Ubogus"
    assert notes == ["plate P1 thickness: unknown unit 'Ubogus'; raw value shown"]


def test_qty_mpa_cell_is_integer():
    notes: list[str] = []
    assert qty_mpa_cell(Quantity(235.0, "UMPa"), {}, notes, "x") == 235


def test_qty_tonnes_cell():
    notes: list[str] = []
    assert qty_tonnes_cell(Quantity(1500.0, "UKg"), {}, notes, "x") == 1.5


def test_report_metadata():
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    md = report_metadata(vessel, "model.3docx")
    assert md["Vessel"] == "MV Test"
    assert md["Schema version"] == "3.1.0"
    assert md["Source"] == "model.3docx"
    assert "Generated" in md


def _vessel_with_frames() -> IrVessel:
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    frame_ids: list[str] = []
    for i, x in enumerate([0.0, 0.8, 1.6]):
        rp = IrRefPlane(id=f"FR{i}", name=f"FR{i}", location=Quantity(x, "Um"))
        vessel.ref_planes[rp.id] = rp
        frame_ids.append(rp.id)
    vessel.coordinate_systems["CS1"] = IrCoordinateSystem(
        id="CS1",
        is_global=True,
        x_ref_plane_ids=frame_ids,
    )
    return vessel


def test_frame_table_report():
    report = frame_table_gen.build(_vessel_with_frames(), source_file="m.3docx")
    assert report.title == "Frame table report"
    section = report.sections[0]
    titles = [t.title for t in section.tables]
    assert titles == ["Spacing entries", "Frame positions"]
    positions = section.tables[1]
    assert positions.columns == ["Frame", "x (mm)"]
    assert positions.rows == [["FR0", 0.0], ["FR1", 800.0], ["FR2", 1600.0]]


def test_frame_table_report_empty_model():
    report = frame_table_gen.build(IrVessel(id="V1"), source_file="m.3docx")
    section = report.sections[0]
    assert section.tables[0].rows == []
    assert any("reference planes" in n for n in section.notes)


def test_frame_table_report_unknown_unit_degrades():
    """Test that unknown ref-plane units degrade gracefully instead of raising."""
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    # Create a ref plane with unknown unit "Uft"
    rp = IrRefPlane(id="FR0", name="FR0", location=Quantity(0.0, "Uft"))
    vessel.ref_planes[rp.id] = rp
    # Register in a global coordinate system exactly like _vessel_with_frames does
    vessel.coordinate_systems["CS1"] = IrCoordinateSystem(
        id="CS1",
        is_global=True,
        x_ref_plane_ids=["FR0"],
    )
    # Should not raise; instead gracefully degrade and capture error in notes
    report = frame_table_gen.build(vessel, source_file="m.3docx")
    section = report.sections[0]
    assert section.tables[0].rows == []
    assert section.notes  # error captured as note, not raised


def test_compartments_report():
    vessel = IrVessel(id="V1", name="MV Test")
    vessel.compartments["C1"] = IrCompartment(
        id="C1", name="WB Tank 1", compartment_purpose="ballast",
        volume=Quantity(120.0, "Um3"), cog=IrCog(10.0, 0.0, 2.0, "Um"),
    )
    report = compartments_gen.build(vessel, source_file="m.3docx")
    table = report.sections[0].tables[0]
    assert table.columns[:4] == ["Name", "Tank type", "Volume (m³)", "COG x (mm)"]
    row = table.rows[0]
    assert row[0] == "WB Tank 1"
    assert row[1] == "BALLASTWATERTANK"
    assert row[2] == 120.0
    assert row[3] == 10000.0


def test_compartments_report_empty():
    report = compartments_gen.build(IrVessel(id="V1"), source_file="m.3docx")
    assert report.sections[0].tables[0].rows == []
