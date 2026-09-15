"""Pure helpers for HMX section export geometry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import asin, atan2, degrees, hypot, pi, tau
from pathlib import Path
from statistics import median
from typing import Iterable

from lxml import etree

from ocx_model_validator.reporting.generators.model_extent import extent_mm
from ocx_model_validator.sections.document import build_compartments_block
from ocx_model_validator.sections.section_builder import CrossSection, SectionPlate, SectionStiffener


_LSTIFF_TYPE = {
    "flat_bar": 10,
    "bulb_flat": 20,
    "l_section": 31,
    "l_overshoot_flange": 35,
    "l_overshoot_web": 36,
    "t_section": 40,
}
_SHIP_RULE_CHILD = {
    "DNV": "DNV",
    "RV5": "RV5",
    "CSR-H": "CSR-H",
}
RULE_SETS: tuple[str, ...] = tuple(_SHIP_RULE_CHILD)
_COMPARTMENT_TYPE = {
    "VOIDSPACE": "VoidSpace",
    "BALLASTWATERTANK": "BallastWaterTank",
    "FUELTANK": "FuelOilTank",
    "FRESHWATERTANK": "FreshWaterTank",
    "CARGOHOLD": "CargoHold",
}
_GENERAL_SHIP_DATA_ATTRS = {
    "MaxServiceSpeed": "0",
    "MinNormBalDraught": "0",
    "HeavyBalDraught": "0",
    "DeepestEqWLDamaged": "0",
    "SlammingDraughtEmpty": "0",
    "SlammingDraughtFull": "0",
    "DeadWeightLT50000": "false",
    "FreeboardType": "B",
    "BilgKeel": "false",
}


@dataclass
class _Chain:
    points: list[tuple[float, float]]
    plates: list[SectionPlate]

    def __post_init__(self) -> None:
        if len(self.points) != len(self.plates) + 1:
            raise ValueError(
                f"chain invariant violated: {len(self.points)} points "
                f"for {len(self.plates)} plates (expected plates + 1)"
            )


def _chain_segments(plates: Iterable[SectionPlate], tol: float = 1.0) -> list[_Chain]:
    """Greedily connect plate segments whose endpoints touch within ``tol`` mm."""
    unused = list(plates)
    chains: list[_Chain] = []

    while unused:
        first = unused.pop(0)
        chain = _Chain(
            points=[(first.y1_mm, first.z1_mm), (first.y2_mm, first.z2_mm)],
            plates=[first],
        )

        grew = True
        while grew:
            grew = False
            start = chain.points[0]
            end = chain.points[-1]

            for idx, candidate in enumerate(unused):
                p1 = (candidate.y1_mm, candidate.z1_mm)
                p2 = (candidate.y2_mm, candidate.z2_mm)

                if _same_point(end, p1, tol):
                    chain.points.append(p2)
                    chain.plates.append(candidate)
                elif _same_point(end, p2, tol):
                    chain.points.append(p1)
                    chain.plates.append(candidate)
                elif _same_point(start, p2, tol):
                    chain.points.insert(0, p1)
                    chain.plates.insert(0, candidate)
                elif _same_point(start, p1, tol):
                    chain.points.insert(0, p2)
                    chain.plates.insert(0, candidate)
                else:
                    continue

                unused.pop(idx)
                grew = True
                break

        chains.append(chain)

    return chains


def _signed_radius(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float | None:
    """Return radius signed by arc center side relative to segment travel.

    Arcs are assumed minor (<180°, chord-recoverable) per the OCX bilge use case:
    bilge arcs are quarter-to-semi circles, and the chord formula degrades at exactly
    180°.
    """
    if plate.radius_mm is None:
        return None
    if plate.arc_center_y_mm is None or plate.arc_center_z_mm is None:
        return -abs(plate.radius_mm)

    y1, z1 = p1
    y2, z2 = p2
    dy = y2 - y1
    dz = z2 - z1
    cross = dy * (plate.arc_center_z_mm - z1) - dz * (plate.arc_center_y_mm - y1)
    return abs(plate.radius_mm) if cross >= 0.0 else -abs(plate.radius_mm)


def _arc_length_of(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Return chord length for straight segments or circular arc length.

    Arcs are assumed minor (<180°, chord-recoverable) per the OCX bilge use case:
    bilge arcs are quarter-to-semi circles, and the chord formula degrades at exactly
    180°.
    """
    chord = _distance(p1, p2)
    if plate.radius_mm is None:
        return chord

    radius = abs(plate.radius_mm)
    if radius <= 0.0:
        return chord

    theta = 2.0 * asin(min(1.0, chord / (2.0 * radius)))
    return radius * theta


