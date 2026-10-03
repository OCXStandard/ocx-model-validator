"""Arrangement IR types — compartments, spaces, cargoes, design-view tree."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import IrCog, Quantity, Ref


@dataclass
class IrCompartment:
    """Schema-neutral compartment record."""
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_purpose: str | None = None
    volume: Quantity | None = None
    filling_height: Quantity | None = None
    air_pipe_height: Quantity | None = None
    relief_valve_pressure: Quantity | None = None
    face_refs: list[Ref] = field(default_factory=list)
    face_boundary_curves: list = field(default_factory=list)  # IrCurve3D per face
    cog: IrCog | None = None


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
    carriage_pressure: Quantity | None = None


@dataclass
class IrGaseousCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    carriage_pressure: Quantity | None = None
    liquid_state: bool = False


@dataclass
class IrBulkCargo:
    id: str
    name: str | None = None
    guidref: str | None = None
    compartment_ref: Ref | None = None
    cargo_type: str | None = None
    density: Quantity | None = None
    stowage_factor: Quantity | None = None
    permeability: Quantity | None = None
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
    type_value: str | None = None
    plate_ref: Ref | None = None
    stiffener_ref: Ref | None = None
    seam_ref: Ref | None = None
    bracket_ref: Ref | None = None
    pillar_ref: Ref | None = None
    hole_contour_ref: Ref | None = None
    edge_reinforcement_ref: Ref | None = None
    lug_plate_ref: Ref | None = None
    connected_bracket_ref: Ref | None = None


@dataclass
class IrOccurrenceGroup:
    """Can nest IrOccurrenceGroup and IrOccurrence at any depth."""
    id: str
    name: str | None = None
    type_value: str | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)


@dataclass
class IrDesignView:
    id: str
    name: str | None = None
    guidref: str | None = None
    vessel_ref: Ref | None = None
    children: list[IrOccurrenceGroup | IrOccurrence] = field(default_factory=list)
