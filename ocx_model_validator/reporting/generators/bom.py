"""Bill-of-material report generator.

Grouping hierarchy: material → part type → sub-group (thickness for plates
and brackets, cross-section for stiffeners and edge reinforcements). Items
without dry_weight show N/A, are excluded from totals, and are counted per
group in the "Missing weight" column.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable
from ocx_model_validator.sections.units import to_si

_NO_MATERIAL = "(no material)"
_NO_SECTION = "(no section)"

# (display name, IrVessel dict attribute, sub-group kind)
_PART_TYPES = [
    ("Plate", "plates", "thickness"),
    ("Stiffener", "stiffeners", "section"),
    ("Edge reinforcement", "edge_reinforcements", "section"),
    ("Bracket", "brackets", "thickness"),
]


@dataclass
class _Group:
    count: int = 0
    weight_t: float = 0.0
    missing: int = 0
    items: list[tuple[str, str | None, float | None]] = field(default_factory=list)
    # items: (id, name, weight_t or None)


def _material_name(part, vessel: IrVessel) -> str:
    ref = part.material_ref
    if ref is None:
        return _NO_MATERIAL
    m = vessel.materials.get(ref.local_ref)
    if m is None:
        return _NO_MATERIAL
    return m.name or m.grade or m.id


def _group_key(part, kind: str, vessel: IrVessel, notes: list[str]) -> str:
    if kind == "thickness":
        mm = qty_mm_cell(part.thickness, vessel.unit_registry, notes,
                         f"{part.id} thickness")
        if isinstance(mm, (int, float)):
            return f"t={mm} mm"
        return f"t={mm}" if mm is not None else "t=N/A"
    ref = part.section_ref
    if ref is None:
        return _NO_SECTION
    s = vessel.sections.get(ref.local_ref)
    return (s.name or s.id) if s is not None else ref.local_ref


def _weight_tonnes(part, vessel: IrVessel, notes: list[str]) -> float | None:
    if part.dry_weight is None:
        return None
    try:
        return to_si(part.dry_weight, vessel.unit_registry) / 1000.0
    except GeometryError:
        notes.append(f"{part.id} dry_weight: unknown unit "
                     f"{part.dry_weight.unit!r}; excluded from totals")
        return None


def build(vessel: IrVessel, detailed: bool = False, source_file: str = "") -> Report:
    notes: list[str] = []
    groups: dict[tuple[str, str, str], _Group] = {}

    for part_type, attr, kind in _PART_TYPES:
        for part in getattr(vessel, attr).values():
            key = (_material_name(part, vessel), part_type,
                   _group_key(part, kind, vessel, notes))
            g = groups.setdefault(key, _Group())
            w = _weight_tonnes(part, vessel, notes)
            g.count += 1
            if w is None:
                g.missing += 1
            else:
                g.weight_t += w
            g.items.append((part.id, part.name, w))

    rows: list[list[Cell]] = []
    total_count = total_missing = 0
    total_weight = 0.0
    current_material: str | None = None
    sub_count = sub_missing = 0
    sub_weight = 0.0

    def _flush_subtotal() -> None:
        if current_material is not None:
            rows.append([f"Subtotal — {current_material}", None, None,
                         sub_count, round(sub_weight, 3), sub_missing])

    for (material, part_type, group), g in sorted(groups.items()):
        if material != current_material:
            _flush_subtotal()
            current_material = material
            sub_count = sub_missing = 0
            sub_weight = 0.0
        rows.append([material, part_type, group,
                     g.count, round(g.weight_t, 3), g.missing])
        sub_count += g.count
        sub_weight += g.weight_t
        sub_missing += g.missing
        total_count += g.count
        total_weight += g.weight_t
        total_missing += g.missing
    _flush_subtotal()

    if total_missing:
        notes.append(f"{total_missing} item(s) missing dry weight; "
                     f"excluded from all totals")

    summary = ReportTable(
        title="Summary",
        columns=["Material", "Part type", "Group", "Count",
                 "Weight (t)", "Missing weight"],
        rows=rows,
        footer_rows=[["Grand total", None, None,
                      total_count, round(total_weight, 3), total_missing]],
    )
    tables = [summary]

    if detailed:
        item_rows: list[list[Cell]] = []
        for (material, part_type, group), g in sorted(groups.items()):
            for item_id, name, w in sorted(g.items, key=lambda it: it[0]):
                item_rows.append([material, part_type, group, item_id, name,
                                  round(w, 3) if w is not None else None])
        tables.append(ReportTable(
            title="Items",
            columns=["Material", "Part type", "Group", "Id", "Name", "Weight (t)"],
            rows=item_rows,
        ))

    notes[:] = list(dict.fromkeys(notes))
    section = ReportSection(title="Bill of material", tables=tables, notes=notes)
    return Report(title="Bill of material report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
