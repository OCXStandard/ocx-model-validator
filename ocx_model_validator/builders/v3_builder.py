"""OcxV3Builder — translates OCX schema v3.x dataclasses into IR types.

All attribute access on raw OCX objects uses ``getattr(obj, "field", None)``
so that minor renames or additions within the v3 family degrade gracefully
instead of raising ``AttributeError``.

Integrity checks (duplicate ids, dangling refs) are performed after the full
model is built and reported via ``IrVessel.duplicate_ids`` and
``IrVessel.dangling_refs``.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from loguru import logger

from ocx_model_validator.model.ir import (
    IrBracket,
    IrBulbFlatSection,
    IrCog,
    IrCompartment,
    IrEdgeReinforcement,
    IrFlatBarSection,
    IrGenericSection,
    IrLimitedByRef,
    IrLSectionOvershootFlange,
    IrLSectionOvershootWeb,
    IrMaterial,
    IrPanel,
    IrPhysicalSpace,
    IrPillar,
    IrPlate,
    IrSection,
    IrTSection,
    IrLSection,
    IrStiffener,
    IrRoundSection,
    IrRectangularTubeSection,
    IrTubeSection,
    IrVessel,
    ParentKind,
    ParentRef,
    Quantity,
    Ref, IrOctagonSection, IrSquareSection, IrUSection, IrISection, IrZSection, IrHalfRoundSection, IrHexagonSection,
)
from ocx_model_validator.model.units import build_unit_registry
from .base import IOcxBuilder, MetaData


# ---------------------------------------------------------------------------
# Mapping from lowercased class-name substring → normalised stype string.
#
# _detect_section_type() lowercases the raw class name and checks each key
# as a substring in order.  More-specific keys MUST precede any key that is
# a substring of them (e.g. "flatbar" before "tbar", "rectangulartube"
# before "tube", "lbarof"/"lbarow" before "lbar",
# "halfroundbar" before "roundbar").
# ---------------------------------------------------------------------------
_SECTION_TYPE_MAP: dict[str, str] = {
    "rectangulartube": "RectangularTube",  # before "tube"
    "octagonbar":      "OctagonBar",
    "squarebar":       "SquareBar",
    "bulbflat":        "BulbFlat",
    "flatbar":         "FlatBar",          # before "tbar"
    "halfroundbar":    "HalfRoundBar",     # before "roundbar"
    "hexagonbar":      "HexagonBar",
    "roundbar":        "RoundBar",
    "ubar":            "UBar",
    "ibar":            "IBar",
    "lbarof":          "LBarOF",           # before "lbar"
    "zbar":            "ZBar",
    "lbarow":          "LBarOW",           # before "lbar"
    "lbar":            "LBar",
    "tbar":            "TBar",
    "tube":            "Tube",
}


class OcxV3Builder(IOcxBuilder):
    """Builds an ``IrVessel`` from an OCX v3.x root dataclass."""

    def supported_versions(self) -> list[tuple[int, int]]:
        return [(3, 0), (3, 1), (3, 2)]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, root) -> IrVessel:
        """Translate the raw OCX root into a fully-populated ``IrVessel``."""
        vessel_raw = getattr(root, "vessel", None)
        if vessel_raw is None:
            raise ValueError("OCX root contains no <Vessel> element.")

        schema_version: str = getattr(root, "schema_version", "unknown")
        vessel_id: str = getattr(vessel_raw, "id", "") or ""
        vessel_name: str = getattr(vessel_raw, "name", None)

        ir = IrVessel(
            id=vessel_id,
            name=vessel_name,
            schema_version=schema_version,
        )

        logger.info(
            f"Building IR for vessel {vessel_name!r} (schema {schema_version})"
        )

        # --- units first — registry is needed for geometry conversion later ---
        self._build_unit_registry(root, ir)

        # --- catalogues first (needed for ref resolution later) ---
        self._build_materials(root, ir)
        self._build_sections(root, ir)

        # --- vessel-level structural parts ---
        vessel_parent = ParentRef(kind=ParentKind.VESSEL, id=vessel_id)
        self._build_vessel_plates(vessel_raw, ir, vessel_parent)
        self._build_vessel_brackets(vessel_raw, ir, vessel_parent)
        self._build_vessel_stiffeners(vessel_raw, ir, vessel_parent)
        self._build_vessel_pillars(vessel_raw, ir, vessel_parent)

        # --- panels + their nested children ---
        for panel_raw in getattr(vessel_raw, "panel", []):
            ir_panel = self._build_panel(panel_raw, ir, vessel_id)
            if ir_panel is not None:
                ir.panels[ir_panel.id] = ir_panel

        # --- arrangement ---
        arrangement = getattr(vessel_raw, "arrangement", None)
        if arrangement is not None:
            self._build_compartments(arrangement, ir)
            self._build_physical_spaces(arrangement, ir)

        # --- vessel metadata ---
        ir.ship_designation = self._build_ship_designation(vessel_raw)
        ir.classification = self._build_classification(vessel_raw)
        ir.builder_info = self._build_builder_info(vessel_raw)
        ir.principal_particulars = self._build_principal_particulars(vessel_raw)

        # --- integrity checks ---
        self._check_integrity(ir)

        logger.success(
            f"IR built: {len(ir.panels)} panels, {len(ir.plates)} plates, "
            f"{len(ir.brackets)} brackets, {len(ir.stiffeners)} stiffeners, "
            f"{len(ir.pillars)} pillars, {len(ir.edge_reinforcements)} edge_reinforcements, "
            f"{len(ir.materials)} materials, "
            f"{len(ir.sections)} sections, {len(ir.compartments)} compartments."
        )
        return ir

    # ------------------------------------------------------------------
    # Safe primitive extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _qty(obj) -> Quantity | None:
        """Safely extract a Quantity from an OCX QuantityT dataclass."""
        if obj is None:
            return None
        try:
            value = getattr(obj, "numericvalue", None)
            unit = getattr(obj, "unit", None)
            if value is None:
                return None
            return Quantity(float(value), str(unit) if unit else "")
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _enum(obj) -> str | None:
        """Safely extract the string value of an OCX enum field."""
        if obj is None:
            return None
        try:
            return obj.value
        except AttributeError:
            return str(obj) if obj else None

    @staticmethod
    def _ref(obj) -> Ref | None:
        """Safely build a Ref from an OCX *Ref dataclass."""
        if obj is None:
            return None
        local = getattr(obj, "local_ref", None) or ""
        guid = getattr(obj, "guidref", None)
        return Ref(local_ref=local, guidref=guid)

    @staticmethod
    def _material_ref(plate_material_obj) -> tuple[Ref | None, Quantity | None]:
        """Extract (material_ref, thickness) from a PlateMaterialT."""
        if plate_material_obj is None:
            return None, None
        local = getattr(plate_material_obj, "local_ref", None) or ""
        guid = getattr(plate_material_obj, "guidref", None)
        mat_ref = Ref(local_ref=local, guidref=guid) if local or guid else None
        thickness_raw = getattr(plate_material_obj, "thickness", None)
        thickness = OcxV3Builder._qty(thickness_raw)
        return mat_ref, thickness

    @staticmethod
    def _cog(physical_properties) -> IrCog | None:
        """Extract centre of gravity from a PhysicalPropertiesT."""
        if physical_properties is None:
            return None
        cog_raw = getattr(physical_properties, "center_of_gravity", None)
        if cog_raw is None:
            return None
        coords = getattr(cog_raw, "coordinates", None)
        unit = getattr(cog_raw, "unit", None)
        if not coords or len(coords) < 3:
            return None
        try:
            return IrCog(
                x=float(coords[0]),
                y=float(coords[1]),
                z=float(coords[2]),
                unit=str(unit) if unit else "",
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _register(ir_dict: dict, obj_id: str, obj, duplicates: list[str]) -> None:
        """Register an object into a dict, recording duplicate ids."""
        if not obj_id:
            return
        if obj_id in ir_dict:
            duplicates.append(obj_id)
            logger.warning(f"Duplicate id detected: {obj_id!r}")
        else:
            ir_dict[obj_id] = obj

    # ------------------------------------------------------------------
    # Unit registry
    # ------------------------------------------------------------------

    def _build_unit_registry(self, root, ir: IrVessel) -> None:
        """Populate ``ir.unit_registry`` from the OCX ``<UnitsMl>`` element."""
        units_ml = getattr(root, "units_ml", None)
        ir.unit_registry = build_unit_registry(units_ml)

    # ------------------------------------------------------------------
    # Material catalogue
    # ------------------------------------------------------------------

    def _build_materials(self, root, ir: IrVessel) -> None:
        cc = getattr(root, "class_catalogue", None)
        if cc is None:
            return
        mc = getattr(cc, "material_catalogue", None)
        if mc is None:
            return
        for m in getattr(mc, "material", []):
            mid = getattr(m, "id", None) or getattr(m, "guidref", None)
            if not mid:
                continue
            ir_mat = IrMaterial(
                id=mid,
                name=getattr(m, "name", None),
                guidref=getattr(m, "guidref", None),
                grade=self._enum(getattr(m, "grade", None)),
                density=self._qty(getattr(m, "density", None)),
                yield_stress=self._qty(getattr(m, "yield_stress", None)),
                ultimate_stress=self._qty(getattr(m, "ultimate_stress", None)),
                youngs_modulus=self._qty(getattr(m, "youngs_modulus", None)),
                poisson_ratio=self._qty(getattr(m, "poisson_ratio", None)),
                thermal_expansion=self._qty(getattr(m, "thermal_expansion", None)),
            )
            self._register(ir.materials, mid, ir_mat, ir.duplicate_ids)

    # ------------------------------------------------------------------
    # Section catalogue
    # ------------------------------------------------------------------

    def _detect_section_type(self, raw_section) -> str:
        """Infer the OCX section type from the class Metadata or class name.

        Tries ``Meta.name`` first (real xsdata dataclasses); falls back to the
        class name for duck-typed stub objects that have no ``Meta`` attribute.
        Matching is case-insensitive against ``_SECTION_TYPE_MAP`` keys.
        """
        try:
            ocx_name = MetaData.name(raw_section)
        except AttributeError:
            ocx_name = None
        if not ocx_name:
            ocx_name = type(raw_section).__name__
        lowered = ocx_name.lower()
        for key, mapped in _SECTION_TYPE_MAP.items():
            if key in lowered:
                return mapped
        return "Generic"

    def _build_section(self, raw_section) -> IrSection:
        """Dispatch to the correct typed subclass factory."""
        sid = getattr(raw_section, "id", None) or getattr(raw_section, "guidref", None) or ""
        name = getattr(raw_section, "name", None)
        guid = getattr(raw_section, "guidref", None)
        stype = self._detect_section_type(raw_section)

        if stype == "RectangularTube":
            return IrRectangularTubeSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                thickness=self._qty(getattr(raw_section, "thickness", None)),
            )

        if stype == "OctagonBar":
            return IrOctagonSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
            )

        if stype == "SquareBar":
            return IrSquareSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
            )

        if stype == "BulbFlat":
            return IrBulbFlatSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_width=self._qty(getattr(raw_section, "flange_width", None)),
                bulb_angle=self._qty(getattr(raw_section, "bulb_angle", None)),
                bulb_outer_radius=self._qty(getattr(raw_section, "bulb_outer_radius", None)),
                bulb_inner_radius=self._qty(getattr(raw_section, "bulb_inner_radius", None)),
                bulb_top_radius=self._qty(getattr(raw_section, "bulb_top_radius", None)),
                bulb_bottom_radius=self._qty(getattr(raw_section, "bulb_bottom_radius", None)),
            )

        if stype == "FlatBar":
            return IrFlatBarSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
            )

        if stype == "UBar":
            return IrUSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
            )

        if stype == "IBar":
            return IrISection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
            )
        if stype == "LBarOF":
            return IrLSectionOvershootFlange(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
                overshoot=self._qty(getattr(raw_section, "overshoot", None)),
            )
        if stype == "ZBar":
            return IrZSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
            )
        if stype == "RoundBar":
            return IrRoundSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                diameter=self._qty(getattr(raw_section, "diameter", None)),
            )
        if stype == "LBar":
            return IrLSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
            )

        if stype == "TBar":
            return IrTSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
            )

        if stype == "LBarOW":
            return IrLSectionOvershootWeb(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
                width=self._qty(getattr(raw_section, "width", None)),
                web_thickness=self._qty(getattr(raw_section, "web_thickness", None)),
                flange_thickness=self._qty(getattr(raw_section, "flange_thickness", None)),
                overshoot=self._qty(getattr(raw_section, "overshoot", None)),
            )

        if stype == "HalfRoundBar":
            return IrHalfRoundSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                diameter=self._qty(getattr(raw_section, "diameter", None)),
            )
        if stype == "HexagonBar":
            return IrHexagonSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                height=self._qty(getattr(raw_section, "height", None)),
            )

        if stype == "Tube":
            return IrTubeSection(
                id=sid, name=name, guidref=guid, section_type=stype,
                diameter=self._qty(getattr(raw_section, "diameter", None)),
                thickness=self._qty(getattr(raw_section, "thickness", None)),
            )
        # Generic fallback — capture all scalar fields
        extra: dict[str, Any] = {}
        if dataclasses.is_dataclass(raw_section):
            for f in dataclasses.fields(raw_section):
                val = getattr(raw_section, f.name, None)
                if val is None or dataclasses.is_dataclass(val) or isinstance(val, list):
                    continue
                extra[f.name] = val.value if hasattr(val, "value") else val
        logger.warning(f'Not mapped section type detected: {type(raw_section).__name__!r}, defaulting to "GenericSection".')
        return IrGenericSection(id=sid, name=name, guidref=guid, section_type="Generic", extra=extra)

    def _build_sections(self, root, ir: IrVessel) -> None:
        cc = getattr(root, "class_catalogue", None)
        if cc is None:
            return
        xc = getattr(cc, "xsection_catalogue", None)
        if xc is None:
            return
        for raw_s in getattr(xc, "bar_section", []):
            ir_sec = self._build_section(raw_s)
            if ir_sec.id:
                self._register(ir.sections, ir_sec.id, ir_sec, ir.duplicate_ids)
                # Also index by guidref if different from id
                if ir_sec.guidref and ir_sec.guidref != ir_sec.id:
                    if ir_sec.guidref not in ir.sections:
                        ir.sections[ir_sec.guidref] = ir_sec

    # ------------------------------------------------------------------
    # Structural part builders (individual objects)
    # ------------------------------------------------------------------

    def _build_plate(self, raw, parent: ParentRef) -> IrPlate | None:
        pid = getattr(raw, "id", None)
        if not pid:
            return None
        pm = getattr(raw, "plate_material", None)
        mat_ref, thickness = self._material_ref(pm)
        pp = getattr(raw, "physical_properties", None)
        return IrPlate(
            id=pid,
            parent_ref=parent,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            material_ref=mat_ref,
            thickness=thickness,
            dry_weight=self._qty(getattr(pp, "dry_weight", None) if pp else None),
            cog=self._cog(pp),
            net_area=self._qty(getattr(raw, "net_area", None)),
            function_type=self._enum(getattr(raw, "function_type", None)),
        )

    def _build_bracket(self, raw, parent: ParentRef) -> IrBracket | None:
        bid = getattr(raw, "id", None)
        if not bid:
            return None
        pm = getattr(raw, "plate_material", None)
        mat_ref, thickness = self._material_ref(pm)
        pp = getattr(raw, "physical_properties", None)
        bp = getattr(raw, "bracket_parameters", None)
        return IrBracket(
            id=bid,
            parent_ref=parent,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            material_ref=mat_ref,
            thickness=thickness,
            dry_weight=self._qty(getattr(pp, "dry_weight", None) if pp else None),
            cog=self._cog(pp),
            arm_length_u=self._qty(getattr(bp, "arm_length_u", None) if bp else None),
            arm_length_v=self._qty(getattr(bp, "arm_length_v", None) if bp else None),
            has_edge_reinforcement=bool(getattr(bp, "has_edge_reinforcement", False) if bp else False),
            number_of_supports=getattr(bp, "number_of_supports", None) if bp else None,
        )

    def _build_stiffener(self, raw, parent: ParentRef) -> IrStiffener | None:
        sid = getattr(raw, "id", None)
        if not sid:
            return None
        pp = getattr(raw, "physical_properties", None)
        return IrStiffener(
            id=sid,
            parent_ref=parent,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            material_ref=self._ref(getattr(raw, "material_ref", None)),
            section_ref=self._ref(getattr(raw, "section_ref", None)),
            dry_weight=self._qty(getattr(pp, "dry_weight", None) if pp else None),
            cog=self._cog(pp),
            function_type=self._enum(getattr(raw, "function_type", None)),
        )

    def _build_pillar(self, raw, parent: ParentRef) -> IrPillar | None:
        pid = getattr(raw, "id", None)
        if not pid:
            return None
        pp = getattr(raw, "physical_properties", None)
        return IrPillar(
            id=pid,
            parent_ref=parent,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            material_ref=self._ref(getattr(raw, "material_ref", None)),
            section_ref=self._ref(getattr(raw, "section_ref", None)),
            cog=self._cog(pp),
            function_type=self._enum(getattr(raw, "function_type", None)),
        )

    def _build_edge_reinforcement(self, raw, parent: ParentRef) -> IrEdgeReinforcement | None:
        """Build an IrEdgeReinforcement from a raw OCX EdgeReinforcement element."""
        eid = getattr(raw, "id", None)
        if not eid:
            return None
        pp = getattr(raw, "physical_properties", None)
        return IrEdgeReinforcement(
            id=eid,
            parent_ref=parent,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            material_ref=self._ref(getattr(raw, "material_ref", None)),
            section_ref=self._ref(getattr(raw, "section_ref", None)),
            dry_weight=self._qty(getattr(pp, "dry_weight", None) if pp else None),
            cog=self._cog(pp),
            function_type=self._enum(getattr(raw, "function_type", None)),
        )

    # ------------------------------------------------------------------
    # Vessel-level structural collections
    # ------------------------------------------------------------------

    def _build_vessel_plates(self, vessel_raw, ir: IrVessel, parent: ParentRef) -> None:
        for raw in getattr(vessel_raw, "plate", []):
            obj = self._build_plate(raw, parent)
            if obj:
                self._register(ir.plates, obj.id, obj, ir.duplicate_ids)

    def _build_vessel_brackets(self, vessel_raw, ir: IrVessel, parent: ParentRef) -> None:
        for raw in getattr(vessel_raw, "bracket", []):
            obj = self._build_bracket(raw, parent)
            if obj:
                self._register(ir.brackets, obj.id, obj, ir.duplicate_ids)

    def _build_vessel_stiffeners(self, vessel_raw, ir: IrVessel, parent: ParentRef) -> None:
        for raw in getattr(vessel_raw, "stiffener", []):
            obj = self._build_stiffener(raw, parent)
            if obj:
                self._register(ir.stiffeners, obj.id, obj, ir.duplicate_ids)

    def _build_vessel_pillars(self, vessel_raw, ir: IrVessel, parent: ParentRef) -> None:
        for raw in getattr(vessel_raw, "pillar", []):
            obj = self._build_pillar(raw, parent)
            if obj:
                self._register(ir.pillars, obj.id, obj, ir.duplicate_ids)

    # ------------------------------------------------------------------
    # Panel
    # ------------------------------------------------------------------

    def _build_panel(self, raw, ir: IrVessel, vessel_id: str) -> IrPanel | None:
        pid = getattr(raw, "id", None)
        if not pid:
            return None

        panel_parent = ParentRef(kind=ParentKind.PANEL, id=pid)

        # --- composed-of children ---
        plate_ids: list[str] = []
        bracket_ids: list[str] = []
        pillar_ids: list[str] = []
        composed_of = getattr(raw, "composed_of", None)
        if composed_of is not None:
            for rp in getattr(composed_of, "plate", []):
                obj = self._build_plate(rp, panel_parent)
                if obj:
                    self._register(ir.plates, obj.id, obj, ir.duplicate_ids)
                    plate_ids.append(obj.id)
            for rb in getattr(composed_of, "bracket", []):
                obj = self._build_bracket(rb, panel_parent)
                if obj:
                    self._register(ir.brackets, obj.id, obj, ir.duplicate_ids)
                    bracket_ids.append(obj.id)
            for rpi in getattr(composed_of, "pillar", []):
                obj = self._build_pillar(rpi, panel_parent)
                if obj:
                    self._register(ir.pillars, obj.id, obj, ir.duplicate_ids)
                    pillar_ids.append(obj.id)

        # --- stiffened-by children ---
        stiffener_ids: list[str] = []
        edge_reinforcement_ids: list[str] = []
        stiffened_by = getattr(raw, "stiffened_by", None)
        if stiffened_by is not None:
            for rs in getattr(stiffened_by, "stiffener", []):
                obj = self._build_stiffener(rs, panel_parent)
                if obj:
                    self._register(ir.stiffeners, obj.id, obj, ir.duplicate_ids)
                    stiffener_ids.append(obj.id)
            for re in getattr(stiffened_by, "edge_reinforcement", []):
                obj = self._build_edge_reinforcement(re, panel_parent)
                if obj:
                    self._register(ir.edge_reinforcements, obj.id, obj, ir.duplicate_ids)
                    edge_reinforcement_ids.append(obj.id)

        # --- limited-by references — collect ALL boundary ref types ---
        limited_by_refs: list[IrLimitedByRef] = []
        limited_by = getattr(raw, "limited_by", None)
        if limited_by is not None:
            # Each tuple: (attribute name on LimitedByT, normalised ref_type label)
            # Standard *Ref elements carry local_ref + guidref.
            _LB_ATTRS: list[tuple[str, str]] = [
                ("panel_ref",               "PanelRef"),
                ("stiffener_ref",           "StiffenerRef"),
                ("seam_ref",                "SeamRef"),
                ("surface_ref",             "SurfaceRef"),
                ("edge_curve_ref",          "EdgeCurveRef"),
                ("grid_ref",                "GridRef"),
                ("edge_reinforcement_ref",  "EdgeReinforcementRef"),
            ]
            for attr, ref_type in _LB_ATTRS:
                for ref_raw in getattr(limited_by, attr, []):
                    local = getattr(ref_raw, "local_ref", None) or ""
                    guid  = getattr(ref_raw, "guidref", None)
                    # ref_type attr on the OCX element itself (e.g. "ocx:PanelRef")
                    ocx_rt = getattr(ref_raw, "ref_type", None)
                    limited_by_refs.append(
                        IrLimitedByRef(
                            ref_type=ref_type,
                            local_ref=local,
                            guidref=guid,
                            ocx_ref_type=ocx_rt,
                        )
                    )

            # FreeEdgeCurve3D is an inline geometry element (no local_ref).
            # Use guidref as identifier; fall back to name if guidref is absent.
            for fec in getattr(limited_by, "free_edge_curve3_d", []):
                guid = getattr(fec, "guidref", None)
                name_val = getattr(fec, "name", None)
                limited_by_refs.append(
                    IrLimitedByRef(
                        ref_type="FreeEdgeCurve3D",
                        local_ref=name_val or "",
                        guidref=guid,
                    )
                )

        pp = getattr(raw, "physical_properties", None)

        return IrPanel(
            id=pid,
            name=getattr(raw, "name", None),
            guidref=getattr(raw, "guidref", None),
            function_type=self._enum(getattr(raw, "function_type", None)),
            tightness=self._enum(getattr(raw, "tightness", None)),
            dry_weight=self._qty(getattr(pp, "dry_weight", None) if pp else None),
            cog=self._cog(pp),
            plate_ids=plate_ids,
            bracket_ids=bracket_ids,
            stiffener_ids=stiffener_ids,
            pillar_ids=pillar_ids,
            edge_reinforcement_ids=edge_reinforcement_ids,
            limited_by=limited_by_refs,
        )

    # ------------------------------------------------------------------
    # Arrangement
    # ------------------------------------------------------------------

    def _build_compartments(self, arrangement, ir: IrVessel) -> None:
        for raw in getattr(arrangement, "compartment", []):
            cid = getattr(raw, "id", None)
            if not cid:
                continue
            cp = getattr(raw, "compartment_properties", None)
            face_refs = [
                Ref(
                    local_ref=getattr(f, "id", None) or getattr(f, "local_ref", "") or "",
                    guidref=getattr(f, "guidref", None),
                )
                for f in getattr(raw, "compartment_face", [])
            ]
            ir_c = IrCompartment(
                id=cid,
                name=getattr(raw, "name", None),
                guidref=getattr(raw, "guidref", None),
                compartment_purpose=self._enum(getattr(raw, "compartment_purpose", None)),
                volume=self._qty(getattr(cp, "volume", None) if cp else None),
                filling_height=self._qty(getattr(cp, "filling_height", None) if cp else None),
                face_refs=face_refs,
            )
            self._register(ir.compartments, cid, ir_c, ir.duplicate_ids)

    def _build_physical_spaces(self, arrangement, ir: IrVessel) -> None:
        for raw in getattr(arrangement, "physical_space", []):
            sid = getattr(raw, "id", None)
            if not sid:
                continue
            ir_ps = IrPhysicalSpace(
                id=sid,
                name=getattr(raw, "name", None),
                guidref=getattr(raw, "guidref", None),
                space_type=self._enum(getattr(raw, "space_type", None)),
            )
            self._register(ir.physical_spaces, sid, ir_ps, ir.duplicate_ids)

    # ------------------------------------------------------------------
    # Vessel metadata
    # ------------------------------------------------------------------

    def _build_ship_designation(self, vessel_raw) -> dict | None:
        sd = getattr(vessel_raw, "ship_designation", None)
        if sd is None:
            return None
        return {
            "vessel_name": getattr(sd, "vessel_name", None),
            "imo_number": getattr(sd, "imo_number", None),
            "call_sign": getattr(sd, "call_sign", None),
        }

    def _build_classification(self, vessel_raw) -> dict | None:
        cd = getattr(vessel_raw, "classification_data", None)
        if cd is None:
            return None
        return {
            "classification_society": (
                getattr(cd, "society_name", None)
                or getattr(cd, "newbuilding_society_name", None)
            ),
        }

    def _build_builder_info(self, vessel_raw) -> dict | None:
        bi = getattr(vessel_raw, "builder_information", None)
        if bi is None:
            return None
        return {
            "yard": getattr(bi, "yard", None),
            "designer": getattr(bi, "designer", None),
            "owner": getattr(bi, "owner", None),
        }

    def _build_principal_particulars(self, vessel_raw) -> dict | None:
        cd = getattr(vessel_raw, "classification_data", None)
        if cd is None:
            return None
        pp = getattr(cd, "principal_particulars", None)
        if pp is None:
            return None

        def _q(attr: str) -> dict | None:
            qty = self._qty(getattr(pp, attr, None))
            return {"value": qty.value, "unit": qty.unit} if qty else None

        return {
            "lpp": _q("lpp"),
            "moulded_breadth": _q("moulded_breadth"),
            "moulded_depth": _q("moulded_depth"),
            "design_speed": _q("design_speed"),
            "scantling_draught": _q("scantling_draught"),
            "freeboard_length": _q("freeboard_length"),
        }

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _check_integrity(self, ir: IrVessel) -> None:
        """Detect dangling references and report them on the IrVessel."""
        all_ids: set[str] = (
            set(ir.panels)
            | set(ir.plates)
            | set(ir.brackets)
            | set(ir.stiffeners)
            | set(ir.pillars)
            | set(ir.materials)
            | set(ir.sections)
            | set(ir.compartments)
        )

        dangling: list[str] = []

        # Check panel adjacency refs
        for panel in ir.panels.values():
            for ref in panel.panel_refs:
                if ref.local_ref and ref.local_ref not in ir.panels:
                    dangling.append(f"Panel {panel.id!r} PanelRef {ref.local_ref!r} not found")
            for ref in panel.stiffener_refs:
                if ref.local_ref and ref.local_ref not in ir.stiffeners:
                    dangling.append(f"Panel {panel.id!r} StiffenerRef {ref.local_ref!r} not found")

        # Check panel child id lists
        for panel in ir.panels.values():
            for pid in panel.plate_ids:
                if pid not in ir.plates:
                    dangling.append(f"Panel {panel.id!r} plate_id {pid!r} not in plates dict")
            for bid in panel.bracket_ids:
                if bid not in ir.brackets:
                    dangling.append(f"Panel {panel.id!r} bracket_id {bid!r} not in brackets dict")
            for sid in panel.stiffener_ids:
                if sid not in ir.stiffeners:
                    dangling.append(f"Panel {panel.id!r} stiffener_id {sid!r} not in stiffeners dict")
            for pid in panel.pillar_ids:
                if pid not in ir.pillars:
                    dangling.append(f"Panel {panel.id!r} pillar_id {pid!r} not in pillars dict")
            for eid in panel.edge_reinforcement_ids:
                if eid not in ir.edge_reinforcements:
                    dangling.append(f"Panel {panel.id!r} edge_reinforcement_id {eid!r} not in edge_reinforcements dict")

        # Check material refs on plates / brackets
        for plate in ir.plates.values():
            if plate.material_ref and plate.material_ref.local_ref:
                if plate.material_ref.local_ref not in ir.materials:
                    dangling.append(
                        f"Plate {plate.id!r} material_ref {plate.material_ref.local_ref!r} not in materials"
                    )
        for bracket in ir.brackets.values():
            if bracket.material_ref and bracket.material_ref.local_ref:
                if bracket.material_ref.local_ref not in ir.materials:
                    dangling.append(
                        f"Bracket {bracket.id!r} material_ref {bracket.material_ref.local_ref!r} not in materials"
                    )

        # Check section refs on stiffeners / pillars
        for stiffener in ir.stiffeners.values():
            if stiffener.section_ref and stiffener.section_ref.local_ref:
                if stiffener.section_ref.local_ref not in ir.sections:
                    dangling.append(
                        f"Stiffener {stiffener.id!r} section_ref {stiffener.section_ref.local_ref!r} not in sections"
                    )

        ir.dangling_refs = dangling
        if dangling:
            logger.warning(f"Integrity check: {len(dangling)} dangling reference(s) detected.")
        if ir.duplicate_ids:
            logger.warning(f"Integrity check: {len(ir.duplicate_ids)} duplicate id(s) detected.")

