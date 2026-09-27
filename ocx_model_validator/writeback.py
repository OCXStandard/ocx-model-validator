"""Apply an nh-optimisation/1 report to an OCX 3D model file.

Patches plate thicknesses only when every EPP strip is optimised (max over
the plate's optimised EPP strips — conservative)
and repoints stiffener SectionRefs to freshly created BarSections carrying
the optimised profile dimensions. Writes a new .3docx file; never modifies
the input.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from lxml import etree

REPORT_SCHEMA = "nh-optimisation/1"

# metres per unit for OCX quantity attributes
_UNIT_TO_M = {"Um": 1.0, "Umm": 0.001, "Ucm": 0.01}

# nauticushull profile type -> (OCX bar child tag, dimension child tags)
_PROFILE_TAGS = {
    "AngleBar": ("LBar", ("Height", "Width", "WebThickness",
                          "FlangeThickness")),
    "TBar": ("TBar", ("Height", "Width", "WebThickness",
                      "FlangeThickness")),
    "FlatBar": ("FlatBar", ("Height", "WebThickness")),
    "HpBulb": ("BulbFlat", ("Height", "WebThickness")),
}


def apply_report(model_path: str | Path, report: dict[str, Any],
                 output_path: str | Path) -> dict[str, Any]:
    """Patch model_path with the report's optimised rows into output_path.

    Returns {"plates_updated", "plates_skipped_mixed",
    "stiffeners_updated", "unmatched", "output_path"}."""
    model_path = Path(model_path)
    output_path = Path(output_path)
    if model_path.resolve() == output_path.resolve():
        raise ValueError("output_path must differ from model_path")
    if report.get("schema") != REPORT_SCHEMA:
        raise ValueError(f"expected schema {REPORT_SCHEMA!r}, "
                         f"got {report.get('schema')!r}")

    tree = etree.parse(str(model_path))
    root = tree.getroot()
    ns = etree.QName(root).namespace

    unmatched: list[str] = []
    plates_updated, plates_skipped_mixed = _patch_plates(
        root, ns, report.get("plates", []), unmatched)
    stiffeners_updated = _patch_stiffeners(root, ns,
                                           report.get("stiffeners", []),
                                           unmatched)

    tree.write(str(output_path), xml_declaration=True, encoding="utf-8",
               pretty_print=True)
    return {"plates_updated": plates_updated,
            "plates_skipped_mixed": plates_skipped_mixed,
            "stiffeners_updated": stiffeners_updated,
            "unmatched": unmatched, "output_path": str(output_path)}


def _parent_plate_name(epp_name: str) -> str:
    return epp_name.rsplit("_EPP", 1)[0]


def _find_by_guid_then_name(root: Any, ns: str, tag: str,
                            guidref: str | None, name: str) -> Any | None:
    guid_attr = f"{{{ns}}}GUIDRef"
    if guidref:
        for cand in root.iter(f"{{{ns}}}{tag}"):
            if cand.get(guid_attr) == guidref:
                return cand
    for cand in root.iter(f"{{{ns}}}{tag}"):
        if cand.get("name") == name:
            return cand
    return None


def _patch_plates(root: Any, ns: str, rows: list[dict[str, Any]],
                  unmatched: list[str]) -> tuple[int, int]:
    # Group all EPP rows by parent plate. A parent plate has one thickness, so
    # only reduce it when every EPP row for that parent was optimised.
    by_plate: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row.get("guidref"), _parent_plate_name(row["name"]))
        by_plate.setdefault(key, []).append(row)

    updated = 0
    skipped_mixed = 0
    for (guidref, plate_name), plate_rows in by_plate.items():
        if any(row.get("status") != "optimised" for row in plate_rows):
            if any(row.get("status") == "optimised" for row in plate_rows):
                skipped_mixed += 1
            continue
        row = max(plate_rows, key=lambda item: item["optimised_mm"])
        plate = _find_by_guid_then_name(root, ns, "Plate", guidref,
                                        plate_name)
        if plate is None:
            unmatched.append(row["name"])
            continue
        thickness = plate.find(f"{{{ns}}}PlateMaterial"
                               f"/{{{ns}}}Thickness")
        if thickness is None:
            unmatched.append(row["name"])
            continue
        unit = thickness.get("unit", "Um")
        factor = _UNIT_TO_M.get(unit)
        if factor is None:
            unmatched.append(row["name"])
            continue
        thickness.set("numericvalue",
                      repr(row["optimised_mm"] * 0.001 / factor))
        updated += 1
    return updated, skipped_mixed


def _patch_stiffeners(root: Any, ns: str, rows: list[dict[str, Any]],
                      unmatched: list[str]) -> int:
    guid_attr = f"{{{ns}}}GUIDRef"
    class_catalogue = root.find(f".//{{{ns}}}ClassCatalogue")
    xsection_catalogue = root.find(f".//{{{ns}}}ClassCatalogue/"
                                   f"{{{ns}}}XSectionCatalogue")
    if xsection_catalogue is None and class_catalogue is not None:
        xsection_catalogue = etree.SubElement(
            class_catalogue, f"{{{ns}}}XSectionCatalogue")
    updated = 0
    for row in rows:
        if row.get("status") != "optimised":
            continue
        if xsection_catalogue is None:
            unmatched.append(row["name"])
            continue
        stiffener = _find_by_guid_then_name(root, ns, "Stiffener",
                                            row.get("guidref"), row["name"])
        ref = stiffener.find(f"{{{ns}}}SectionRef") \
            if stiffener is not None else None
        if ref is None:
            unmatched.append(row["name"])
            continue
        section = _make_bar_section(ns, row)
        if section is None:
            unmatched.append(row["name"])
            continue
        xsection_catalogue.append(section)
        ref.set("localRef", section.get("id"))
        ref.set(guid_attr, section.get(guid_attr))
        ref.set("name", section.get("name"))
        updated += 1
    return updated


def _make_bar_section(ns: str, row: dict[str, Any]) -> Any | None:
    tags = _PROFILE_TAGS.get(row.get("profile_type"))
    if tags is None:
        return None
    bar_tag, dim_tags = tags
    dims = [float(v) for v in
            row["optimised_profile"].replace("x", " ").split()]
    if len(dims) != len(dim_tags):
        return None
    new_id = f"nhopt_{uuid.uuid4().hex[:12]}"
    name = f"OPT_{row['profile_type']}_" + "x".join(
        f"{d:g}" for d in dims)
    section = etree.Element(f"{{{ns}}}BarSection", id=new_id, name=name)
    section.set(f"{{{ns}}}GUIDRef", str(uuid.uuid4()))
    bar = etree.SubElement(section, f"{{{ns}}}{bar_tag}")
    for tag, mm in zip(dim_tags, dims):
        elem = etree.SubElement(bar, f"{{{ns}}}{tag}")
        elem.set("numericvalue", repr(mm * 0.001))
        elem.set("unit", "Um")
    return section
