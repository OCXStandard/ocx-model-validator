"""Shared unit-conversion and formatting helpers for report generators.

All helpers degrade gracefully: missing quantities become None (rendered as
an empty cell) and unknown units become a raw ``"<value> <unit>"`` string
plus a note — generators never raise on bad units.
"""
from __future__ import annotations

from datetime import datetime

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
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


def qty_tonnes_cell(qty, registry, notes, context) -> Cell:
    """SI kg → tonnes, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def qty_t_per_m3_cell(qty, registry, notes, context) -> Cell:
    """SI kg/m³ → t/m³, 3 decimals."""
    return _safe_convert(qty, registry, 1e-3, 3, notes, context)


def report_metadata(vessel: IrVessel, source_file: str) -> dict[str, str]:
    """Standard report metadata block."""
    return {
        "Vessel": vessel.name or vessel.id,
        "Schema version": vessel.schema_version,
        "Source": source_file,
        "Generated": datetime.now().isoformat(timespec="seconds"),
    }
