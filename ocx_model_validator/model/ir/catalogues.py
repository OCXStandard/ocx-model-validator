"""Catalogue IR types — materials and hole shapes."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.geometry import IrCurve3D


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

@dataclass
class IrMaterial:
    """Schema-neutral material record."""
    id: str
    name: str | None = None
    guidref: str | None = None
    grade: str | None = None
    density: Quantity | None = None
    yield_stress: Quantity | None = None
    ultimate_stress: Quantity | None = None
    youngs_modulus: Quantity | None = None
    poisson_ratio: Quantity | None = None
    thermal_expansion: Quantity | None = None


# ---------------------------------------------------------------------------
# Hole shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IrHole2D:
    """Hole shape definition from HoleShapeCatalogue."""
    id: str
    name: str | None = None
    guidref: str | None = None
    contour: IrCurve3D | None = None
    parametric: dict | None = None


@dataclass
class IrHoleShapeCatalogue:
    id: str
    name: str | None = None
    holes: dict[str, IrHole2D] = field(default_factory=dict)
