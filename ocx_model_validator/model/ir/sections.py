"""Section catalogue IR types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocx_model_validator.model.ir.base import Quantity


@dataclass
class IrSection:
    """Base class for cross-section definitions."""
    id: str
    name: str | None = None
    guidref: str | None = None
    section_type: str | None = None  # normalised type string, e.g. "FlatBar"
    catalogue_reference: str | None = None  # BarSection catalogueReference (3.2.0)

@dataclass
class IrRectangularTubeSection(IrSection):
    """Rectangular hollow profile."""
    height: Quantity | None = None
    width: Quantity | None = None
    thickness: Quantity | None = None

@dataclass
class IrOctagonSection(IrSection):
    """Octagon solid bar profile / tube."""
    height: Quantity | None = None

@dataclass
class IrSquareSection(IrSection):
    """Square bar profile."""
    height: Quantity | None = None

@dataclass
class IrBulbFlatSection(IrSection):
    """Bulb flat section (HP profile)."""
    height: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_width: Quantity | None = None
    bulb_angle: Quantity | None = None
    bulb_outer_radius: Quantity | None = None
    bulb_inner_radius: Optional[Quantity] | None = None
    bulb_top_radius: Optional[Quantity] | None = None
    bulb_bottom_radius: Optional[Quantity] | None = None


@dataclass
class IrFlatBarSection(IrSection):
    """Flat bar"""
    height: Quantity | None = None   # flat bar height
    width: Quantity | None = None

@dataclass
class IrUSection(IrSection):
    """U profile."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None

@dataclass
class IrISection(IrSection):
    """I profile."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None

@dataclass
class IrLSectionOvershootFlange(IrSection):
    """Welded angle bar with overshoot flange."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None
    overshoot: Quantity | None = None

@dataclass
class IrZSection(IrSection):
    """Z-section."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None

@dataclass
class IrRoundSection(IrSection):
    """Round bar."""
    diameter: Quantity | None = None

@dataclass
class IrLSection(IrSection):
    """L / angle section with two unequal legs."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None


@dataclass
class IrTSection(IrSection):
    """T-section (symmetric)."""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None

@dataclass
class IrLSectionOvershootWeb(IrSection):
    """Angle bar with an overshoot web"""
    height: Quantity | None = None
    width: Quantity | None = None
    web_thickness: Quantity | None = None
    flange_thickness: Quantity | None = None
    overshoot: Quantity | None = None


@dataclass
class IrHalfRoundSection(IrSection):
    """Half round bar"""
    diameter: Quantity | None = None


@dataclass
class IrHexagonSection(IrSection):
    """Hexagon solid bar profile"""
    height: Quantity | None = None


@dataclass
class IrAngleSection(IrSection):
    """Equal-leg angle section."""
    leg_length: Quantity | None = None
    leg_thickness: Quantity | None = None


@dataclass
class IrTubeSection(IrSection):
    """Circular hollow profile / tube."""
    diameter: Quantity | None = None
    thickness: Quantity | None = None


@dataclass
class IrGenericSection(IrSection):
    """Catch-all for section types not yet mapped to a typed subclass.

    All extracted scalar fields from the raw OCX section dataclass are stored
    in ``extra`` so no data is silently dropped.
    """
    extra: dict[str, Any] = field(default_factory=dict)