def _arc_position(_chain: _Chain, y: float, z: float) -> float:
    """Return arc-length station of the nearest chord projection on ``chain``."""
    best_index = 0
    best_t = 0.0
    best_dist = float("inf")

    for idx, (p1, p2) in enumerate(zip(_chain.points, _chain.points[1:])):
        t, dist = _projection((y, z), p1, p2)
        if dist < best_dist:
            best_index = idx
            best_t = t
            best_dist = dist

    prefix = sum(
        _arc_length_of(plate, p1, p2)
        for plate, p1, p2 in zip(_chain.plates[:best_index], _chain.points, _chain.points[1:])
    )
    plate = _chain.plates[best_index]
    p1 = _chain.points[best_index]
    p2 = _chain.points[best_index + 1]
    seg_len = _arc_length_of(plate, p1, p2)
    if (
        plate.radius_mm is not None
        and plate.arc_center_y_mm is not None
        and plate.arc_center_z_mm is not None
        and abs(plate.radius_mm) > 0.0
    ):
        return prefix + _arc_station_on_segment(plate, p1, p2, (y, z), seg_len)

    return prefix + best_t * seg_len


def _level1_code(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
    extent: dict[str, float] | None,
) -> str:
    """Classify a plate segment into the HMX level-1 structural code."""
    if plate.radius_mm is not None:
        return "BILGE"

    if not extent:
        return "Undefined"

    try:
        min_y = extent["min_y"]
        max_y = extent["max_y"]
        min_z = extent["min_z"]
        max_z = extent["max_z"]
    except KeyError:
        return "Undefined"

    if None in (min_y, max_y, min_z, max_z):
        return "Undefined"

    y1, z1 = p1
    y2, z2 = p2
    dy = y2 - y1
    dz = z2 - z1
    span_z = max_z - min_z
    if span_z <= 0.0 or max(abs(min_y), abs(max_y)) <= 0.0:
        return "Undefined"

    mid_y = (y1 + y2) / 2.0
    mid_z = (z1 + z2) / 2.0

    if abs(dz) <= 0.05 * max(abs(dy), 1.0):
        edge_tol = 0.05 * span_z
        if abs(mid_z - min_z) <= edge_tol:
            return "GBOTTOM"
        if abs(mid_z - max_z) <= edge_tol:
            return "STRDECK"

    if abs(dy) <= 0.05 * max(abs(dz), 1.0):
        side_limit = 0.95 * max(abs(min_y), abs(max_y))
        if abs(mid_y) >= side_limit:
            return "SIDE"

    return "Undefined"


def _side(chain: _Chain) -> str:
    """Return side code based on mean transverse coordinate of chain vertices."""
    mean_y = sum(y for y, _ in chain.points) / len(chain.points)
    if mean_y > 1.0:
        return "LEFT"
    if mean_y < -1.0:
        return "RIGHT"
    return "CENTER"


def _angles(stiffener: SectionStiffener) -> tuple[float, float]:
    """Return web and flange angles from a stiffener web direction vector."""
    if stiffener.web_dir_y is None or stiffener.web_dir_z is None:
        return (90.0, 270.0)

    web = degrees(atan2(stiffener.web_dir_z, stiffener.web_dir_y)) % 360.0
    # Heuristic: FlAngle=90 for WebAngle in [0°,90°), otherwise 270. Matches the
    # ISSCFrame170.hmx sample away from vertical webs; the true flange side is not
    # derivable from web direction alone (ambiguous at 90°/270°).
    flange = 90.0 if web < 90.0 else 270.0
    return (web, flange)


class _MaterialIds:
    """Stable sequential material IDs keyed by yield strength."""

    def __init__(self) -> None:
        self._ids: dict[float, str] = {}

    def id_for(self, yield_mpa: float) -> str:
        if yield_mpa not in self._ids:
            self._ids[yield_mpa] = str(len(self._ids) + 1)
        return self._ids[yield_mpa]

    def items(self):
        return self._ids.items()


