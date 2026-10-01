"""Shared stub objects that mimic OCX v3 xsdata dataclasses.

These stubs are plain Python objects with the same attribute names that the
OCX xsdata parser would produce.  The builder uses ``getattr(obj, field, None)``
throughout, so duck-typing is sufficient — no real OCX imports needed.

Usage in tests::

    from tests.stubs import (
        StubRoot, StubVessel, StubPanel, StubPlate, StubBracket,
        StubStiffener, StubPillar, StubEdgeReinforcement, StubCompartment,
        StubClassCatalogue, StubMaterialCatalogue, StubMaterial,
        StubXsectionCatalogue,
        StubFlatBarSection, StubTBarSection, StubBulbflatSection,
        StubRectangulartubeSection, StubOctagonbarSection, StubSquarebarSection,
        StubUbarSection, StubIbarSection, StubLbarofSection, StubZbarSection,
        StubRoundbarSection, StubLbarSection, StubLbarowSection,
        StubHalfroundbarSection, StubHexagonbarSection, StubTubeSection,
        StubGenericSection,
        StubQuantity, StubEnum, StubRef, StubPlateMaterial,
        StubCog, StubPhysicalProperties, StubBracketParameters,
        StubArrangement, StubCompartmentFace,
        StubShipDesignation, StubClassificationData,
        StubPrincipalParticulars, StubBuilderInformation,
        StubComposedOf, StubStiffenedBy, StubLimitedBy,
    )
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Primitive stubs
# ---------------------------------------------------------------------------

class StubQuantity:
    """Mimics OCX QuantityT (has numericvalue + unit)."""

    def __init__(self, value: float, unit: str):
        self.numericvalue = value
        self.unit = unit


class StubEnum:
    """Mimics an OCX enum field (has .value)."""
    def __init__(self, value: str):
        self.value = value


class StubRef:
    """Mimics an OCX *Ref type (local_ref + guidref + ref_type).
    ref_type mirrors the raw ``refType`` attribute on the OCX schema element.
    """
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


# ---------------------------------------------------------------------------
# Plate/bracket material stub
# ---------------------------------------------------------------------------

class StubPlateMaterial:
    """Mimics OCX PlateMaterialT."""
    def __init__(
        self,
        local_ref: str = "",
        guidref: str | None = None,
        thickness: StubQuantity | None = None,
    ):
        self.local_ref = local_ref
        self.guidref = guidref
        self.thickness = thickness


# ---------------------------------------------------------------------------
# Centre of gravity stub
# ---------------------------------------------------------------------------

class StubCog:
    """Mimics OCX CenterOfGravity (has coordinates + unit)."""
    def __init__(self, x: float, y: float, z: float, unit: str = "Um"):
        self.coordinates = [x, y, z]
        self.unit = unit


# ---------------------------------------------------------------------------
# Physical properties stub
# ---------------------------------------------------------------------------

class StubPhysicalProperties:
    """Mimics OCX PhysicalPropertiesT."""
    def __init__(
        self,
        dry_weight: StubQuantity | None = None,
        center_of_gravity: StubCog | None = None,
    ):
        self.dry_weight = dry_weight
        self.center_of_gravity = center_of_gravity


# ---------------------------------------------------------------------------
# Bracket parameters stub
# ---------------------------------------------------------------------------

class StubBracketParameters:
    """Mimics OCX BracketParametersT."""
    def __init__(
        self,
        arm_length_u: StubQuantity | None = None,
        arm_length_v: StubQuantity | None = None,
        has_edge_reinforcement: bool = False,
        number_of_supports: int | None = None,
    ):
        self.arm_length_u = arm_length_u
        self.arm_length_v = arm_length_v
        self.has_edge_reinforcement = has_edge_reinforcement
        self.number_of_supports = number_of_supports


# ---------------------------------------------------------------------------
# Structural part stubs
# ---------------------------------------------------------------------------

class StubPlate:
    """Mimics OCX Plate element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        plate_material: StubPlateMaterial | None = None,
        physical_properties: StubPhysicalProperties | None = None,
        net_area: StubQuantity | None = None,
        function_type: StubEnum | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.plate_material = plate_material
        self.physical_properties = physical_properties
        self.net_area = net_area
        self.function_type = function_type


