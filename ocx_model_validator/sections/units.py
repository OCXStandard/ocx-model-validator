"""Convert IR quantities/points to the target units: mm, MPa, m3.

The OCX unit_registry (IrUnit.to_si_factor) is authoritative; a small
fallback table covers models that omit the units section. A blank unit
string means the value is already SI.
"""
from __future__ import annotations

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import IrUnit, Quantity
from ocx_model_validator.model.ir.geometry import IrPoint3D

_FALLBACK_SI = {
    "": 1.0,
    "Um": 1.0,
    "Umm": 1e-3,
    "Ucm": 1e-2,
    "Um3": 1.0,
    "UPa": 1.0,
    "UMPa": 1e6,
    "Ukg": 1.0,
    "Ut": 1e3,
}


def to_si(qty: Quantity, registry: dict[str, IrUnit]) -> float:
    """Return the SI value of qty using registry, falling back to _FALLBACK_SI."""
    unit = qty.unit or ""
    entry = registry.get(unit)
    if entry is not None and entry.to_si_factor is not None:
        return qty.value * entry.to_si_factor
    if unit in _FALLBACK_SI:
        return qty.value * _FALLBACK_SI[unit]
    raise GeometryError(f"Unknown unit id {unit!r}; cannot convert to SI")


def qty_mm(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) * 1000.0


def qty_mpa(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) / 1e6


def qty_m3(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry)


def point_mm(p: IrPoint3D, registry: dict[str, IrUnit]) -> tuple[float, float, float]:
    """Convert an IrPoint3D to an (x, y, z) tuple in millimetres."""
    unit = getattr(p, "unit", "") or ""
    f = 1000.0 * to_si(Quantity(1.0, unit), registry)
    return (p.x * f, p.y * f, p.z * f)