def build_hmx(
    vessel,
    cross_section: CrossSection,
    frame_table,
    rule_set: str = "DNV",
) -> etree._Element:
    """Build a Nauticus-compatible Hull XML model with one Scantling section.

    Nauticus sample files leave some schema-required structural wrappers empty
    when no real structure is present; the exporter mirrors that convention
    instead of adding fake cutouts or stiffeners for strict XSD validity.
    """
    if rule_set not in _SHIP_RULE_CHILD:
        raise ValueError(f"Unsupported rule set {rule_set!r}")

    warnings = [*getattr(frame_table, "warnings", []), *cross_section.warnings]
    if not cross_section.plates:
        raise ValueError("HMX Scantling export requires at least one plate")
    extent = extent_mm(vessel)
    materials = _MaterialIds()
    _register_section_materials(cross_section, materials)

    root = etree.Element("HullModel")
    root.append(_ship_data(rule_set, extent, materials, warnings))
    root.append(_frame_table(frame_table, warnings))
    compartments, comp_boxes = _compartments(vessel, warnings, rule_set=rule_set)
    if compartments is not None:
        root.append(compartments)

    cross_sections = etree.SubElement(root, "CrossSections")
    cross_sections.append(
        _scantling(vessel, cross_section, frame_table, extent, comp_boxes, materials, warnings)
    )

    if warnings:
        root.insert(0, etree.Comment(_xml_comment_text("warnings: " + "; ".join(dict.fromkeys(warnings)))))
    return root


def save_hmx(root: etree._Element, path: str | Path) -> None:
    """Save an HMX XML document with declaration and stable pretty printing."""
    _write_pretty_xml(root, path)


def _write_pretty_xml(root: etree._Element, path: str | Path) -> None:
    etree.ElementTree(root).write(
        str(path),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )


def _ship_data(
    rule_set: str,
    extent: dict[str, float | None] | None,
    materials: _MaterialIds | None,
    warnings: list[str],
) -> etree._Element:
    """Build the HMX ShipData block."""
    rule_child_name = _SHIP_RULE_CHILD[rule_set]
    ship_data = etree.Element("ShipData", VesselId="", ShipType="Other")
    rule_child = etree.SubElement(ship_data, rule_child_name)

    applicable_attrs = {"RuleEdition": "2024"}
    if rule_set == "DNV":
        applicable_attrs["RuleSet"] = "DNV-1A1"
    etree.SubElement(rule_child, "ApplicableRules", **applicable_attrs)
    warnings.append("ShipData ApplicableRules RuleEdition uses placeholder value 2024")

    etree.SubElement(rule_child, "MainDimensions", **_main_dimensions_attrs(extent, warnings))

    general_tag = "GeneralShipDataType" if rule_set == "DNV" else "GeneralShipData"
    etree.SubElement(rule_child, general_tag, **_GENERAL_SHIP_DATA_ATTRS)
    warnings.append(
        "ShipData GeneralShipData uses placeholder values for required attributes"
    )

    etree.SubElement(rule_child, "MaterialData", **_material_data_attrs(materials, warnings))

    if rule_set != "DNV":
        etree.SubElement(rule_child, "IceClassData")

    return ship_data


def _scantling(
    vessel,
    cross_section: CrossSection,
    frame_table,
    extent: dict[str, float] | None,
    comp_boxes: dict[str, dict],
    materials: _MaterialIds,
    warnings: list[str],
) -> etree._Element:
    scantling = etree.Element("Scantling")
    _append_section_body(
        scantling, vessel, cross_section, frame_table, extent,
        comp_boxes, materials, warnings, _LSTIFF_TYPE,
    )
    return scantling


def _append_section_body(
    parent: etree._Element,
    vessel,
    cross_section: CrossSection,
    frame_table,
    extent: dict[str, float] | None,
    comp_boxes: dict[str, dict] | None,
    materials: _MaterialIds | None,
    warnings: list[str],
    lstiff_types: dict[str, int],
) -> None:
    """Append the shared IDDATA/POSITION/MATERIAL/MISC/PANEL section body.

    ``comp_boxes=None`` suppresses SEGMENT compartment refs and
    ``materials=None`` suppresses MaterialId attributes (2DLX mode).
    """
    _append_iddata(parent, vessel, cross_section)
    _append_position(parent, cross_section, extent)
    _append_material(parent, cross_section)

    stdspan = _standard_span_mm(frame_table, cross_section.x_mm, warnings)
    stdspace = _standard_spacing_mm(cross_section)
    _append_misc(parent, extent, stdspan, stdspace)

    chains = _chain_segments(cross_section.plates)
    assigned_stiffeners = _assign_stiffeners_to_chains(cross_section.stiffeners, chains)
    for index, chain in enumerate(chains):
        _append_panel(
            parent,
            chain,
            assigned_stiffeners.get(index, []),
            extent,
            comp_boxes,
            cross_section.x_mm,
            stdspan,
            stdspace,
            materials,
            warnings,
            lstiff_types,
        )