class StubBracket:
    """Mimics OCX Bracket element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        plate_material: StubPlateMaterial | None = None,
        physical_properties: StubPhysicalProperties | None = None,
        bracket_parameters: StubBracketParameters | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.plate_material = plate_material
        self.physical_properties = physical_properties
        self.bracket_parameters = bracket_parameters


class StubStiffener:
    """Mimics OCX Stiffener element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        material_ref: StubRef | None = None,
        section_ref: StubRef | None = None,
        physical_properties: StubPhysicalProperties | None = None,
        function_type: StubEnum | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.material_ref = material_ref
        self.section_ref = section_ref
        self.physical_properties = physical_properties
        self.function_type = function_type


class StubPillar:
    """Mimics OCX Pillar element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        material_ref: StubRef | None = None,
        section_ref: StubRef | None = None,
        function_type: StubEnum | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.material_ref = material_ref
        self.section_ref = section_ref
        self.function_type = function_type


class StubEdgeReinforcement:
    """Mimics OCX EdgeReinforcement element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        material_ref: StubRef | None = None,
        section_ref: StubRef | None = None,
        physical_properties: StubPhysicalProperties | None = None,
        function_type: StubEnum | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.material_ref = material_ref
        self.section_ref = section_ref
        self.physical_properties = physical_properties
        self.function_type = function_type


# ---------------------------------------------------------------------------
# Panel composition stubs
# ---------------------------------------------------------------------------

class StubComposedOf:
    """Mimics OCX ComposedOf element."""
    def __init__(
        self,
        plate: list[StubPlate] | None = None,
        bracket: list[StubBracket] | None = None,
        pillar: list[StubPillar] | None = None,
    ):
        self.plate = plate or []
        self.bracket = bracket or []
        self.pillar = pillar or []


class StubStiffenedBy:
    """Mimics OCX StiffenedBy element."""
    def __init__(
        self,
        stiffener: list[StubStiffener] | None = None,
        edge_reinforcement: list[StubEdgeReinforcement] | None = None,
    ):
        self.stiffener = stiffener or []
        self.edge_reinforcement = edge_reinforcement or []


class StubFreeEdgeCurve3D:
    """Mimics OCX FreeEdgeCurve3D — an inline geometry element, no local_ref."""
    def __init__(self, name: str | None = None, guidref: str | None = None):
        self.name = name
        self.guidref = guidref


class StubLimitedBy:
    """Mimics OCX LimitedByT — all seven ref-type collections.

    Attribute names match the xsdata-generated field names on LimitedByT
    exactly so the builder's ``getattr(limited_by, attr, [])`` calls work.
    """
    def __init__(
        self,
        panel_ref: list | None = None,
        stiffener_ref: list | None = None,
        seam_ref: list | None = None,
        surface_ref: list | None = None,
        edge_curve_ref: list | None = None,
        grid_ref: list | None = None,
        edge_reinforcement_ref: list | None = None,
        free_edge_curve3_d: list | None = None,
    ):
        self.panel_ref              = panel_ref              or []
        self.stiffener_ref          = stiffener_ref          or []
        self.seam_ref               = seam_ref               or []
        self.surface_ref            = surface_ref            or []
        self.edge_curve_ref         = edge_curve_ref         or []
        self.grid_ref               = grid_ref               or []
        self.edge_reinforcement_ref = edge_reinforcement_ref or []
        self.free_edge_curve3_d     = free_edge_curve3_d     or []


class StubSeamRef:
    """Mimics OCX SeamRef."""
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


class StubSurfaceRef:
    """Mimics OCX SurfaceRef."""
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


class StubEdgeCurveRef:
    """Mimics OCX EdgeCurveRef."""
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


class StubGridRef:
    """Mimics OCX GridRef."""
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


class StubEdgeReinforcementRef:
    """Mimics OCX EdgeReinforcementRef."""
    def __init__(self, local_ref: str, guidref: str | None = None,
                 ref_type: str | None = None):
        self.local_ref = local_ref
        self.guidref = guidref
        self.ref_type = ref_type


