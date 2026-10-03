"""Compartments report generator — reuses build_compartments_block.

Includes cargo information: the main table carries the cargo types
assigned to each compartment and a Cargoes table lists all cargo
attributes and properties per compartment.
"""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError, SectionError
from ocx_model_validator.frame_table import FrameTable, build_frame_table
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_kpa_cell,
    qty_t_per_m3_cell,
    report_metadata,
)
from ocx_model_validator.reporting.generators._compartment_data import build_compartments_block
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

_COLUMNS = [
    "Name", "Tank type", "Cargo type", "Volume (m³)",
    "COG x (mm)", "COG y (mm)", "COG z (mm)",
    "min x (frame)", "max x (frame)", "min y (mm)", "max y (mm)", "min z (mm)", "max z (mm)",
    "Filling height (mm)", "Air pipe height (mm)", "Relief valve pressure (kPa)",
]

_CARGO_COLUMNS = [
    "Compartment", "Kind", "Cargo type", "Density (t/m³)",
    "Carriage pressure (kPa)", "Liquid state", "Stowage factor",
    "Permeability", "Angle of repose",
]

_FRAME_TOL_MM = 0.5


def _frame_pos(x_mm: float | None, ft: FrameTable | None) -> Cell:
    """Render an x position as '#<frame>' plus/minus the offset in mm."""
    if x_mm is None or ft is None:
        return x_mm
    label, frame_x = ft.nearest_frame(x_mm)
    offset = x_mm - frame_x
    if abs(offset) < _FRAME_TOL_MM:
        return f"#{label}"
    sign = "+" if offset >= 0 else "-"
    return f"#{label}{sign}{abs(round(offset, 1)):g}"


def _raw_qty_cell(q: Quantity | None) -> Cell:
    """Value as-is; unit id appended when present (no SI target defined)."""
    if q is None:
        return None
    return q.value if not q.unit else f"{q.value} {q.unit}"


def _cargoes_by_compartment(vessel: IrVessel) -> dict[str, list[tuple[str, object]]]:
    """Map compartment id → [(kind, cargo), …] preserving kind order."""
    result: dict[str, list[tuple[str, object]]] = {}
    for kind, coll in (("Liquid", vessel.liquid_cargoes),
                       ("Gaseous", vessel.gaseous_cargoes),
                       ("Bulk", vessel.bulk_cargoes),
                       ("Unit", vessel.unit_cargoes)):
        for c in coll.values():
            if c.compartment_ref is None:
                continue
            result.setdefault(c.compartment_ref.local_ref, []).append((kind, c))
    return result


def _cargo_type_cell(cargoes: list[tuple[str, object]]) -> Cell:
    types = [c.cargo_type for _, c in cargoes if c.cargo_type]
    return ", ".join(dict.fromkeys(types)) if types else None


def _cargo_rows(vessel: IrVessel, by_comp: dict[str, list[tuple[str, object]]],
                notes: list[str]) -> list[list[Cell]]:
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for cid in sorted(by_comp,
                      key=lambda cid: (vessel.compartments.get(cid).name
                                       if vessel.compartments.get(cid) else cid) or cid):
        comp = vessel.compartments.get(cid)
        comp_name = (comp.name or comp.id) if comp is not None else cid
        for kind, c in by_comp[cid]:
            ctx = f"cargo {c.id}"
            rows.append([
                comp_name, kind, c.cargo_type,
                qty_t_per_m3_cell(getattr(c, "density", None), reg, notes,
                                  f"{ctx} density"),
                qty_kpa_cell(getattr(c, "carriage_pressure", None), reg,
                             notes, f"{ctx} carriage pressure"),
                "yes" if getattr(c, "liquid_state", False) else None,
                _raw_qty_cell(getattr(c, "stowage_factor", None)),
                _raw_qty_cell(getattr(c, "permeability", None)),
                _raw_qty_cell(getattr(c, "angle_of_repose", None)),
            ])
    return rows


def build(vessel: IrVessel, source_file: str = "") -> Report:
    raw_rows, warnings = build_compartments_block(vessel)
    try:
        ft: FrameTable | None = build_frame_table(vessel)
    except (GeometryError, SectionError):
        ft = None
    rows: list[list[Cell]] = []
    by_comp = _cargoes_by_compartment(vessel)
    for r in sorted(raw_rows, key=lambda r: r["name"]):
        cog = r.get("cog_mm") or [None, None, None]
        ext = r.get("extent_mm") or {}
        rows.append([
            r.get("name"), r.get("tank_type"),
            _cargo_type_cell(by_comp.get(r.get("id"), [])),
            r.get("volume_m3"),
            cog[0], cog[1], cog[2],
            _frame_pos(ext.get("min_x"), ft), _frame_pos(ext.get("max_x"), ft),
            ext.get("min_y"), ext.get("max_y"),
            ext.get("min_z"), ext.get("max_z"),
            r.get("filling_height_mm"), r.get("air_pipe_height_mm"),
            r.get("relief_valve_pressure_kpa"),
        ])
    notes = list(warnings)
    section = ReportSection(
        title="Compartments",
        tables=[ReportTable("Compartments", _COLUMNS, rows),
                ReportTable("Cargoes", _CARGO_COLUMNS,
                            _cargo_rows(vessel, by_comp, notes))],
        notes=notes,
    )
    return Report(title="Compartments report",
                  metadata=report_metadata(vessel, source_file),
                  sections=[section])