def _append_iddata(parent: etree._Element, vessel, cross_section: CrossSection) -> None:
    iddata = etree.SubElement(parent, "IDDATA")
    section_name = getattr(vessel, "name", None) or getattr(vessel, "id", None)
    if not section_name:
        section_name = f"Section at x={_fmt(cross_section.x_mm)}"
    etree.SubElement(iddata, "NAME").text = str(section_name)
    etree.SubElement(iddata, "DATE").text = date.today().isoformat()
    etree.SubElement(iddata, "SIGNATURE").text = "ocx-model-validator"
    etree.SubElement(iddata, "COMMENTS").text = ""


def _append_position(
    parent: etree._Element,
    cross_section: CrossSection,
    extent: dict[str, float] | None,
) -> None:
    position = etree.SubElement(parent, "POSITION")
    etree.SubElement(position, "DISTAP").text = _fmt_m(cross_section.x_mm)
    etree.SubElement(position, "MIDSHIP").text = "true" if _is_midship(cross_section.x_mm, extent) else "false"


def _append_material(parent: etree._Element, cross_section: CrossSection) -> None:
    material = etree.SubElement(parent, "MATERIAL")
    bottom, deck, between = _yield_bands(cross_section)
    etree.SubElement(material, "YIELDBOTT").text = _fmt(bottom)
    etree.SubElement(material, "YIELDDECK").text = _fmt(deck)
    etree.SubElement(material, "YIELDBETW").text = _fmt(between)


def _append_misc(
    parent: etree._Element,
    extent: dict[str, float] | None,
    stdspan: float,
    stdspace: float,
) -> None:
    misc = etree.SubElement(parent, "MISC")
    etree.SubElement(misc, "STRUCTTYPE").text = "SECTION"
    etree.SubElement(misc, "HSIDE").text = _fmt(_hside_mm(extent))
    etree.SubElement(misc, "STDSPAN").text = _fmt(stdspan)
    etree.SubElement(misc, "STDSPACE").text = _fmt(stdspace)


def _append_panel(
    parent: etree._Element,
    chain: _Chain,
    stiffeners: list[SectionStiffener],
    extent: dict[str, float] | None,
    comp_boxes: dict[str, dict] | None,
    x_mm: float,
    stdspan: float,
    stdspace: float,
    materials: _MaterialIds | None,
    warnings: list[str],
    lstiff_types: dict[str, int],
) -> None:
    panel = etree.SubElement(parent, "PANEL", Name=chain.plates[0].panel or chain.plates[0].name)
    etree.SubElement(panel, "CORRUGATED")
    etree.SubElement(panel, "BENDEFF").text = "100"
    etree.SubElement(panel, "SHEAREFF").text = "100"
    _append_shape(panel, chain, extent, comp_boxes, x_mm)
    _append_plates(panel, chain, materials, warnings)
    _append_longs(panel, chain, stiffeners, stdspan, materials, warnings, lstiff_types)
    _append_schema_cutouts(panel)
    _append_schema_trvstiffs(panel)


def _append_shape(
    panel: etree._Element,
    chain: _Chain,
    extent: dict[str, float] | None,
    comp_boxes: dict[str, dict] | None,
    x_mm: float,
) -> None:
    shape = etree.SubElement(panel, "SHAPE")
    first_y, first_z = chain.points[0]
    etree.SubElement(shape, "NODE", Y=_fmt(first_y), Z=_fmt(first_z))

    for plate, p1, p2 in zip(chain.plates, chain.points, chain.points[1:]):
        attrs = {
            "Y": _fmt(p2[0]),
            "Z": _fmt(p2[1]),
            "Position": _level1_code(plate, p1, p2, extent),
            "Girder": "Undefined",
            "Radius": _fmt(_signed_radius(plate, p1, p2) or 0.0),
        }
        if comp_boxes is not None:
            left, right = _segment_compartments(
                ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                (p2[0] - p1[0], p2[1] - p1[1]),
                comp_boxes,
                x_mm,
            )
            if left is not None:
                attrs["LeftCompartment"] = str(comp_boxes.get(left, {}).get("id", left))
            if right is not None:
                attrs["RightCompartment"] = str(comp_boxes.get(right, {}).get("id", right))
        etree.SubElement(shape, "SEGMENT", **attrs)