class StubPanel:
    """Mimics OCX Panel element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        function_type: StubEnum | None = None,
        tightness: StubEnum | None = None,
        physical_properties: StubPhysicalProperties | None = None,
        composed_of: StubComposedOf | None = None,
        stiffened_by: StubStiffenedBy | None = None,
        limited_by: StubLimitedBy | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.function_type = function_type
        self.tightness = tightness
        self.physical_properties = physical_properties
        self.composed_of = composed_of
        self.stiffened_by = stiffened_by
        self.limited_by = limited_by


# ---------------------------------------------------------------------------
# Arrangement stubs
# ---------------------------------------------------------------------------

class StubCompartmentFace:
    """Mimics OCX CompartmentFace element."""
    def __init__(self, id: str, guidref: str | None = None):
        self.id = id
        self.guidref = guidref


class StubCompartmentProperties:
    """Mimics OCX CompartmentProperties element."""
    def __init__(
        self,
        volume: StubQuantity | None = None,
        filling_height: StubQuantity | None = None,
    ):
        self.volume = volume
        self.filling_height = filling_height


class StubCompartment:
    """Mimics OCX Compartment element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        compartment_purpose: StubEnum | None = None,
        compartment_properties: StubCompartmentProperties | None = None,
        compartment_face: list[StubCompartmentFace] | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.compartment_purpose = compartment_purpose
        self.compartment_properties = compartment_properties
        self.compartment_face = compartment_face or []


class StubPhysicalSpace:
    """Mimics OCX PhysicalSpace element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        space_type: StubEnum | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.space_type = space_type


class StubArrangement:
    """Mimics OCX Arrangement element."""
    def __init__(
        self,
        compartment: list[StubCompartment] | None = None,
        physical_space: list[StubPhysicalSpace] | None = None,
    ):
        self.compartment = compartment or []
        self.physical_space = physical_space or []


# ---------------------------------------------------------------------------
# Catalogue stubs
# ---------------------------------------------------------------------------

class StubMaterial:
    """Mimics OCX Material element."""
    def __init__(
        self,
        id: str,
        name: str | None = None,
        guidref: str | None = None,
        grade: StubEnum | None = None,
        density: StubQuantity | None = None,
        yield_stress: StubQuantity | None = None,
        ultimate_stress: StubQuantity | None = None,
        youngs_modulus: StubQuantity | None = None,
        poisson_ratio: StubQuantity | None = None,
        thermal_expansion: StubQuantity | None = None,
    ):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.grade = grade
        self.density = density
        self.yield_stress = yield_stress
        self.ultimate_stress = ultimate_stress
        self.youngs_modulus = youngs_modulus
        self.poisson_ratio = poisson_ratio
        self.thermal_expansion = thermal_expansion


class StubMaterialCatalogue:
    def __init__(self, material: list[StubMaterial] | None = None):
        self.material = material or []


# ---------------------------------------------------------------------------
# Section stubs — class names drive section type detection in the builder.
# The class name (lowercased) must contain the key from _SECTION_TYPE_MAP.
# ---------------------------------------------------------------------------

class StubFlatBarSection:
    """Class name contains 'flatbar' → stype='FlatBar' → IrFlatBarSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width


class StubTBarSection:
    """Class name contains 'tbar' → stype='TBar' → IrTSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness


class StubBulbflatSection:
    """Class name contains 'bulbflat' → stype='BulbFlat' → IrBulbFlatSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_width: StubQuantity | None = None,
                 bulb_angle: StubQuantity | None = None,
                 bulb_outer_radius: StubQuantity | None = None,
                 bulb_inner_radius: StubQuantity | None = None,
                 bulb_top_radius: StubQuantity | None = None,
                 bulb_bottom_radius: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.web_thickness = web_thickness
        self.flange_width = flange_width
        self.bulb_angle = bulb_angle
        self.bulb_outer_radius = bulb_outer_radius
        self.bulb_inner_radius = bulb_inner_radius
        self.bulb_top_radius = bulb_top_radius
        self.bulb_bottom_radius = bulb_bottom_radius


