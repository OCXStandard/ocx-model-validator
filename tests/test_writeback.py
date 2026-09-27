"""Unit tests for applying an nh-optimisation/1 report to an OCX model."""

import pytest
from lxml import etree

from ocx_model_validator import writeback

NS = "https://3docx.org/fileadmin//ocx_schema//V300//OCX_Schema.xsd"


def make_model(tmp_path):
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ocx:ocxXML xmlns:ocx="{NS}" schemaVersion="3.0.0">
  <ocx:Vessel>
    <ocx:Panel>
      <ocx:ComposedOf>
        <ocx:Plate id="pl1" name="P:P50/DECK" ocx:GUIDRef="guid-p1">
          <ocx:PlateMaterial>
            <ocx:Thickness numericvalue="0.03" unit="Um"/>
          </ocx:PlateMaterial>
        </ocx:Plate>
        <ocx:Stiffener id="st1" name="S:1/DECK" ocx:GUIDRef="guid-s1">
          <ocx:SectionRef localRef="sec1" ocx:GUIDRef="guid-sec1"
                          name="L450x150x11x14"/>
        </ocx:Stiffener>
      </ocx:ComposedOf>
    </ocx:Panel>
  </ocx:Vessel>
  <ocx:ClassCatalogue>
    <ocx:XSectionCatalogue>
      <ocx:BarSection id="sec1" name="L450x150x11x14"
                      ocx:GUIDRef="guid-sec1">
        <ocx:LBar>
          <ocx:Height numericvalue="0.45" unit="Um"/>
          <ocx:Width numericvalue="0.15" unit="Um"/>
          <ocx:WebThickness numericvalue="0.011" unit="Um"/>
          <ocx:FlangeThickness numericvalue="0.014" unit="Um"/>
        </ocx:LBar>
      </ocx:BarSection>
    </ocx:XSectionCatalogue>
  </ocx:ClassCatalogue>