def _append_plates(
    panel: etree._Element,
    chain: _Chain,
    materials: _MaterialIds | None,
    warnings: list[str],
) -> None:
    plates = etree.SubElement(panel, "PLATES")
    side = _side(chain)
    for plate, p1, p2 in zip(chain.plates, chain.points, chain.points[1:]):
        yield_mpa = _yield_or_default(plate.material_reh_mpa)
        thickness = _required_numeric(
            plate.thickness_mm,
            0.0,
            f"plate {plate.name}: thickness is missing; emitted 0",
            warnings,
        )
        attrs = {
            "Width": _fmt(_arc_length_of(plate, p1, p2)),
            "RefCode": "CURVE",
            "Thickness": _fmt(thickness),
            "Yield": _fmt(yield_mpa),
        }
        if materials is not None:
            attrs["MaterialId"] = materials.id_for(yield_mpa)
        attrs["Material"] = "STDSTEEL"
        attrs["Side"] = side
        etree.SubElement(plates, "PLATE", **attrs)


def _append_longs(
    panel: etree._Element,
    chain: _Chain,
    stiffeners: list[SectionStiffener],
    stdspan: float,
    materials: _MaterialIds | None,
    warnings: list[str],
    lstiff_types: dict[str, int],
) -> None:
    longs = etree.SubElement(panel, "LONGS")
    if not stiffeners:
        return

    for stiffener in sorted(stiffeners, key=lambda item: _arc_position(chain, item.y_mm, item.z_mm)):
        yield_mpa = _yield_or_default(stiffener.material_reh_mpa)
        type_code = lstiff_types.get(stiffener.section_kind or "")
        if type_code is None:
            type_code = 10
            warnings.append(
                f"stiffener {stiffener.name}: unsupported section kind "
                f"{stiffener.section_kind!r}; using HMX type 10"
            )
        web_angle, flange_angle = _angles(stiffener)
        attrs = {
            "Name": stiffener.name,
            "Position": _fmt(_arc_position(chain, stiffener.y_mm, stiffener.z_mm)),
            "RefCode": "CURVE",
            "Type": str(type_code),
            "RusCode": "",
            "H": _fmt(stiffener.h_mm or 0.0),
            "BF": _fmt(stiffener.bf_mm or 0.0),
            "T": _fmt(stiffener.tw_mm or 0.0),
            "TF": _fmt(stiffener.tf_mm or 0.0),
            "WebAngle": _fmt(web_angle),
            "FlAngle": _fmt(flange_angle),
            "Span": _fmt(stdspan),
            "Yield": _fmt(yield_mpa),
        }
        if materials is not None:
            attrs["MaterialId"] = materials.id_for(yield_mpa)
        attrs["K"] = "0"
        attrs["BuckStiff"] = "false"
        etree.SubElement(longs, "LSTIFF", **attrs)


def _append_schema_cutouts(panel: etree._Element) -> None:
    etree.SubElement(panel, "CUTOUTS")


def _append_schema_trvstiffs(panel: etree._Element) -> None:
    etree.SubElement(panel, "TRVSTIFFS")


def _register_section_materials(cross_section: CrossSection, materials: _MaterialIds) -> None:
    for plate in cross_section.plates:
        materials.id_for(_yield_or_default(plate.material_reh_mpa))
    for stiffener in cross_section.stiffeners:
        materials.id_for(_yield_or_default(stiffener.material_reh_mpa))


def _yield_bands(cross_section: CrossSection) -> tuple[float, float, float]:
    if not cross_section.plates:
        return (235.0, 235.0, 235.0)
    z_values = [z for plate in cross_section.plates for z in (plate.z1_mm, plate.z2_mm)]
    min_z = min(z_values)
    max_z = max(z_values)
    span = max_z - min_z
    if span <= 0.0:
        mode = _mode_or_default(plate.material_reh_mpa for plate in cross_section.plates)
        return (mode, mode, mode)

    low_limit = min_z + 0.15 * span
    high_limit = max_z - 0.15 * span
    bottom: list[float | None] = []
    deck: list[float | None] = []
    between: list[float | None] = []
    for plate in cross_section.plates:
        mid_z = (plate.z1_mm + plate.z2_mm) / 2.0
        if mid_z <= low_limit:
            bottom.append(plate.material_reh_mpa)
        elif mid_z >= high_limit:
            deck.append(plate.material_reh_mpa)
        else:
            between.append(plate.material_reh_mpa)

    all_yields = [plate.material_reh_mpa for plate in cross_section.plates]
    fallback = _mode_or_default(all_yields)
    return (
        _mode_or_default(bottom, fallback),
        _mode_or_default(deck, fallback),
        _mode_or_default(between, fallback),
    )


