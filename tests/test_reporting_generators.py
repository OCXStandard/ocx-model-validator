"""Tests for report generators."""
import pytest

from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Quantity
from ocx_model_validator.model.ir.catalogues import IrHole2D, IrHoleShapeCatalogue, IrMaterial
from ocx_model_validator.model.ir.geometry import IrCoordinateSystem, IrRefPlane
from ocx_model_validator.model.ir.sections import IrFlatBarSection, IrGenericSection, IrTSection
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators import catalogues as catalogues_gen
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


def _vessel_with_catalogues() -> IrVessel:
    vessel = IrVessel(id="V1", name="MV Test")
    vessel.materials["M1"] = IrMaterial(
        id="M1", name="NV A36", grade="A36",
        density=Quantity(7850.0, ""),        # blank unit == already SI (kg/m³)
        yield_stress=Quantity(355.0, "UMPa"),
    )
    vessel.sections["S1"] = IrFlatBarSection(
        id="S1", name="FB200x20",
        height=Quantity(0.2, "Um"), width=Quantity(0.02, "Um"),
    )
    vessel.sections["S2"] = IrTSection(id="S2", name="T300")
    vessel.hole_shape_catalogue = IrHoleShapeCatalogue(
        id="H", name="Holes",
        holes={"H1": IrHole2D(id="H1", name="Manhole",
                              parametric={"length": 600, "width": 400})},
    )
    return vessel


def test_catalogues_report_all_sections():
    report = catalogues_gen.build(_vessel_with_catalogues(), source_file="m.3docx")
    assert [s.title for s in report.sections] == ["Materials", "Cross sections", "Openings"]


def test_catalogues_materials_table():
    report = catalogues_gen.build(_vessel_with_catalogues())
    table = report.sections[0].tables[0]
    assert table.columns == ["Id", "Name", "Grade", "Density (t/m³)",
                             "Yield (MPa)", "Ultimate (MPa)", "E (MPa)"]
    assert table.rows[0] == ["M1", "NV A36", "A36", 7.85, 355, None, None]


def test_catalogues_sections_table_union_columns():
    report = catalogues_gen.build(_vessel_with_catalogues())
    table = report.sections[1].tables[0]
    assert table.columns[:3] == ["Id", "Name", "Type"]
    assert "height (mm)" in table.columns
    fb_row = next(r for r in table.rows if r[0] == "S1")
    assert fb_row[table.columns.index("height (mm)")] == 200.0


def test_catalogues_filter_material_only():
    report = catalogues_gen.build(_vessel_with_catalogues(), which="material")
    assert [s.title for s in report.sections] == ["Materials"]


def test_catalogues_no_hole_catalogue():
    report = catalogues_gen.build(IrVessel(id="V1"), which="opening")
    section = report.sections[0]
    assert section.tables[0].rows == []
    assert any("hole shape catalogue" in n.lower() for n in section.notes)


def test_catalogues_generic_section_does_not_crash():
    vessel = _vessel_with_catalogues()
    vessel.sections["G1"] = IrGenericSection(id="G1", name="Gen", extra={"height": 0.2})
    report = catalogues_gen.build(vessel, which="section")
    table = report.sections[0].tables[0]
    assert "extra (mm)" not in table.columns
    g_row = next(r for r in table.rows if r[0] == "G1")
    assert g_row[1] == "Gen"


def test_catalogues_invalid_which_raises_value_error():
    with pytest.raises(ValueError, match="unknown catalogue"):
        catalogues_gen.build(IrVessel(id="V1"), which="materials")
