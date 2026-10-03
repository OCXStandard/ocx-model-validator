"""Shared unit-conversion and formatting helpers for report generators.

All helpers degrade gracefully: missing quantities become None (rendered as
an empty cell) and unknown units become a raw ``"<value> <unit>"`` string
plus a note — generators never raise on bad units.
"""
from __future__ import annotations

from datetime import datetime

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import IrUnit, ParentKind, ParentRef, Quantity
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.model.units import to_si
from ocx_model_validator.reporting.model import Cell


def _safe_convert(
    qty: Quantity | None,
    registry: dict[str, IrUnit],
    si_scale: float,
    digits: int,
    notes: list[str],
    context: str,
) -> Cell:
    if qty is None:
        return None
    try:
        return round(to_si(qty, registry) * si_scale, digits)
    except GeometryError:
        notes.append(f"{context}: unknown unit {qty.unit!r}; raw value shown")
        return f"{qty.value} {qty.unit}"


def qty_mm_cell(qty, registry, notes, context) -> Cell:
    """SI metres → mm, 1 decimal."""
    return _safe_convert(qty, registry, 1e3, 1, notes, context)


def qty_mpa_cell(qty, registry, notes, context) -> Cell:
    """SI Pa → MPa, integer."""
    cell = _safe_convert(qty, registry, 1e-6, 0, notes, context)
    return int(cell) if isinstance(cell, float) else cell


def qty_m3_cell(qty, registry, notes, context) -> Cell:
    """SI m³ → m³, 2 decimals."""
    return _safe_convert(qty, registry, 1.0, 2, notes, context)


def qty_m2_cell(qty, registry, notes, context) -> Cell:
    """SI m² → m², 2 decimals."""
    return _safe_convert(qty, registry, 1.0, 2, notes, context)


def xyz_m_cells(x: float, y: float, z: float, unit: str, registry,
                notes, context) -> list[Cell]:
    """Three coordinate cells in metres, 3 decimals."""
    return [_safe_convert(Quantity(v, unit), registry, 1.0, 3, notes,
                          f"{context} {axis}")
            for axis, v in (("x", x), ("y", y), ("z", z))]


def qty_tonnes_cell(qty, registry, notes, context) -> Cell:
    """SI kg → tonnes, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def qty_t_per_m3_cell(qty, registry, notes, context) -> Cell:
    """SI kg/m³ → t/m³, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def inherited_function_cell(own: str | None, parent_ref: ParentRef | None,
                            vessel: IrVessel) -> Cell:
    """Effective functionType of a panel child.

    Panel children inherit the panel's functionType; a child override wins.
    An inherited value is shown in parentheses, an override plain.
    """
    if own:
        return own
    if parent_ref is not None and parent_ref.kind == ParentKind.PANEL:
        panel = vessel.panels.get(parent_ref.id)
        if panel is not None and panel.function_type:
            return f"({panel.function_type})"
    return None


def report_metadata(vessel: IrVessel, source_file: str) -> dict[str, str]:
    """Standard report metadata block."""
    return {
        "Vessel": vessel.name or vessel.id,
        "Schema version": vessel.schema_version,
        "Source": source_file,
        "Generated": datetime.now().isoformat(timespec="seconds"),
    }
