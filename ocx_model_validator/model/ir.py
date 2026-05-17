"""Schema-neutral Intermediate Representation (IR) dataclasses for OCX models.

These types are completely independent of any OCX schema version.  Builders
(ocx_agent/builders/) translate versioned OCX xsdata dataclasses into these
types.  OcxSession and all agent tools work exclusively with IR types.

Design decisions:
- Every optional field defaults to ``None`` or ``[]`` — no field access ever
  raises AttributeError.
- ``IrVessel`` is the single root.  All structural parts (plates, brackets,
  stiffeners, pillars, sections, materials) are stored in flat dicts keyed by
  ``id`` so look-up is O(1) and duplicate / dangling-ref detection is trivial.
- ``IrPanel`` holds *id references* to its children, not the objects themselves.
- Every child part carries a ``parent_ref: ParentRef`` pointing either to its
  containing panel or directly to the vessel when not nested inside a panel.
- Section types are modelled as typed subtypes of ``IrSection`` so callers can
  ``isinstance``-dispatch on section geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


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
# Sections — typed hierarchy
# ---------------------------------------------------------------------------

@dataclass
class IrSection:
    """Base class for cross-section definitions."""
    id: str
    name: str | None = None
    guidref: str | None = None
    section_type: str | None = None  # normalised type string, e.g. "FlatBar"

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


# ---------------------------------------------------------------------------
# Structural parts
# ---------------------------------------------------------------------------

@dataclass
class IrPlate:
    """Schema-neutral plate record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    thickness: Quantity | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    net_area: Quantity | None = None
    function_type: str | None = None


@dataclass
class IrBracket:
    """Schema-neutral bracket record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    thickness: Quantity | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    arm_length_u: Quantity | None = None
    arm_length_v: Quantity | None = None
    has_edge_reinforcement: bool = False
    number_of_supports: int | None = None


@dataclass
class IrStiffener:
    """Schema-neutral stiffener record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    function_type: str | None = None


@dataclass
class IrPillar:
    """Schema-neutral pillar record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    cog: IrCog | None = None
    function_type: str | None = None


@dataclass
class IrEdgeReinforcement:
    """Schema-neutral edge reinforcement record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    function_type: str | None = None


# ---------------------------------------------------------------------------
# Panel limit reference
# ---------------------------------------------------------------------------

@dataclass
class IrLimitedByRef:
    """A single boundary reference from a panel's LimitedBy collection.

    ``ref_type`` carries the normalised OCX element name so consumers can
    filter or group by boundary type without isinstance dispatch:

        "PanelRef" | "StiffenerRef" | "SeamRef" | "SurfaceRef"
        | "EdgeCurveRef" | "GridRef" | "EdgeReinforcementRef"
        | "FreeEdgeCurve3D"

    ``local_ref`` is the XML IDREF value pointing to the referenced element.
    ``guidref``   is the GUID of the referenced element.
    ``ocx_ref_type`` is the raw ``refType`` attribute from the OCX schema
        element itself (e.g. ``"ocx:PanelRef"``), preserved for look-up
        and round-trip fidelity.  ``None`` when not present (FreeEdgeCurve3D).
    """
    ref_type: str          # normalised element name, e.g. "PanelRef"
    local_ref: str         # XML IDREF value (may be empty string)
    guidref: str | None = None
    ocx_ref_type: str | None = None  # raw refType attribute from OCX schema

    def as_ref(self) -> "Ref":
        """Return a plain Ref for backward-compatible look-ups."""
        return Ref(local_ref=self.local_ref, guidref=self.guidref)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

@dataclass
class IrPanel:
    """Schema-neutral panel record.

    Children are stored as **id references** into the flat dicts on
    ``IrVessel``.  This allows O(1) look-up and makes reference integrity
    checks straightforward.

    ``limited_by`` collects *all* boundary references from the OCX
    ``LimitedBy`` element, tagged with their OCX element type via
    ``IrLimitedByRef.ref_type``.  Use ``panel_refs`` / ``stiffener_refs``
    etc. convenience properties to filter by type.

    ``ref_type`` values: ``"PanelRef"`` | ``"StiffenerRef"`` | ``"SeamRef"``
    | ``"SurfaceRef"`` | ``"EdgeCurveRef"`` | ``"GridRef"``
    | ``"EdgeReinforcementRef"`` | ``"FreeEdgeCurve3D"``

    For ``FreeEdgeCurve3D`` entries ``local_ref`` holds the curve ``name``
    (may be empty) and ``guidref`` holds its GUIDRef.
    """
    id: str
    name: str | None = None
    guidref: str | None = None
    function_type: str | None = None
    tightness: str | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    # Child part id references (into IrVessel dicts)
    plate_ids: list[str] = field(default_factory=list)
    bracket_ids: list[str] = field(default_factory=list)
    stiffener_ids: list[str] = field(default_factory=list)
    pillar_ids: list[str] = field(default_factory=list)
    edge_reinforcement_ids: list[str] = field(default_factory=list)
    # All boundary references, each tagged with ref_type
    limited_by: list[IrLimitedByRef] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Typed filter helpers
    # ------------------------------------------------------------------

    def _refs_of_type(self, ref_type: str) -> list[IrLimitedByRef]:
        return [r for r in self.limited_by if r.ref_type == ref_type]

    @property
    def panel_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("PanelRef")

    @property
    def stiffener_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("StiffenerRef")

    @property
    def seam_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("SeamRef")

    @property
    def surface_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("SurfaceRef")

    @property
    def edge_curve_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("EdgeCurveRef")

    @property
    def grid_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("GridRef")

    @property
    def edge_reinforcement_refs(self) -> list[IrLimitedByRef]:
        return self._refs_of_type("EdgeReinforcementRef")

    @property
    def free_edge_curve_refs(self) -> list[IrLimitedByRef]:
        """Inline FreeEdgeCurve3D geometry elements forming the panel boundary."""
        return self._refs_of_type("FreeEdgeCurve3D")


