"""Typed vessel metadata IR types."""
from __future__ import annotations

from dataclasses import dataclass

from ocx_model_validator.model.ir.base import Quantity


@dataclass(frozen=True)
class IrHeader:
    """OCX <Header> document metadata."""
    time_stamp: str | None = None
    name: str | None = None
    author: str | None = None
    organization: str | None = None
    originating_system: str | None = None
    application_version: str | None = None
    documentation: str | None = None


@dataclass(frozen=True)
class IrShipDesignation:
    ship_name: str | None = None
    call_sign: str | None = None
    number_imo: str | None = None
    ship_type: str | None = None


@dataclass(frozen=True)
class IrTonnageData:
    tonnage: Quantity | None = None
    dead_weight: Quantity | None = None


@dataclass(frozen=True)
class IrPrincipalParticulars:
    lpp: Quantity | None = None
    rule_length: Quantity | None = None
    block_coefficient: Quantity | None = None
    moulded_breadth: Quantity | None = None
    moulded_depth: Quantity | None = None
    scantling_draught: Quantity | None = None
    design_speed: Quantity | None = None
    freeboard_length: Quantity | None = None
    normal_ballast_draught: Quantity | None = None
    heavy_ballast_draught: Quantity | None = None
    minimum_ballast_draught: Quantity | None = None
    length_of_waterline: Quantity | None = None
    upper_deck_area: Quantity | None = None
    freeboard_type: str | None = None


@dataclass(frozen=True)
class IrStatutoryData:
    port_registration: str | None = None
    flag_state: str | None = None


@dataclass(frozen=True)
class IrBuilderInformation:
    yard: str | None = None
    designer: str | None = None
    owner: str | None = None
    year_of_build: str | None = None