</ocx:ocxXML>"""
    path = tmp_path / "model.3docx"
    path.write_text(xml, encoding="utf-8")
    return path


def make_report(plates=(), stiffeners=()):
    return {"schema": "nh-optimisation/1", "source": {},
            "plates": list(plates), "stiffeners": list(stiffeners),
            "totals": {}}


def plate_row(**over):
    row = {"name": "P:P50/DECK_EPP1", "guidref": None,
           "offered_mm": 30.0, "optimised_mm": 20.0, "status": "optimised",
           "saving_kg_per_m": 66.7, "iterations": 2}
    row.update(over)
    return row


def stiffener_row(**over):
    row = {"name": "S:1/DECK", "guidref": "guid-s1",
           "profile_type": "AngleBar",
           "offered_profile": "450 x 150 x 11 x 14",
           "optimised_profile": "400 x 100 x 10 x 14",
           "status": "optimised", "saving_kg_per_m": 10.0, "iterations": 3}
    row.update(over)
    return row


def parse(path):
    return etree.parse(str(path)).getroot()


def write_root(path, root):
    etree.ElementTree(root).write(str(path), xml_declaration=True,
                                  encoding="utf-8", pretty_print=True)


def test_plate_thickness_patched_um(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(
        model, make_report(plates=[plate_row()]), out)
    root = parse(out)
    thickness = root.find(f".//{{{NS}}}Plate/{{{NS}}}PlateMaterial"
                          f"/{{{NS}}}Thickness")
    assert float(thickness.get("numericvalue")) == pytest.approx(0.02)
    assert thickness.get("unit") == "Um"
    assert result["plates_updated"] == 1


def test_max_epp_thickness_governs_parent_plate(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    writeback.apply_report(model, make_report(plates=[
        plate_row(name="P:P50/DECK_EPP1", optimised_mm=18.0),
        plate_row(name="P:P50/DECK_EPP2", optimised_mm=22.0),
    ]), out)
    thickness = parse(out).find(f".//{{{NS}}}Plate/{{{NS}}}PlateMaterial"
                                f"/{{{NS}}}Thickness")
    assert float(thickness.get("numericvalue")) == pytest.approx(0.022)


def test_mixed_status_epp_rows_do_not_reduce_parent_plate(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(model, make_report(plates=[
        plate_row(name="P:P50/DECK_EPP1", optimised_mm=20.0),
        plate_row(name="P:P50/DECK_EPP2", status="under-dimensioned",
                  optimised_mm=30.0),
    ]), out)
    thickness = parse(out).find(f".//{{{NS}}}Plate/{{{NS}}}PlateMaterial"
                                f"/{{{NS}}}Thickness")
    assert float(thickness.get("numericvalue")) == pytest.approx(0.03)
    assert result["plates_updated"] == 0
    assert result["plates_skipped_mixed"] == 1
    assert result["unmatched"] == []


def test_stiffener_gets_new_bar_section(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(
        model, make_report(stiffeners=[stiffener_row()]), out)
    root = parse(out)
    ref = root.find(f".//{{{NS}}}Stiffener/{{{NS}}}SectionRef")
    new_id = ref.get("localRef")
    assert new_id != "sec1"
    catalogue = root.find(f".//{{{NS}}}ClassCatalogue/"
                          f"{{{NS}}}XSectionCatalogue")
    section = catalogue.find(f"{{{NS}}}BarSection[@id='{new_id}']")
    lbar = section.find(f"{{{NS}}}LBar")
    assert float(lbar.find(f"{{{NS}}}Height").get(
        "numericvalue")) == pytest.approx(0.4)
    assert float(lbar.find(f"{{{NS}}}Width").get(
        "numericvalue")) == pytest.approx(0.1)
    assert float(lbar.find(f"{{{NS}}}WebThickness").get(
        "numericvalue")) == pytest.approx(0.01)
    assert float(lbar.find(f"{{{NS}}}FlangeThickness").get(
        "numericvalue")) == pytest.approx(0.014)
    # original section untouched for other users
    assert root.find(f".//{{{NS}}}BarSection[@id='sec1']") is not None
    assert section.getparent() is catalogue
    assert result["stiffeners_updated"] == 1


def test_plate_guid_match_wins_before_name_fallback(tmp_path):
    model = make_model(tmp_path)
    root = parse(model)
    composed = root.find(f".//{{{NS}}}ComposedOf")
    target = root.find(f".//{{{NS}}}Plate")
    duplicate = etree.fromstring(etree.tostring(target))
    duplicate.set("id", "pl-duplicate")
    duplicate.set(f"{{{NS}}}GUIDRef", "guid-other")
    duplicate.find(f"{{{NS}}}PlateMaterial/{{{NS}}}Thickness").set(
        "numericvalue", "0.03")
    composed.insert(0, duplicate)
    write_root(model, root)

    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(
        model, make_report(plates=[plate_row(guidref="guid-p1")]), out)
    root = parse(out)
    duplicate_thickness = root.find(
        f".//{{{NS}}}Plate[@id='pl-duplicate']/{{{NS}}}PlateMaterial/"
        f"{{{NS}}}Thickness")
    target_thickness = root.find(
        f".//{{{NS}}}Plate[@id='pl1']/{{{NS}}}PlateMaterial/"
        f"{{{NS}}}Thickness")
    assert float(duplicate_thickness.get("numericvalue")) == pytest.approx(
        0.03)
    assert float(target_thickness.get("numericvalue")) == pytest.approx(0.02)
    assert result["plates_updated"] == 1


def test_stiffener_guid_match_wins_before_name_fallback(tmp_path):
    model = make_model(tmp_path)
    root = parse(model)
    composed = root.find(f".//{{{NS}}}ComposedOf")
    target = root.find(f".//{{{NS}}}Stiffener")
    duplicate = etree.fromstring(etree.tostring(target))
    duplicate.set("id", "st-duplicate")
    duplicate.set(f"{{{NS}}}GUIDRef", "guid-other")
    duplicate.find(f"{{{NS}}}SectionRef").set("localRef", "sec1")
    composed.insert(0, duplicate)
    write_root(model, root)

    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(
        model, make_report(stiffeners=[stiffener_row(guidref="guid-s1")]),
        out)
    root = parse(out)
    duplicate_ref = root.find(
        f".//{{{NS}}}Stiffener[@id='st-duplicate']/{{{NS}}}SectionRef")
    target_ref = root.find(
        f".//{{{NS}}}Stiffener[@id='st1']/{{{NS}}}SectionRef")
    assert duplicate_ref.get("localRef") == "sec1"
    assert target_ref.get("localRef") != "sec1"
    assert result["stiffeners_updated"] == 1


def test_unknown_plate_thickness_unit_is_unmatched(tmp_path):
    model = make_model(tmp_path)
    root = parse(model)
    root.find(f".//{{{NS}}}Plate/{{{NS}}}PlateMaterial/"
              f"{{{NS}}}Thickness").set("unit", "Uinch")
    write_root(model, root)

    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(
        model, make_report(plates=[plate_row()]), out)
    thickness = parse(out).find(f".//{{{NS}}}Plate/"
                                f"{{{NS}}}PlateMaterial/"
                                f"{{{NS}}}Thickness")
    assert thickness.get("numericvalue") == "0.03"
    assert result["plates_updated"] == 0
    assert result["unmatched"] == ["P:P50/DECK_EPP1"]


def test_non_optimised_rows_skipped(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(model, make_report(
        plates=[plate_row(status="already-minimal")],
        stiffeners=[stiffener_row(status="under-dimensioned")]), out)
    assert result["plates_updated"] == 0
    assert result["stiffeners_updated"] == 0
    thickness = parse(out).find(f".//{{{NS}}}Plate/{{{NS}}}PlateMaterial"
                                f"/{{{NS}}}Thickness")
    assert float(thickness.get("numericvalue")) == pytest.approx(0.03)


def test_unmatched_rows_reported(tmp_path):
    model = make_model(tmp_path)
    out = tmp_path / "patched.3docx"
    result = writeback.apply_report(model, make_report(
        plates=[plate_row(name="P:GHOST_EPP1", guidref="no-such")]), out)
    assert result["plates_updated"] == 0
    assert result["unmatched"] == ["P:GHOST_EPP1"]


def test_refuses_overwrite_of_input(tmp_path):
    model = make_model(tmp_path)
    with pytest.raises(ValueError, match="differ"):
        writeback.apply_report(model, make_report(), model)


def test_rejects_wrong_schema(tmp_path):
    model = make_model(tmp_path)
    with pytest.raises(ValueError, match="nh-optimisation/1"):
        writeback.apply_report(model, {"schema": "bogus/1"},
                               tmp_path / "out.3docx")