class StubRectangulartubeSection:
    """Class name contains 'rectangulartube' → stype='RectangularTube' → IrRectangularTubeSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.thickness = thickness


class StubOctagonbarSection:
    """Class name contains 'octagonbar' → stype='OctagonBar' → IrOctagonSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height


class StubSquarebarSection:
    """Class name contains 'squarebar' → stype='SquareBar' → IrSquareSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height


class StubUbarSection:
    """Class name contains 'ubar' → stype='UBar' → IrUSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness


class StubIbarSection:
    """Class name contains 'ibar' → stype='IBar' → IrISection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness


class StubLbarofSection:
    """Class name contains 'lbarof' → stype='LBarOF' → IrLSectionOvershootFlange."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None,
                 overshoot: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness
        self.overshoot = overshoot


class StubZbarSection:
    """Class name contains 'zbar' → stype='ZBar' → IrZSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness


class StubRoundbarSection:
    """Class name contains 'roundbar' → stype='RoundBar' → IrRoundSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 diameter: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.diameter = diameter


class StubLbarSection:
    """Class name contains 'lbar' (but not 'lbarof'/'lbarow') → stype='LBar' → IrLSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness


class StubLbarowSection:
    """Class name contains 'lbarow' → stype='LBarOW' → IrLSectionOvershootWeb."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None,
                 width: StubQuantity | None = None,
                 web_thickness: StubQuantity | None = None,
                 flange_thickness: StubQuantity | None = None,
                 overshoot: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height
        self.width = width
        self.web_thickness = web_thickness
        self.flange_thickness = flange_thickness
        self.overshoot = overshoot


class StubHalfroundbarSection:
    """Class name contains 'halfroundbar' → stype='HalfRoundBar' → IrHalfRoundSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 diameter: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.diameter = diameter


class StubHexagonbarSection:
    """Class name contains 'hexagonbar' → stype='HexagonBar' → IrHexagonSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 height: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.height = height


class StubTubeSection:
    """Class name contains 'tube' → stype='Tube' → IrTubeSection."""
    def __init__(self, id: str, name: str | None = None, guidref: str | None = None,
                 diameter: StubQuantity | None = None,
                 thickness: StubQuantity | None = None):
        self.id = id
        self.name = name
        self.guidref = guidref
        self.diameter = diameter
        self.thickness = thickness


@dataclass
class StubGenericSection:
    """No matching keyword in class name → IrGenericSection.
    Must be a dataclass so the builder's generic fallback path
    (which calls dataclasses.fields()) can introspect it.
    """
    id: str
    name: str | None = None
    guidref: str | None = None
    extra_field: str | None = None   # example arbitrary field the builder will capture


class StubXsectionCatalogue:
    def __init__(self, bar_section: list | None = None):
        self.bar_section = bar_section or []


class StubClassCatalogue:
    def __init__(
        self,
        material_catalogue: StubMaterialCatalogue | None = None,
        xsection_catalogue: StubXsectionCatalogue | None = None,
    ):
        self.material_catalogue = material_catalogue
        self.xsection_catalogue = xsection_catalogue


# ---------------------------------------------------------------------------
# Units stubs (UnitsML / OCX UnitSet)
# ---------------------------------------------------------------------------

class StubUnitName:
    """Mimics OCX UnitName (has .value string)."""
    def __init__(self, value: str):
        self.value = value


class StubUnitSymbol:
    """Mimics OCX UnitSymbol (has .type_value string)."""
    def __init__(self, type_value: str):
        self.type_value = type_value


class StubEnumValue:
    """Generic enum-like stub with a .value attribute."""
    def __init__(self, value: str):
        self.value = value


class StubEnumeratedRootUnit:
    """Mimics OCX EnumeratedRootUnit (unit enum, prefix enum, power_numerator)."""
    def __init__(
        self,
        unit: str | None = None,
        prefix: str | None = None,
        power_numerator: int = 1,
    ):
        self.unit = StubEnumValue(unit) if isinstance(unit, str) else unit
        self.prefix = StubEnumValue(prefix) if isinstance(prefix, str) else prefix
        self.power_numerator = power_numerator