def _mode_or_default(values: Iterable[float | None], default: float = 235.0) -> float:
    counts: dict[float, int] = {}
    for value in values:
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return default
    return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]


def _standard_span_mm(frame_table, x_mm: float, warnings: list[str]) -> float:
    rows = getattr(frame_table, "spacing_rows", None) or []
    if rows:
        current = rows[0][1]
        for row, spacing in rows:
            if getattr(row, "x_mm", float("-inf")) <= x_mm:
                current = spacing
            else:
                break
        return current

    entries = getattr(frame_table, "entries", None) or []
    if entries:
        return entries[0][1]

    warnings.append("FrameTable has no spacing data; Scantling STDSPAN uses fallback 800 mm")
    return 800.0


def _standard_spacing_mm(cross_section: CrossSection) -> float:
    spacings = [
        stiffener.spacing_mm
        for stiffener in cross_section.stiffeners
        if stiffener.spacing_mm is not None and stiffener.spacing_mm > 0.0
    ]
    if not spacings:
        return 800.0
    return float(median(spacings))


def _assign_stiffeners_to_chains(
    stiffeners: list[SectionStiffener],
    chains: list[_Chain],
) -> dict[int, list[SectionStiffener]]:
    assignments: dict[int, list[SectionStiffener]] = {idx: [] for idx in range(len(chains))}
    if not chains:
        return assignments
    for stiffener in stiffeners:
        idx = min(
            range(len(chains)),
            key=lambda chain_idx: _distance_to_chain((stiffener.y_mm, stiffener.z_mm), chains[chain_idx]),
        )
        assignments[idx].append(stiffener)
    return assignments


def _distance_to_chain(point: tuple[float, float], chain: _Chain) -> float:
    return min(_projection(point, p1, p2)[1] for p1, p2 in zip(chain.points, chain.points[1:]))


def _is_midship(x_mm: float, extent: dict[str, float] | None) -> bool:
    if extent is None:
        return False
    min_x = extent.get("min_x")
    max_x = extent.get("max_x")
    if min_x is None or max_x is None:
        return False
    lbp = max_x - min_x
    if lbp <= 0.0:
        return False
    return abs(x_mm - min_x - lbp / 2.0) <= 0.05 * lbp


def _hside_mm(extent: dict[str, float] | None) -> float:
    if extent is None:
        return 0.0
    min_z = extent.get("min_z")
    max_z = extent.get("max_z")
    if min_z is None or max_z is None:
        return 0.0
    return max_z - min_z


def _yield_or_default(value: float | None) -> float:
    return 235.0 if value is None else value


def _required_numeric(
    value: float | None,
    default: float,
    warning: str,
    warnings: list[str],
) -> float:
    if value is not None:
        return value
    warnings.append(warning)
    return default


def _xml_comment_text(text: str) -> str:
    safe = text.replace("--", "- -")
    if safe.endswith("-"):
        safe += " "
    return safe


def _frame_table(ft, warnings: list[str]) -> etree._Element:
    """Build the HMX FrameTable block."""
    frame_table = etree.Element(
        "FrameTable",
        FrameOffset=_fmt_m(ft.frame0_offset_mm),
        FrameRef="AP",
    )
    rows = (
        [(row.label, spacing_mm) for row, spacing_mm in ft.spacing_rows]
        if ft.spacing_rows
        else list(ft.entries)
    )
    if not rows:
        rows = [("Stern", 800.0)]
        warnings.append(
            "FrameTable has no spacing rows; emitted fallback Stern spacing 0.8 m"
        )

    for idx, (label, spacing_mm) in enumerate(rows):
        frame_no = "Stern" if idx == 0 else label
        etree.SubElement(
            frame_table,
            "Spacing",
            FrameNo=frame_no,
            Spacing=_fmt_m(spacing_mm),
        )
    return frame_table


