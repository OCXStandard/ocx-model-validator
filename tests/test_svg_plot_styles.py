"""Styling hooks on the cross-section SVG renderer."""
from ocx_model_validator.sections.svg_plot import render_svg


def make_doc():
    return {
        "schema": "nh-cross-section/2",
        "source": {"file": "m.3docx"},
        "cross_section": {
            "x_mm": 160000.0,
            "frame": "210",
            "plates": [
                {"name": "P1", "y1_mm": 0.0, "z1_mm": 0.0,
                 "y2_mm": 1000.0, "z2_mm": 0.0, "thickness_mm": 10.0},
            ],
            "stiffeners": [
                {"name": "S1", "y_mm": 500.0, "z_mm": 0.0,
                 "web_dir_y": 0.0, "web_dir_z": 1.0,
                 "profile_type": "FlatBar",
                 "profile_dimensions": "300 x 11"},
            ],
        },
    }


def test_default_rendering_unchanged():
    svg = render_svg(make_doc())
    assert 'stroke="#1f77b4"' in svg          # first palette colour
    assert "Plate thickness" in svg           # default legend
    assert 'stroke="black"' in svg            # default stiffener stub


def test_plate_style_overrides_colour_dash_title():
    def plate_style(row):
        assert row["name"] == "P1"
        return {"color": "#d62828", "dash": "6 4",
                "title": "P1 | DECK | 10 -> 8 mm"}

    svg = render_svg(make_doc(), plate_style=plate_style)
    assert 'stroke="#d62828"' in svg
    assert 'stroke-dasharray="6 4"' in svg
    assert "P1 | DECK | 10 -&gt; 8 mm" in svg or "P1 | DECK | 10 -> 8 mm" in svg


def test_stiffener_style_overrides_colour_and_title():
    def stiffener_style(row):
        return {"color": "#ffd166", "title": "S1 tooltip"}

    svg = render_svg(make_doc(), stiffener_style=stiffener_style)
    assert 'class="stiffener"' in svg
    assert 'stroke="#ffd166"' in svg
    assert "S1 tooltip" in svg


def test_legend_extra_and_thickness_legend_off():
    svg = render_svg(
        make_doc(),
        legend_extra=[("#c8c8c8", None, "no saving"),
                      ("#555555", "6 4", "flagged")],
        thickness_legend=False)
    assert "Plate thickness" not in svg
    assert "no saving" in svg
    assert "flagged" in svg