class StubRootUnits:
    """Mimics OCX RootUnits (list of EnumeratedRootUnit)."""
    def __init__(self, enumerated_root_unit: list | None = None):
        self.enumerated_root_unit = enumerated_root_unit or []


class StubUnit:
    """Mimics an OCX Unit element (id, name, symbol, dimension_url, root_units)."""
    def __init__(
        self,
        id: str,
        name: str = "",
        symbol: str = "",
        dimension_url: str | None = None,
        root_units: StubRootUnits | None = None,
    ):
        self.id = id
        self.unit_name = [StubUnitName(name)] if name else []
        self.unit_symbol = [StubUnitSymbol(symbol)] if symbol else []
        self.dimension_url = dimension_url
        self.root_units = root_units


class StubUnitSet:
    """Mimics OCX UnitSet (list of Unit)."""
    def __init__(self, unit: list | None = None):
        self.unit = unit or []


class StubUnitsMl:
    """Mimics OCX UnitsMl (has .unit_set)."""
    def __init__(self, unit_set: StubUnitSet | None = None):
        self.unit_set = unit_set


# ---------------------------------------------------------------------------
# Vessel metadata stubs
# ---------------------------------------------------------------------------

class StubShipDesignation:
    def __init__(self, vessel_name: str | None = None, imo_number: str | None = None,
                 call_sign: str | None = None):
        self.vessel_name = vessel_name
        self.imo_number = imo_number
        self.call_sign = call_sign


class StubPrincipalParticulars:
    def __init__(
        self,
        lpp: StubQuantity | None = None,
        moulded_breadth: StubQuantity | None = None,
        moulded_depth: StubQuantity | None = None,
        design_speed: StubQuantity | None = None,
        scantling_draught: StubQuantity | None = None,
        freeboard_length: StubQuantity | None = None,
    ):
        self.lpp = lpp
        self.moulded_breadth = moulded_breadth
        self.moulded_depth = moulded_depth
        self.design_speed = design_speed
        self.scantling_draught = scantling_draught
        self.freeboard_length = freeboard_length


class StubClassificationData:
    def __init__(
        self,
        society_name: str | None = None,
        newbuilding_society_name: str | None = None,
        principal_particulars: StubPrincipalParticulars | None = None,
    ):
        self.society_name = society_name
        self.newbuilding_society_name = newbuilding_society_name
        self.principal_particulars = principal_particulars


class StubBuilderInformation:
    def __init__(self, yard: str | None = None, designer: str | None = None,
                 owner: str | None = None):
        self.yard = yard
        self.designer = designer
        self.owner = owner


# ---------------------------------------------------------------------------
# Vessel and root stubs
# ---------------------------------------------------------------------------

class StubVessel:
    """Mimics OCX Vessel element."""
    def __init__(
        self,
        id: str = "V001",
        name: str | None = "TestVessel",
        panel: list[StubPanel] | None = None,
        plate: list[StubPlate] | None = None,
        bracket: list[StubBracket] | None = None,
        stiffener: list[StubStiffener] | None = None,
        pillar: list[StubPillar] | None = None,
        arrangement: StubArrangement | None = None,
        ship_designation: StubShipDesignation | None = None,
        classification_data: StubClassificationData | None = None,
        builder_information: StubBuilderInformation | None = None,
    ):
        self.id = id
        self.name = name
        self.panel = panel or []
        self.plate = plate or []
        self.bracket = bracket or []
        self.stiffener = stiffener or []
        self.pillar = pillar or []
        self.arrangement = arrangement
        self.ship_designation = ship_designation
        self.classification_data = classification_data
        self.builder_information = builder_information


class StubRoot:
    """Mimics the top-level OcxXml root dataclass returned by OcxParser.parse()."""
    def __init__(
        self,
        schema_version: str = "3.1.0",
        vessel: StubVessel | None = None,
        class_catalogue: StubClassCatalogue | None = None,
        units_ml: StubUnitsMl | None = None,
    ):
        self.schema_version = schema_version
        self.vessel = vessel or StubVessel()
        self.class_catalogue = class_catalogue
        self.units_ml = units_ml

