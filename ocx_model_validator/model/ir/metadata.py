"""Typed vessel metadata IR types."""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.model.ir.base import Quantity


@dataclass(frozen=True)
class IrShipDesignation:
    vessel_name: str | None = None
    imo_number: str | None = None
    call_sign: str | None = None
    flag_state: str | None = None


@dataclass(frozen=True)
class IrTonnageData:
    gross_tonnage: Quantity | None = None
    net_tonnage: Quantity | None = None


@dataclass(frozen=True)
class IrPrincipalParticulars:
    lpp: Quantity | None = None
    moulded_breadth: Quantity | None = None
    moulded_depth: Quantity | None = None
    design_speed: Quantity | None = None
    displacement: Quantity | None = None
    deadweight: Quantity | None = None
    block_coefficient: Quantity | None = None
    scantling_draught: Quantity | None = None
    normal_ballast_draught: Quantity | None = None
    heavy_ballast_draught: Quantity | None = None


@dataclass(frozen=True)
class IrStatutoryData:
    freeboard_type: str | None = None
    freeboard_length: Quantity | None = None
    upper_deck_area: Quantity | None = None
    tonnage_data: IrTonnageData | None = None


@dataclass(frozen=True)
class IrBuilderInformation:
    builder_name: str | None = None
    yard_number: str | None = None
    delivery_date: str | None = None
