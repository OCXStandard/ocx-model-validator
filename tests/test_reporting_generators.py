"""Tests for report generators."""
import pytest

from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, Quantity
from ocx_model_validator.model.ir.catalogues import IrHole2D, IrHoleShapeCatalogue, IrMaterial
from ocx_model_validator.model.ir.geometry import IrCoordinateSystem, IrRefPlane
from ocx_model_validator.model.ir.sections import (
    IrBulbFlatSection,
    IrFlatBarSection,
    IrGenericSection,
    IrTSection,
)
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
        rp = IrRefPlane(id=f"FR{i}", name=f"FR{i}", location=Quantity(x, "Um"),
                        display_grid=True)
        vessel.ref_planes[rp.id] = rp
        frame_ids.append(rp.id)
    aux = IrRefPlane(id="AUX", name="AUX", location=Quantity(1.2, "Um"),
                     display_grid=False)
    vessel.ref_planes[aux.id] = aux
    frame_ids.append(aux.id)
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
    assert positions.columns == ["#", "Frame", "Name", "x (mm)", "Display grid"]
    # counter numbers grid frames only; displayGrid=false rows get no number
    assert positions.rows == [[1, "FR0", "FR0", 0.0, "yes"],
                              [2, "FR1", "FR1", 800.0, "yes"],
                              ["", "AUX", "AUX", 1200.0, "no"],
                              [3, "FR2", "FR2", 1600.0, "yes"]]


def test_frame_table_spacing_only_from_display_grid_planes():
    report = frame_table_gen.build(_vessel_with_frames(), source_file="m.3docx")
    spacing = report.sections[0].tables[0]
    assert spacing.columns == ["From frame", "Name", "x (mm)", "Spacing (mm)"]
    # AUX (displayGrid=false) must not affect the grid spacing
    assert spacing.rows == [["FR0", "FR0", 0.0, 800.0]]


def test_frame_table_offset_names_frame():
    report = frame_table_gen.build(_vessel_with_frames(), source_file="m.3docx")
    intro = report.sections[0].intro
    assert "0.0 mm" in intro
    assert "FR0" in intro
    # frame count includes only grid frames (AUX excluded)
    assert "3 frames" in intro


def test_frame_table_missing_display_grid_defaults_to_yes():
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    for i, x in enumerate([0.0, 0.8]):
        rp = IrRefPlane(id=f"FR{i}", name=f"FR{i}", location=Quantity(x, "Um"))
        vessel.ref_planes[rp.id] = rp
    vessel.coordinate_systems["CS1"] = IrCoordinateSystem(
        id="CS1", is_global=True, x_ref_plane_ids=["FR0", "FR1"],
    )
    report = frame_table_gen.build(vessel, source_file="m.3docx")
    section = report.sections[0]
    positions = section.tables[1]
    assert positions.rows == [[1, "FR0", "FR0", 0.0, "yes"],
                              [2, "FR1", "FR1", 800.0, "yes"]]
    assert "2 frames" in section.intro


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


def test_catalogues_bulb_angle_rendered_in_degrees():
    vessel = _vessel_with_catalogues()
    vessel.sections["S3"] = IrBulbFlatSection(
        id="S3", name="HP200x10",
        height=Quantity(0.2, "Um"),
        bulb_angle=Quantity(15.0, "Udeg"),
    )
    report = catalogues_gen.build(vessel, which="section")
    table = report.sections[0].tables[0]
    assert "bulb_angle (mm)" not in table.columns
    assert "bulb_angle (deg)" in table.columns
    hp_row = next(r for r in table.rows if r[0] == "S3")
    assert hp_row[table.columns.index("bulb_angle (deg)")] == 15.0


def test_catalogues_bulb_angle_unknown_unit_noted():
    vessel = IrVessel(id="V1")
    vessel.sections["S3"] = IrBulbFlatSection(
        id="S3", name="HP200x10",
        bulb_angle=Quantity(0.26, "Ugon"),
    )
    report = catalogues_gen.build(vessel, which="section")
    section = report.sections[0]
    hp_row = section.tables[0].rows[0]
    idx = section.tables[0].columns.index("bulb_angle (deg)")
    assert hp_row[idx] == "0.26 Ugon"
    assert any("bulb_angle" in n for n in section.notes)


def test_catalogues_invalid_which_raises_value_error():
    with pytest.raises(ValueError, match="unknown catalogue"):
        catalogues_gen.build(IrVessel(id="V1"), which="materials")


def test_compartments_report_includes_compartment_properties():
    vessel = IrVessel(id="V1", name="MV Test")
    vessel.compartments["C1"] = IrCompartment(
        id="C1", name="WB Tank 1", compartment_purpose="ballast",
        volume=Quantity(120.0, "Um3"), cog=IrCog(10.0, 0.0, 2.0, "Um"),
        filling_height=Quantity(9.0, "Um"),
        air_pipe_height=Quantity(10.5, "Um"),
        relief_valve_pressure=Quantity(25000.0, "UPa"),
    )
    report = compartments_gen.build(vessel, source_file="m.3docx")
    table = report.sections[0].tables[0]
    idx_fh = table.columns.index("Filling height (mm)")
    idx_ap = table.columns.index("Air pipe height (mm)")
    idx_rv = table.columns.index("Relief valve pressure (kPa)")
    row = table.rows[0]
    assert row[idx_fh] == 9000.0
    assert row[idx_ap] == 10500.0
    assert row[idx_rv] == 25.0


def _vessel_with_frames_and_compartment() -> IrVessel:
    from ocx_model_validator.model.ir.geometry import IrLine3D, IrPoint3D

    vessel = _vessel_with_frames()  # grid frames FR0/FR1/FR2 at 0/800/1600 mm
    vessel.compartments["C1"] = IrCompartment(
        id="C1", name="Tank 1", compartment_purpose="void",
        face_boundary_curves=[
            IrLine3D(curve_length=None,
                     start=IrPoint3D(1.0, -3.0, 0.5, "Um"),
                     end=IrPoint3D(1.6, 3.0, 2.5, "Um")),
        ],
    )
    return vessel


def test_compartment_extent_x_shown_as_frame_position():
    report = compartments_gen.build(_vessel_with_frames_and_compartment(),
                                    source_file="m.3docx")
    table = report.sections[0].tables[0]
    row = table.rows[0]
    idx_min = table.columns.index("min x (frame)")
    idx_max = table.columns.index("max x (frame)")
    # 1000 mm is 200 mm beyond FR1 (800); 1600 mm is exactly FR2
    assert row[idx_min] == "#FR1+200"
    assert row[idx_max] == "#FR2"


def test_compartment_extent_x_falls_back_to_mm_without_frame_table():
    vessel = IrVessel(id="V1", name="MV Test")
    from ocx_model_validator.model.ir.geometry import IrLine3D, IrPoint3D
    vessel.compartments["C1"] = IrCompartment(
        id="C1", name="Tank 1", compartment_purpose="void",
        face_boundary_curves=[
            IrLine3D(curve_length=None,
                     start=IrPoint3D(1.0, 0.0, 0.0, "Um"),
                     end=IrPoint3D(2.0, 1.0, 1.0, "Um")),
        ],
    )
    report = compartments_gen.build(vessel, source_file="m.3docx")
    table = report.sections[0].tables[0]
    row = table.rows[0]
    assert row[table.columns.index("min x (frame)")] == 1000.0
    assert row[table.columns.index("max x (frame)")] == 2000.0
