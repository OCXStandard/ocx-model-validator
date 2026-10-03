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
    """Schema-neutral material record.

    ``material_type`` is ``"steel"`` / ``"aluminium"`` for OCX 3.2.0
    catalogues and ``None`` for legacy 3.0/3.1 ``Material`` entries.
    The welded/unwelded strength fields and ``alloy_designation`` are
    aluminium-specific (3.2.0); ``grade``/``yield_stress``/``ultimate_stress``
    are steel/legacy fields.
    """
    id: str
    name: str | None = None
    guidref: str | None = None
    material_type: str | None = None  # "steel" | "aluminium" | None
    grade: str | None = None
    density: Quantity | None = None
    yield_stress: Quantity | None = None
    ultimate_stress: Quantity | None = None
    youngs_modulus: Quantity | None = None
    poisson_ratio: Quantity | None = None
    thermal_expansion: Quantity | None = None
    unwelded_yield_strength: Quantity | None = None
    welded_yield_strength: Quantity | None = None
    unwelded_tensile_strength: Quantity | None = None
    welded_tensile_strength: Quantity | None = None
    alloy_designation: str | None = None


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
