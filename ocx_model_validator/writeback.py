"""Apply an nh-optimisation/1 report to an OCX 3D model file.

Patches plate thicknesses (max over the plate's EPP strips — conservative)
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

    Returns {"plates_updated", "stiffeners_updated", "unmatched",
    "output_path"}."""
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
    plates_updated = _patch_plates(root, ns,
                                   report.get("plates", []), unmatched)
    stiffeners_updated = _patch_stiffeners(root, ns,
                                           report.get("stiffeners", []),
                                           unmatched)

    tree.write(str(output_path), xml_declaration=True, encoding="utf-8",
               pretty_print=True)
    return {"plates_updated": plates_updated,
            "stiffeners_updated": stiffeners_updated,
            "unmatched": unmatched, "output_path": str(output_path)}


def _parent_plate_name(epp_name: str) -> str:
    # "P:P50/DECK_EPP1" -> "P50/DECK"
    name = epp_name.split(":", 1)[-1]
    return name.rsplit("_EPP", 1)[0]


def _patch_plates(root: Any, ns: str, rows: list[dict[str, Any]],
                  unmatched: list[str]) -> int:
    # Group optimised EPP rows by parent plate; apply the MAX thickness.
    by_plate: dict[tuple[str | None, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("status") != "optimised":
            continue
        key = (row.get("guidref"), _parent_plate_name(row["name"]))
        best = by_plate.get(key)
        if best is None or row["optimised_mm"] > best["optimised_mm"]:
            by_plate[key] = row

    updated = 0
    guid_attr = f"{{{ns}}}GUIDRef"
    for (guidref, plate_name), row in by_plate.items():
        plate = None
        for cand in root.iter(f"{{{ns}}}Plate"):
            if (guidref and cand.get(guid_attr) == guidref) or \
                    cand.get("name") == plate_name:
                plate = cand
                break
        if plate is None:
            unmatched.append(row["name"])
            continue
        thickness = plate.find(f"{{{ns}}}PlateMaterial"
                               f"/{{{ns}}}Thickness")
        if thickness is None:
            unmatched.append(row["name"])
            continue
        factor = _UNIT_TO_M.get(thickness.get("unit", "Um"), 1.0)
        thickness.set("numericvalue",
                      repr(row["optimised_mm"] * 0.001 / factor))
        updated += 1
    return updated


def _patch_stiffeners(root: Any, ns: str, rows: list[dict[str, Any]],
                      unmatched: list[str]) -> int:
    guid_attr = f"{{{ns}}}GUIDRef"
    vessel = root.find(f"{{{ns}}}Vessel")
    if vessel is None:
        vessel = root
    updated = 0
    for row in rows:
        if row.get("status") != "optimised":
            continue
        stiffener = None
        for cand in root.iter(f"{{{ns}}}Stiffener"):
            if (row.get("guidref")
                    and cand.get(guid_attr) == row["guidref"]) or \
                    cand.get("name") == row["name"]:
                stiffener = cand
                break
        ref = stiffener.find(f"{{{ns}}}SectionRef") \
            if stiffener is not None else None
        if ref is None:
            unmatched.append(row["name"])
            continue
        section = _make_bar_section(ns, row)
        if section is None:
            unmatched.append(row["name"])
            continue
        vessel.append(section)
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