def _compartments(
    vessel,
    warnings: list[str],
    rule_set: str = "DNV",
) -> tuple[etree._Element | None, dict[str, dict]]:
    """Build HMX Compartments and compartment boxes for later segment tagging."""
    rows, row_warnings = build_compartments_block(vessel)
    warnings.extend(row_warnings)
    compartments = etree.Element("Compartments")
    boxes: dict[str, dict] = {}

    for row in rows:
        name = row.get("name") or ""
        extent = row.get("extent_mm") or {}
        if _is_empty_extent(extent):
            warnings.append(f"compartment {name}: extent is empty; skipped")
            continue

        hmx_type = _hmx_compartment_type(row.get("tank_type"), name, warnings)
        comp_id = str(len(compartments) + 1)
        compartment = etree.SubElement(
            compartments,
            "Compartment",
            Name=name,
            Type=hmx_type,
            Id=comp_id,
        )
        etree.SubElement(compartment, "General", **_compartment_general_attrs(row, extent))
        if rule_set == "CSR-H":
            etree.SubElement(compartment, "CSRH", **_csrh_compartment_attrs(row))
        else:
            etree.SubElement(compartment, "RV5", **_rv5_compartment_attrs(row))
        geometry = etree.SubElement(compartment, "Geometry")
        etree.SubElement(geometry, "BoundingBox", **_bounding_box_attrs(extent))
        if name in boxes:
            warnings.append(
                f"duplicate compartment name {name!r}; keeping first bounding box for segment tagging"
            )
        else:
            boxes[name] = {"id": comp_id, **extent}

    if len(compartments) == 0:
        return None, {}
    return compartments, boxes


def _segment_compartments(
    p_mid: tuple[float, float],
    direction: tuple[float, float],
    comp_boxes: dict[str, dict],
    x_mm: float,
) -> tuple[str | None, str | None]:
    """Return names of compartments sampled 100 mm left and right of a segment."""
    dy, dz = direction
    length = hypot(dy, dz)
    if length <= 0.0:
        return (None, None)
    left_normal = (-dz / length, dy / length)
    left_point = (p_mid[0] + 100.0 * left_normal[0], p_mid[1] + 100.0 * left_normal[1])
    right_point = (p_mid[0] - 100.0 * left_normal[0], p_mid[1] - 100.0 * left_normal[1])
    return (
        _matching_compartment(left_point, comp_boxes, x_mm),
        _matching_compartment(right_point, comp_boxes, x_mm),
    )


def _main_dimensions_attrs(
    extent: dict[str, float | None] | None,
    warnings: list[str],
) -> dict[str, str]:
    if extent is None:
        warnings.append("ShipData MainDimensions extent is missing; omitted dimensions")
        return {}
    required = ("min_x", "max_x", "min_y", "max_y", "min_z", "max_z")
    if any(extent.get(key) is None for key in required):
        warnings.append("ShipData MainDimensions extent is incomplete; omitted dimensions")
        return {}

    length_m = (extent["max_x"] - extent["min_x"]) / 1000.0  # type: ignore[operator]
    breadth_m = (extent["max_y"] - extent["min_y"]) / 1000.0  # type: ignore[operator]
    depth_m = (extent["max_z"] - extent["min_z"]) / 1000.0  # type: ignore[operator]
    draught_m = 0.7 * depth_m
    warnings.append("ShipData MainDimensions draught T uses placeholder 0.7*D")
    return {
        "Lbp": _fmt(length_m),
        "B": _fmt(breadth_m),
        "D": _fmt(depth_m),
        "T": _fmt(draught_m),
    }


def _material_data_attrs(materials: _MaterialIds | None, warnings: list[str]) -> dict[str, str]:
    first_yield = None
    if materials is not None:
        first_yield = next((yield_mpa for yield_mpa, _ in materials.items()), None)
    sigma = _fmt(first_yield if first_yield is not None else 235.0)
    warnings.append("ShipData MaterialData SigmaF* uses placeholder values")
    return {
        "E": "206000",
        "SigmaFBott": sigma,
        "SigmaFDeck": sigma,
        "SigmaFMid": sigma,
    }


def _is_empty_extent(extent: dict) -> bool:
    keys = ("min_x", "max_x", "min_y", "max_y", "min_z", "max_z")
    return any(extent.get(key) is None for key in keys)


def _hmx_compartment_type(tank_type: str | None, name: str, warnings: list[str]) -> str:
    if tank_type in _COMPARTMENT_TYPE:
        return _COMPARTMENT_TYPE[tank_type]
    warnings.append(f"compartment {name}: unsupported tank type {tank_type!r}; using Undefined")
    return "Undefined"


