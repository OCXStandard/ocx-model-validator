"""Structural IR types and the IrVessel root."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocx_model_validator.model.ir.arrangement import (
    IrBulkCargo,
    IrCompartment,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrPhysicalSpace,
    IrUnitCargo,
)
from ocx_model_validator.model.ir.base import (
    IrCog,
    IrMassProperties,
    IrUnit,
    ParentRef,
    Quantity,
    Ref,
)
from ocx_model_validator.model.ir.catalogues import (
    IrHoleShapeCatalogue,
    IrMaterial,
)
from ocx_model_validator.model.ir.connections import (
    IrConnectionConfiguration,
    IrPenetration,
)
from ocx_model_validator.model.ir.geometry import (
    IrCoordinateSystem,
    IrCurve3D,
    IrPoint3D,
    IrRefPlane,
    IrSurface,
    IrSurfaceCollection,
    IrUnboundedGeometry,
    IrVector3D,
)
from ocx_model_validator.model.ir.metadata import (
    IrBuilderInformation,
    IrHeader,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
    IrTonnageData,
)
from ocx_model_validator.model.ir.sections import IrSection

# ---------------------------------------------------------------------------
# Structural parts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IrInclination:
    """Local web/flange orientation of a stiffener at a position on its trace."""
    web_direction: IrVector3D | None = None
    flange_direction: IrVector3D | None = None
    position: IrPoint3D | None = None


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
    mass_properties: IrMassProperties | None = None
    net_area: Quantity | None = None
    function_type: str | None = None
    outer_contour: IrCurve3D | None = None


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
    mass_properties: IrMassProperties | None = None
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
    mass_properties: IrMassProperties | None = None
    function_type: str | None = None
    end_cut_end1: IrEndCut | None = None
    end_cut_end2: IrEndCut | None = None
    penetrations: list[IrPenetration] = field(default_factory=list)
    trace: IrCurve3D | None = None
    inclinations: list[IrInclination] = field(default_factory=list)


@dataclass
class IrPillar:
    """Schema-neutral pillar record."""
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    material_ref: Ref | None = None
    section_ref: Ref | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    mass_properties: IrMassProperties | None = None
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
    mass_properties: IrMassProperties | None = None
    function_type: str | None = None


# ---------------------------------------------------------------------------
# Seams, members and end detailing
# ---------------------------------------------------------------------------

@dataclass
class IrSeam:
    """Weld/connection line produced by Panel.split_by; carries its trace curve."""
    id: str
    name: str | None = None
    guidref: str | None = None
    trace_line: IrCurve3D | None = None


@dataclass
class IrMember:
    """Structural member element (physical-properties + external geometry ref).

    No reachable vessel-tree source exists in OCX 3.1.0, so the builder leaves
    ``IrVessel.members`` empty; the type is kept aligned for forward schemas.
    """
    id: str
    parent_ref: ParentRef
    name: str | None = None
    guidref: str | None = None
    dry_weight: Quantity | None = None
    cog: IrCog | None = None
    mass_properties: IrMassProperties | None = None
    external_geometry_ref: Ref | None = None


@dataclass(frozen=True)
class IrEndCut:
    """Stiffener end detailing (one instance per stiffener end)."""
    id: str | None = None
    name: str | None = None
    cutback_distance: Quantity | None = None
    web_cut_back_angle: Quantity | None = None
    web_nose_height: Quantity | None = None
    flange_cut_back_angle: Quantity | None = None
    flange_nose_height: Quantity | None = None
    symmetric_flange: bool = False
    sniped: bool = False
    feature_cope: "IrFeatureCope | None" = None


@dataclass(frozen=True)
class IrFeatureCope:
    """Cope feature on a structural element."""
    id: str
    name: str | None = None
    guidref: str | None = None
    cope_height: Quantity | None = None
    cope_length: Quantity | None = None
    cope_radius: Quantity | None = None


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
    mass_properties: IrMassProperties | None = None
    # Child part id references (into IrVessel dicts)
    plate_ids: list[str] = field(default_factory=list)
    bracket_ids: list[str] = field(default_factory=list)
    stiffener_ids: list[str] = field(default_factory=list)
    pillar_ids: list[str] = field(default_factory=list)
    edge_reinforcement_ids: list[str] = field(default_factory=list)
    seam_ids: list[str] = field(default_factory=list)
    member_ids: list[str] = field(default_factory=list)
    hole_shape_refs: list[Ref] = field(default_factory=list)
    # All boundary references, each tagged with ref_type
    limited_by: list[IrLimitedByRef] = field(default_factory=list)
    unbounded_geometry: IrUnboundedGeometry | None = None

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

    # --- new structural collections ---
    seams: dict[str, IrSeam] = field(default_factory=dict)
    members: dict[str, IrMember] = field(default_factory=dict)

    # --- catalogue dicts (keyed by id) ---
    materials: dict[str, IrMaterial] = field(default_factory=dict)
    sections: dict[str, IrSection] = field(default_factory=dict)
    hole_shape_catalogue: IrHoleShapeCatalogue | None = None

    # --- arrangement ---
    compartments: dict[str, IrCompartment] = field(default_factory=dict)
    physical_spaces: dict[str, IrPhysicalSpace] = field(default_factory=dict)

    # --- cargo collections ---
    liquid_cargoes: dict[str, IrLiquidCargo] = field(default_factory=dict)
    gaseous_cargoes: dict[str, IrGaseousCargo] = field(default_factory=dict)
    bulk_cargoes: dict[str, IrBulkCargo] = field(default_factory=dict)
    unit_cargoes: dict[str, IrUnitCargo] = field(default_factory=dict)

    # --- geometry collections ---
    coordinate_systems: dict[str, IrCoordinateSystem] = field(default_factory=dict)
    ref_planes: dict[str, IrRefPlane] = field(default_factory=dict)
    surfaces: dict[str, IrSurface] = field(default_factory=dict)
    surface_collections: dict[str, IrSurfaceCollection] = field(default_factory=dict)

    # --- design views ---
    design_views: dict[str, IrDesignView] = field(default_factory=dict)

    # --- connection configurations (placeholder) ---
    connection_configurations: dict[str, IrConnectionConfiguration] = field(default_factory=dict)

    # --- vessel-level metadata ---
    header: IrHeader | None = None
    ship_designation: IrShipDesignation | None = None
    classification: dict[str, Any] | None = None  # ClassificationData not in scope
    builder_info: IrBuilderInformation | None = None
    principal_particulars: IrPrincipalParticulars | None = None
    statutory_data: IrStatutoryData | None = None
    tonnage_data: IrTonnageData | None = None

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

    def get_seam(self, seam_id: str) -> IrSeam | None:
        return self.seams.get(seam_id)

    def get_member(self, member_id: str) -> IrMember | None:
        return self.members.get(member_id)

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