# ---------------------------------------------------------------------------
# Arrangement
# ---------------------------------------------------------------------------

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
# Vessel — the root IR object
# ---------------------------------------------------------------------------

@dataclass
class IrVessel:
    """Root IR object.  Contains the complete schema-neutral model.

    Flat look-up dicts:
        panels, plates, brackets, stiffeners, pillars, materials, sections,
        compartments, physical_spaces

    All dicts are keyed by the component's ``id`` field.  Builders are
    responsible for detecting and logging duplicate ids.
    """
    id: str
    name: str | None = None
    schema_version: str = "unknown"

    # --- unit registry (keyed by OCX unit id, e.g. 'Umm') ---
    unit_registry: dict[str, IrUnit] = field(default_factory=dict)

    # --- structural part dicts (keyed by id) ---
    panels: dict[str, IrPanel] = field(default_factory=dict)
    plates: dict[str, IrPlate] = field(default_factory=dict)
    brackets: dict[str, IrBracket] = field(default_factory=dict)
    stiffeners: dict[str, IrStiffener] = field(default_factory=dict)
    pillars: dict[str, IrPillar] = field(default_factory=dict)
    edge_reinforcements: dict[str, IrEdgeReinforcement] = field(default_factory=dict)

    # --- catalogue dicts (keyed by id) ---
    materials: dict[str, IrMaterial] = field(default_factory=dict)
    sections: dict[str, IrSection] = field(default_factory=dict)

    # --- arrangement ---
    compartments: dict[str, IrCompartment] = field(default_factory=dict)
    physical_spaces: dict[str, IrPhysicalSpace] = field(default_factory=dict)

    # --- vessel-level metadata ---
    ship_designation: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    builder_info: dict[str, Any] | None = None
    principal_particulars: dict[str, Any] | None = None

    # --- integrity report populated by builder ---
    duplicate_ids: list[str] = field(default_factory=list)
    dangling_refs: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience look-up helpers
    # ------------------------------------------------------------------

    def get_plate(self, plate_id: str) -> IrPlate | None:
        return self.plates.get(plate_id)

    def get_bracket(self, bracket_id: str) -> IrBracket | None:
        return self.brackets.get(bracket_id)

    def get_stiffener(self, stiffener_id: str) -> IrStiffener | None:
        return self.stiffeners.get(stiffener_id)

    def get_pillar(self, pillar_id: str) -> IrPillar | None:
        return self.pillars.get(pillar_id)

    def get_edge_reinforcement(self, er_id: str) -> IrEdgeReinforcement | None:
        return self.edge_reinforcements.get(er_id)

    def get_panel(self, panel_id: str) -> IrPanel | None:
        return self.panels.get(panel_id)

    def get_material(self, material_id: str) -> IrMaterial | None:
        return self.materials.get(material_id)

    def get_section(self, section_id: str) -> IrSection | None:
        return self.sections.get(section_id)

    def get_compartment(self, compartment_id: str) -> IrCompartment | None:
        return self.compartments.get(compartment_id)

    def plates_for_panel(self, panel_id: str) -> list[IrPlate]:
        panel = self.panels.get(panel_id)
        if panel is None:
            return []
        return [self.plates[pid] for pid in panel.plate_ids if pid in self.plates]

    def brackets_for_panel(self, panel_id: str) -> list[IrBracket]:
        panel = self.panels.get(panel_id)
        if panel is None:
            return []
        return [self.brackets[bid] for bid in panel.bracket_ids if bid in self.brackets]

    def stiffeners_for_panel(self, panel_id: str) -> list[IrStiffener]:
        panel = self.panels.get(panel_id)
        if panel is None:
            return []
        return [self.stiffeners[sid] for sid in panel.stiffener_ids if sid in self.stiffeners]

    def pillars_for_panel(self, panel_id: str) -> list[IrPillar]:
        panel = self.panels.get(panel_id)
        if panel is None:
            return []
        return [self.pillars[pid] for pid in panel.pillar_ids if pid in self.pillars]

    def edge_reinforcements_for_panel(self, panel_id: str) -> list[IrEdgeReinforcement]:
        panel = self.panels.get(panel_id)
        if panel is None:
            return []
        return [
            self.edge_reinforcements[eid]
            for eid in panel.edge_reinforcement_ids
            if eid in self.edge_reinforcements
        ]

