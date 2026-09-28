"""SVG renderer for cross-section documents."""
import xml.etree.ElementTree as ET

from ocx_model_validator.sections.svg_plot import _PALETTE, _UNKNOWN_COLOR, render_svg


def _doc(plates=None, stiffeners=None, x_mm=50_000.0, frame="FR20"):
    return {
        "schema": "nh-cross-section/4",
        "source": {"file": "ship.3docx", "vessel_id": "V1", "generated": "t"},
        "cross_section": {
            "x_mm": x_mm,
            "frame": frame,
            "stiffeners": stiffeners or [],
            "plates": plates or [],
        },
        "compartments": [],
        "warnings": [],
    }


def _plate(name="P1", thickness=12.5, y1=0.0, z1=0.0, y2=10_000.0, z2=0.0):
    return {"name": name, "y1_mm": y1, "z1_mm": z1, "y2_mm": y2, "z2_mm": z2,
            "thickness_mm": thickness, "material_reh_mpa": None, "panel": None}


def _stiffener(name="L1", y=2_000.0, z=0.0, wdy=0.0, wdz=1.0,
               profile_type="FlatBar", profile_dimensions="200 x 20"):
    return {"name": name, "y_mm": y, "z_mm": z, "panel": None,
            "profile_type": profile_type, "profile_dimensions": profile_dimensions,
            "material_reh_mpa": None, "spacing_mm": None,
            "orientation": "Longitudinal", "web_angle_deg": 90.0,
            "web_dir_y": wdy, "web_dir_z": wdz}


def test_svg_is_well_formed_xml_with_title():
    svg = render_svg(_doc(plates=[_plate()]))
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "Cross section at x=50000.0 mm (frame FR20)" in svg
    assert "ship.3docx" in svg


def test_plate_lines_color_coded_by_thickness():
    svg = render_svg(_doc(plates=[
        _plate(name="A", thickness=10.0, z1=0.0, z2=0.0),
        _plate(name="B", thickness=15.0, y1=0.0, z1=0.0, y2=0.0, z2=8_000.0),
        _plate(name="C", thickness=10.0, z1=2_000.0, z2=2_000.0),
    ]))
    # sorted unique thicknesses: 10.0 -> palette[0], 15.0 -> palette[1]
    assert svg.count(f'stroke="{_PALETTE[0]}"') >= 3  # 2 plate lines + 1 swatch
    assert svg.count(f'stroke="{_PALETTE[1]}"') >= 2  # 1 plate line + 1 swatch
    assert "10.0 mm" in svg and "15.0 mm" in svg


def test_unknown_thickness_dashed_grey():
    svg = render_svg(_doc(plates=[_plate(thickness=None)]))
    assert _UNKNOWN_COLOR in svg
    assert "stroke-dasharray" in svg


def test_stiffener_stub_direction_and_number():
    svg = render_svg(_doc(plates=[_plate()],
                          stiffeners=[_stiffener(wdy=0.0, wdz=1.0)]))
    root = ET.fromstring(svg)
    stubs = [l for l in root.iter("{http://www.w3.org/2000/svg}line")
             if l.get("class") == "stiffener"]
    assert len(stubs) == 1
    stub = stubs[0]
    # web dir (0, +1): stub goes up => SVG y decreases, x constant
    assert float(stub.get("x1")) == float(stub.get("x2"))
    assert float(stub.get("y2")) < float(stub.get("y1"))
    # numbered label "1" exists
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    assert "1" in texts


def test_stiffener_unknown_direction_dashed_vertical():
    svg = render_svg(_doc(plates=[_plate()],
                          stiffeners=[_stiffener(wdy=None, wdz=None)]))
    root = ET.fromstring(svg)
    stubs = [l for l in root.iter("{http://www.w3.org/2000/svg}line")
             if l.get("class") == "stiffener"]
    assert stubs[0].get("stroke-dasharray")
    assert float(stubs[0].get("x1")) == float(stubs[0].get("x2"))


def test_stiffener_legend_rows_in_json_order():
    svg = render_svg(_doc(plates=[_plate()], stiffeners=[
        _stiffener(name="HP-A", profile_type="BulbFlat",
                   profile_dimensions="240 x 10"),
        _stiffener(name="FB-B", y=4_000.0),
    ]))
    assert "1  HP-A — BulbFlat 240 x 10" in svg
    assert "2  FB-B — FlatBar 200 x 20" in svg
    assert svg.index("HP-A") < svg.index("FB-B")


def test_user_strings_are_escaped():
    svg = render_svg(_doc(plates=[_plate(name="A<&>B")],
                          stiffeners=[_stiffener(name="L<1>")]))
    assert "A<&>B" not in svg
    assert "L<1>" not in svg
    ET.fromstring(svg)  # must stay well-formed


def test_empty_geometry_renders_note():
    svg = render_svg(_doc())
    assert "no geometry" in svg.lower()
    ET.fromstring(svg)


def test_no_unknown_swatch_when_all_thicknesses_known():
    svg = render_svg(_doc(plates=[_plate()]))
    assert "unknown" not in svg


def test_frame_zero_label_shown_in_title():
    svg = render_svg(_doc(plates=[_plate()], frame=0))
    assert "(frame 0)" in svg
