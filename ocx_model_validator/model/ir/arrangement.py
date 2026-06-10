"""Arrangement IR types — compartments, spaces, cargoes, design-view tree."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity, Ref


@dataclass
class IrCompartment:
    """Schema-neutral compartment record."""
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_purpose: str | None = None
    volume: Quantity | None = None
    filling_height: Quantity | None = None
    face_refs: list[Ref] = field(default_factory=list)
    cog: Quantity | None = None


@dataclass
class IrPhysicalSpace:
    """Schema-neutral physical space record."""
    id: str
    name: str | None = None
    guidref: str | None = None
    space_type: str | None = None


# ---------------------------------------------------------------------------
# Cargo types
# ---------------------------------------------------------------------------

@dataclass
class IrLiquidCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    filling_height: Quantity | None = None
    permeability: Quantity | None = None


@dataclass
class IrGaseousCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    carriage_pressure: Quantity | None = None


@dataclass
class IrBulkCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    stowage_factor: Quantity | None = None
    stowage_height: Quantity | None = None
    angle_of_repose: Quantity | None = None


@dataclass
class IrUnitCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None


# ---------------------------------------------------------------------------
# Design view — recursive product tree
# ---------------------------------------------------------------------------

@dataclass
class IrOccurrence:
    id: str
    name: str | None = None
    guidref: str | None = None
    definition_ref: Ref | None = None
    transformation: dict | None = None  # raw geometry transform


@dataclass
class IrOccurrenceGroup:
    """Can nest IrOccurrenceGroup and IrOccurrence at any depth."""
    id: str
    name: str | None = None
    guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)


@dataclass
class IrDesignView:
    id: str
    name: str | None = None
    guidref: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)
