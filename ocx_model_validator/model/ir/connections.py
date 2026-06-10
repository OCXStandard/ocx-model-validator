"""Connection IR types.

These are intentionally minimal placeholders.  The full connection-
configuration model is deferred to a future design.  ``structural.py`` imports
``IrPenetration`` from here; this module must NOT import from ``structural.py``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IrConnectionConfiguration:
    """Placeholder — full definition in a future design."""
    id: str
    name: str | None = None


@dataclass
class IrPenetration(IrConnectionConfiguration):
    """Stiffener penetration — subtype of IrConnectionConfiguration. Placeholder."""
    pass