def _compartment_general_attrs(row: dict, extent: dict) -> dict[str, str]:
    attrs: dict[str, str] = {}
    length = _extent_length(extent)
    if length is not None:
        attrs["Length"] = _fmt_int(length)
    air_pipe = row.get("air_pipe_height_mm")
    if air_pipe is not None:
        attrs["TopOfAirPipe"] = _fmt_int(air_pipe)
    volume = row.get("volume_m3")
    if volume is not None:
        attrs["Volume"] = _fmt(volume)
    cog = row.get("cog_mm")
    if cog is not None and len(cog) == 3:
        attrs["CgX"] = _fmt_int(cog[0])
        attrs["CgY"] = _fmt_int(cog[1])
        attrs["CgZ"] = _fmt_int(cog[2])
    return attrs


def _rv5_compartment_attrs(row: dict) -> dict[str, str]:
    pressure = row.get("relief_valve_pressure_kpa")
    if pressure is None:
        return {"PressureValveFitted": "false"}
    return {
        "OverPressure": _fmt(pressure),
        "PressureValveFitted": "true",
    }


def _csrh_compartment_attrs(row: dict) -> dict[str, str]:
    pressure = row.get("relief_valve_pressure_kpa")
    if pressure is None:
        return {}
    return {"OverPressure": _fmt(pressure)}


def _bounding_box_attrs(extent: dict) -> dict[str, str]:
    return {
        "MinX": _fmt(extent["min_x"]),
        "MaxX": _fmt(extent["max_x"]),
        "MinY": _fmt(extent["min_y"]),
        "MaxY": _fmt(extent["max_y"]),
        "MinZ": _fmt(extent["min_z"]),
        "MaxZ": _fmt(extent["max_z"]),
    }


def _extent_length(extent: dict) -> float | None:
    min_x = extent.get("min_x")
    max_x = extent.get("max_x")
    if min_x is None or max_x is None:
        return None
    return max_x - min_x


def _matching_compartment(
    point: tuple[float, float],
    comp_boxes: dict[str, dict],
    x_mm: float,
) -> str | None:
    y, z = point
    for name, box in comp_boxes.items():
        min_y = box.get("min_y")
        max_y = box.get("max_y")
        min_z = box.get("min_z")
        max_z = box.get("max_z")
        if None in (min_y, max_y, min_z, max_z):
            continue
        min_x = box.get("min_x")
        max_x = box.get("max_x")
        in_x = (min_x is None or x_mm >= min_x) and (max_x is None or x_mm <= max_x)
        if in_x and min_y <= y <= max_y and min_z <= z <= max_z:
            return name
    return None


def _fmt_m(mm: float) -> str:
    return _fmt(mm / 1000.0)


def _fmt_int(value: float) -> str:
    return str(int(round(value)))


def _fmt(value: float) -> str:
    return f"{value:g}"


def _same_point(a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    return _distance(a, b) <= tol


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(b[0] - a[0], b[1] - a[1])


def _projection(
    point: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> tuple[float, float]:
    vx = p2[0] - p1[0]
    vz = p2[1] - p1[1]
    length_sq = vx * vx + vz * vz
    if length_sq <= 0.0:
        return (0.0, _distance(point, p1))

    t = ((point[0] - p1[0]) * vx + (point[1] - p1[1]) * vz) / length_sq
    t = max(0.0, min(1.0, t))
    projected = (p1[0] + t * vx, p1[1] + t * vz)
    return (t, _distance(point, projected))


def _arc_station_on_segment(
    plate: SectionPlate,
    p1: tuple[float, float],
    p2: tuple[float, float],
    point: tuple[float, float],
    seg_len: float,
) -> float:
    radius = abs(plate.radius_mm or 0.0)
    if radius <= 0.0:
        return 0.0

    cy = plate.arc_center_y_mm
    cz = plate.arc_center_z_mm
    if cy is None or cz is None:
        return 0.0

    query_radius = _distance((cy, cz), point)
    if query_radius <= 0.0:
        return 0.0

    start_angle = atan2(p1[1] - cz, p1[0] - cy)
    end_angle = atan2(p2[1] - cz, p2[0] - cy)
    query_angle = atan2(point[1] - cz, point[0] - cy)

    total = _minor_sweep(start_angle, end_angle)
    query_delta = _minor_sweep(start_angle, query_angle)
    swept = query_delta if total >= 0.0 else -query_delta

    theta_total = min(abs(total), seg_len / radius if radius > 0.0 else 0.0)
    swept = max(0.0, min(theta_total, swept))
    return radius * swept


def _minor_sweep(start_angle: float, end_angle: float) -> float:
    delta = (end_angle - start_angle) % tau
    if delta > pi:
        delta -= tau
    return delta
