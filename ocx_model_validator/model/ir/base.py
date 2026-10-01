"""Shared primitive / value types for the schema-neutral IR."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Primitive / shared value types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IrCog:
    """Centre of gravity as a 3D point in model coordinates.

    ``unit`` carries the raw OCX unit id (e.g. ``'Um'`` for metres, ``'Umm'``
    for millimetres) matching the ``unit=`` attribute on the OCX
    ``<CenterOfGravity>`` element.
    """
    x: float
    y: float
    z: float
    unit: str  # OCX unit id, e.g. 'Um'

    def __repr__(self) -> str:
        return f"IrCog({self.x}, {self.y}, {self.z} [{self.unit}])"


@dataclass(frozen=True)
class Quantity:
    """A physical quantity — value + unit string."""
    value: float
    unit: str

    def __repr__(self) -> str:
        return f"{self.value} {self.unit}"


@dataclass(frozen=True)
class IrUnit:
    """Schema-neutral representation of a single UnitsML ``<Unit>`` entry.

    The ``to_si_factor`` converts a raw OCX quantity value to the coherent SI
    base-unit value::

        si_value = raw_value * ir_unit.to_si_factor

    Examples::

        IrUnit(id='Umm',  symbol='mm', to_si_factor=1e-3,  si_symbol='m')
        IrUnit(id='UKg',  symbol='kg', to_si_factor=1.0,   si_symbol='kg')
        IrUnit(id='UNOvermm2', symbol='N/mm2', to_si_factor=1e6, si_symbol='Pa')

    The ``id`` matches the ``id`` attribute on the OCX ``<Unit>`` element,
    which is also the value stored in all OCX quantity ``unit=`` attributes.
    """
    id: str                    # OCX unit id  (e.g. 'Umm')
    name: str                  # human-readable name (e.g. 'millimeter')
    symbol: str                # unit symbol (e.g. 'mm')
    dimension_url: str | None  # UnitsML dimension URL (e.g. 'D_L')
    to_si_factor: float        # multiply value × this to get SI base unit
    si_symbol: str             # SI base-unit symbol (e.g. 'm', 'kg', 'Pa')


@dataclass(frozen=True)
class Ref:
    """A reference to another structural part by XML id and/or GUIDRef."""
    local_ref: str
    guidref: str | None = None

    def __repr__(self) -> str:
        if self.guidref:
            return f"Ref({self.local_ref!r}, guid={self.guidref!r})"
        return f"Ref({self.local_ref!r})"


class ParentKind(str, Enum):
    VESSEL = "vessel"
    PANEL = "panel"


@dataclass(frozen=True)
class ParentRef:
    """Reference to the parent container of a structural part."""
    kind: ParentKind
    id: str  # id of the parent vessel or panel

    def __repr__(self) -> str:
        return f"ParentRef({self.kind.value}:{self.id!r})"
