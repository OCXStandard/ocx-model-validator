"""OCX and UnitsML XML stub loaders for pytest testing.

Each stub class loads an XML snippet from::

    tests/data/ocx_{version}_stubs/<entity>.3docx    (OCX entities)
    tests/data/unitsml_stubs/<entity>.xml            (UnitsML entities)

injects the correct ``xmlns`` namespace declaration, and parses it into the
typed dataclass for the requested schema version.

OCX Naming convention
---------------------
Stub directory:  ``ocx_{major}{minor}{patch}_stubs``  (e.g. ``ocx_310_stubs`` → 3.1.0)
Stub file:       ``<entity_lowercase>.3docx``           (e.g. ``material.3docx``)

UnitsML Naming convention
-------------------------
Stub directory:  ``unitsml_stubs`` (shared across all OCX versions)
Stub file:       ``<entity_lowercase>.xml``             (e.g. ``unit.xml``)

The XML snippets do **not** need to include ``xmlns`` declarations — the loader
injects the correct namespace automatically from the schema module.

Adding new entity stubs
-----------------------
1. Extract the XML snippet from a real 3Docx model.
2. Save it as ``tests/data/ocx_<version>_stubs/<entity>.3docx`` or
   ``tests/data/unitsml_stubs/<entity>.xml``.
3. Add a ``Stub<Entity>(OcxStubLoader)`` or ``UnitsML<Entity>(UnitsMLStubLoader)``
   subclass below with ``entity_file``.
4. Write tests in ``tests/test_ocx_xml_stubs.py``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeVar

from ocx_model_validator.parsers.load_tools import DeclarationOfOcxImport, OcxParser

if TYPE_CHECKING:
    from lxml import etree

T = TypeVar("T")

# Root path to all versioned stub data directories
STUBS_DATA_DIR = Path(__file__).parent / "data"

# UnitsML stubs directory (shared across OCX versions)
UNITSML_STUBS_DIR = STUBS_DATA_DIR / "unitsml_stubs"

# UnitsML namespace URI
UNITSML_NS = "urn:oasis:names:tc:unitsml:schema:xsd:UnitsMLSchema_lite-0.9.18"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def version_from_folder(folder_name: str) -> str:
    """Derive an OCX version string from a stub folder name.

    Convention: ``ocx_{digits}_stubs`` where each character in *digits* is one
    version component separated by a dot.

    Examples::

        'ocx_310_stubs'  →  '3.1.0'
        'ocx_300_stubs'  →  '3.0.0'

    Args:
        folder_name: The stub directory name (not a full path).

    Returns:
        Version string such as ``'3.1.0'``.

    Raises:
        ValueError: If *folder_name* does not match the expected pattern.
    """
    match = re.match(r"ocx_(\d+)_stubs$", folder_name)
    if not match:
        raise ValueError(
            f"Cannot parse OCX version from folder name: {folder_name!r}. "
            "Expected pattern: 'ocx_<digits>_stubs'."
        )
    digits = match.group(1)
    return ".".join(digits)  # '310' → '3.1.0'


# ---------------------------------------------------------------------------
# Base loader
# ---------------------------------------------------------------------------

class OcxStubLoader:
    """Base class for OCX entity stub loaders.

    Subclasses must define ``entity_file``, the filename of the XML snippet
    stored under the versioned stub directory.

    Stub files are self-contained XML documents written by ``generate_stubs.py``
    using ``Serializer.serialize_xml()``.  They already contain the correct
    ``xmlns:ocx`` declaration, so no namespace injection is needed on load.

    The ``load()`` classmethod:

    1. Reads the stub XML file.
    2. Parses it via :class:`~ocx_model_validator.parsers.parser.OcxParser`.
    3. Returns the typed OCX dataclass instance.

    Usage::

        from tests.stubs import StubMaterial, STUBS_DATA_DIR
        from ocx_model_validator.parsers.load_tools import DeclarationOfOcxImport

        stub_dir = STUBS_DATA_DIR / "ocx_310_stubs"
        decl = DeclarationOfOcxImport(name="ocx", version="3.1.0")
        material = StubMaterial.load(stub_dir=stub_dir, declaration=decl)
    """

    #: XML snippet filename, e.g. ``"material.3docx"``.  Must be set in each subclass.
    entity_file: ClassVar[str]

    @classmethod
    def load(cls, stub_dir: Path, declaration: DeclarationOfOcxImport) -> T:
        """Parse the stub file and return the OCX dataclass instance.

        Args:
            stub_dir: Path to the versioned stub directory
                      (e.g. ``tests/data/ocx_310_stubs``).
            declaration: The OCX module import declaration for the target
                         schema version.

        Returns:
            The parsed OCX dataclass instance.

        Raises:
            FileNotFoundError: If the stub XML file does not exist in *stub_dir*.
        """
        xml_path = stub_dir / cls.entity_file
        if not xml_path.exists():
            raise FileNotFoundError(
                f"Stub file not found: {xml_path}. "
                f"Create the XML snippet at that path to enable this stub."
            )
        xml_str = xml_path.read_text(encoding="utf-8")
        parser = OcxParser()
        return parser.parse_from_string(xml_str=xml_str, declaration=declaration)


# ---------------------------------------------------------------------------
# Concrete stub loaders — one subclass per OCX entity type
# ---------------------------------------------------------------------------

# Core structural entities
class StubMaterial(OcxStubLoader):
    """Stub loader for the OCX ``Material`` entity."""
    entity_file = "material.3docx"

class StubPlate(OcxStubLoader):
    """Stub loader for the OCX ``Plate`` entity."""
    entity_file = "plate.3docx"

class StubPanel(OcxStubLoader):
    """Stub loader for the OCX ``Panel`` entity."""
    entity_file = "panel.3docx"

class StubStiffener(OcxStubLoader):
    """Stub loader for the OCX ``Stiffener`` entity."""
    entity_file = "stiffener.3docx"

class StubHeader(OcxStubLoader):
    """Stub loader for the OCX ``Header`` entity."""
    entity_file = "header.3docx"

class StubVessel(OcxStubLoader):
    """Stub loader for the OCX ``Vessel`` entity."""
    entity_file = "vessel.3docx"


# Section types
class StubFlatBar(OcxStubLoader):
    """Stub loader for the OCX ``FlatBar`` section entity."""
    entity_file = "flatbar.3docx"

class StubBulbFlat(OcxStubLoader):
    """Stub loader for the OCX ``BulbFlat`` section entity."""
    entity_file = "bulbflat.3docx"

class StubBarSection(OcxStubLoader):
    """Stub loader for the OCX ``BarSection`` entity."""
    entity_file = "barsection.3docx"

class StubIBar(OcxStubLoader):
    """Stub loader for the OCX ``IBar`` section entity."""
    entity_file = "ibar.3docx"

class StubLBar(OcxStubLoader):
    """Stub loader for the OCX ``LBar`` section entity."""
    entity_file = "lbar.3docx"

class StubTBar(OcxStubLoader):
    """Stub loader for the OCX ``TBar`` section entity."""
    entity_file = "tbar.3docx"

class StubTube(OcxStubLoader):
    """Stub loader for the OCX ``Tube`` section entity."""
    entity_file = "tube.3docx"

class StubRectangularTube(OcxStubLoader):
    """Stub loader for the OCX ``RectangularTube`` section entity."""
    entity_file = "rectangulartube.3docx"

class StubHalfRoundBar(OcxStubLoader):
    """Stub loader for the OCX ``HalfRoundBar`` section entity."""
    entity_file = "halfroundbar.3docx"

class StubUserDefinedBarSection(OcxStubLoader):
    """Stub loader for the OCX ``UserDefinedBarSection`` entity."""
    entity_file = "userdefinedbarsection.3docx"

class StubSectionProperties(OcxStubLoader):
    """Stub loader for the OCX ``SectionProperties`` entity."""
    entity_file = "sectionproperties.3docx"

class StubSectionOuterShape(OcxStubLoader):
    """Stub loader for the OCX ``SectionOuterShape`` entity."""
    entity_file = "sectionoutershape.3docx"


# Bracket entities
class StubBracket(OcxStubLoader):
    """Stub loader for the OCX ``Bracket`` entity."""
    entity_file = "bracket.3docx"

class StubBracketParameters(OcxStubLoader):
    """Stub loader for the OCX ``BracketParameters`` entity."""
    entity_file = "bracketparameters.3docx"

class StubBracketRef(OcxStubLoader):
    """Stub loader for the OCX ``BracketRef`` entity."""
    entity_file = "bracketref.3docx"

class StubSingleBracket(OcxStubLoader):
    """Stub loader for the OCX ``SingleBracket`` entity."""
    entity_file = "singlebracket.3docx"

class StubDoubleBracket(OcxStubLoader):
    """Stub loader for the OCX ``DoubleBracket`` entity."""
    entity_file = "doublebracket.3docx"

class StubConnectedBracketRef(OcxStubLoader):
    """Stub loader for the OCX ``ConnectedBracketRef`` entity."""
    entity_file = "connectedbracketref.3docx"


# Connection entities
class StubConnectionConfiguration(OcxStubLoader):
    """Stub loader for the OCX ``ConnectionConfiguration`` entity."""
    entity_file = "connectionconfiguration.3docx"

class StubWebStiffener(OcxStubLoader):
    """Stub loader for the OCX ``WebStiffener`` entity."""
    entity_file = "webstiffener.3docx"

class StubWebStiffenerRef(OcxStubLoader):
    """Stub loader for the OCX ``WebStiffenerRef`` entity."""
    entity_file = "webstiffenerref.3docx"

class StubWebStiffenerWithSingleBracket(OcxStubLoader):
    """Stub loader for the OCX ``WebStiffenerWithSingleBracket`` entity."""
    entity_file = "webstiffenerwithsinglebracket.3docx"

class StubSlotParameters(OcxStubLoader):
    """Stub loader for the OCX ``SlotParameters`` entity."""
    entity_file = "slotparameters.3docx"

class StubPenetration(OcxStubLoader):
    """Stub loader for the OCX ``Penetration`` entity."""
    entity_file = "penetration.3docx"

class StubFeatureCope(OcxStubLoader):
    """Stub loader for the OCX ``FeatureCope`` entity."""
    entity_file = "featurecope.3docx"


# Pillar entity
class StubPillar(OcxStubLoader):
    """Stub loader for the OCX ``Pillar`` entity."""
    entity_file = "pillar.3docx"


# Edge reinforcement
class StubEdgeReinforcement(OcxStubLoader):
    """Stub loader for the OCX ``EdgeReinforcement`` entity."""
    entity_file = "edgereinforcement.3docx"

class StubEdgeReinforcementRef(OcxStubLoader):
    """Stub loader for the OCX ``EdgeReinforcementRef`` entity."""
    entity_file = "edgereinforcementref.3docx"


# Reference entities
class StubPlateRef(OcxStubLoader):
    """Stub loader for the OCX ``PlateRef`` entity."""
    entity_file = "plateref.3docx"

class StubPanelRef(OcxStubLoader):
    """Stub loader for the OCX ``PanelRef`` entity."""
    entity_file = "panelref.3docx"

class StubStiffenerRef(OcxStubLoader):
    """Stub loader for the OCX ``StiffenerRef`` entity."""
    entity_file = "stiffenerref.3docx"

class StubVesselRef(OcxStubLoader):
    """Stub loader for the OCX ``VesselRef`` entity."""
    entity_file = "vesselref.3docx"

class StubLugPlateRef(OcxStubLoader):
    """Stub loader for the OCX ``LugPlateRef`` entity."""
    entity_file = "lugplateref.3docx"


# Geometry entities
class StubPoint3D(OcxStubLoader):
    """Stub loader for the OCX ``Point3D`` entity."""
    entity_file = "point3d.3docx"

class StubSphere3D(OcxStubLoader):
    """Stub loader for the OCX ``Sphere3D`` entity."""
    entity_file = "sphere3d.3docx"

class StubCylinder3D(OcxStubLoader):
    """Stub loader for the OCX ``Cylinder3D`` entity."""
    entity_file = "cylinder3d.3docx"

class StubCone3D(OcxStubLoader):
    """Stub loader for the OCX ``Cone3D`` entity."""
    entity_file = "cone3d.3docx"

class StubEllipse3D(OcxStubLoader):
    """Stub loader for the OCX ``Ellipse3D`` entity."""
    entity_file = "ellipse3d.3docx"

class StubCircumCircle3D(OcxStubLoader):
    """Stub loader for the OCX ``CircumCircle3D`` entity."""
    entity_file = "circumcircle3d.3docx"

class StubPolyLine3D(OcxStubLoader):
    """Stub loader for the OCX ``PolyLine3D`` entity."""
    entity_file = "polyline3d.3docx"

class StubAxis(OcxStubLoader):
    """Stub loader for the OCX ``Axis`` entity."""
    entity_file = "axis.3docx"

class StubPositions(OcxStubLoader):
    """Stub loader for the OCX ``Positions`` entity."""
    entity_file = "positions.3docx"

class StubTip(OcxStubLoader):
    """Stub loader for the OCX ``Tip`` entity."""
    entity_file = "tip.3docx"


# Quantity entities (dimensions)
class StubArea(OcxStubLoader):
    """Stub loader for the OCX ``Area`` entity."""
    entity_file = "area.3docx"

class StubRadius(OcxStubLoader):
    """Stub loader for the OCX ``Radius`` entity."""
    entity_file = "radius.3docx"

class StubBaseRadius(OcxStubLoader):
    """Stub loader for the OCX ``BaseRadius`` entity."""
    entity_file = "baseradius.3docx"

class StubTipRadius(OcxStubLoader):
    """Stub loader for the OCX ``TipRadius`` entity."""
    entity_file = "tipradius.3docx"

class StubUpperRadius(OcxStubLoader):
    """Stub loader for the OCX ``UpperRadius`` entity."""
    entity_file = "upperradius.3docx"

class StubLowerRadius(OcxStubLoader):
    """Stub loader for the OCX ``LowerRadius`` entity."""
    entity_file = "lowerradius.3docx"

class StubArmLengthU(OcxStubLoader):
    """Stub loader for the OCX ``ArmLengthU`` entity."""
    entity_file = "armlengthu.3docx"

class StubArmLengthV(OcxStubLoader):
    """Stub loader for the OCX ``ArmLengthV`` entity."""
    entity_file = "armlengthv.3docx"

class StubConnectionLength(OcxStubLoader):
    """Stub loader for the OCX ``ConnectionLength`` entity."""
    entity_file = "connectionlength.3docx"

class StubCopeRadius(OcxStubLoader):
    """Stub loader for the OCX ``CopeRadius`` entity."""
    entity_file = "coperadius.3docx"

class StubCopeHeight(OcxStubLoader):
    """Stub loader for the OCX ``CopeHeight`` entity."""
    entity_file = "copeheight.3docx"

class StubCopeLength(OcxStubLoader):
    """Stub loader for the OCX ``CopeLength`` entity."""
    entity_file = "copelength.3docx"

class StubDistanceAbove(OcxStubLoader):
    """Stub loader for the OCX ``DistanceAbove`` entity."""
    entity_file = "distanceabove.3docx"

class StubMajorDiameter(OcxStubLoader):
    """Stub loader for the OCX ``MajorDiameter`` entity."""
    entity_file = "majordiameter.3docx"

class StubMinorDiameter(OcxStubLoader):
    """Stub loader for the OCX ``MinorDiameter`` entity."""
    entity_file = "minordiameter.3docx"

class StubMajorAxis(OcxStubLoader):
    """Stub loader for the OCX ``MajorAxis`` entity."""
    entity_file = "majoraxis.3docx"

class StubMinorAxis(OcxStubLoader):
    """Stub loader for the OCX ``MinorAxis`` entity."""
    entity_file = "minoraxis.3docx"

class StubNeutralAxisU(OcxStubLoader):
    """Stub loader for the OCX ``NeutralAxisU`` entity."""
    entity_file = "neutralaxisu.3docx"

class StubNeutralAxisV(OcxStubLoader):
    """Stub loader for the OCX ``NeutralAxisV`` entity."""
    entity_file = "neutralaxisv.3docx"

class StubInertiaU(OcxStubLoader):
    """Stub loader for the OCX ``InertiaU`` entity."""
    entity_file = "inertiau.3docx"

class StubInertiaV(OcxStubLoader):
    """Stub loader for the OCX ``InertiaV`` entity."""
    entity_file = "inertiav.3docx"

class StubFlangeThickness(OcxStubLoader):
    """Stub loader for the OCX ``FlangeThickness`` entity."""
    entity_file = "flangethickness.3docx"

class StubBulbAngle(OcxStubLoader):
    """Stub loader for the OCX ``BulbAngle`` entity."""
    entity_file = "bulbangle.3docx"

class StubBulbOuterRadius(OcxStubLoader):
    """Stub loader for the OCX ``BulbOuterRadius`` entity."""
    entity_file = "bulbouterradius.3docx"

class StubBulbInnerRadius(OcxStubLoader):
    """Stub loader for the OCX ``BulbInnerRadius`` entity."""
    entity_file = "bulbinnerradius.3docx"

class StubUnose(OcxStubLoader):
    """Stub loader for the OCX ``Unose`` entity."""
    entity_file = "unose.3docx"

class StubVnose(OcxStubLoader):
    """Stub loader for the OCX ``Vnose`` entity."""
    entity_file = "vnose.3docx"


# Direction entities
class StubUDirection(OcxStubLoader):
    """Stub loader for the OCX ``UDirection`` entity."""
    entity_file = "udirection.3docx"

class StubVDirection(OcxStubLoader):
    """Stub loader for the OCX ``VDirection`` entity."""
    entity_file = "vdirection.3docx"


# Contour entities
class StubInnerContour(OcxStubLoader):
    """Stub loader for the OCX ``InnerContour`` entity."""
    entity_file = "innercontour.3docx"

class StubHoleContourRef(OcxStubLoader):
    """Stub loader for the OCX ``HoleContourRef`` entity."""
    entity_file = "holecontourref.3docx"


# Design view entities
class StubDesignView(OcxStubLoader):
    """Stub loader for the OCX ``DesignView`` entity."""
    entity_file = "designview.3docx"

class StubOccurrenceGroup(OcxStubLoader):
    """Stub loader for the OCX ``OccurrenceGroup`` entity."""
    entity_file = "occurrencegroup.3docx"

class StubOccurrence(OcxStubLoader):
    """Stub loader for the OCX ``Occurrence`` entity."""
    entity_file = "occurrence.3docx"


# Ship data entities
class StubClassNotation(OcxStubLoader):
    """Stub loader for the OCX ``ClassNotation`` entity."""
    entity_file = "classnotation.3docx"

class StubStatutoryData(OcxStubLoader):
    """Stub loader for the OCX ``StatutoryData`` entity."""
    entity_file = "statutorydata.3docx"

class StubShipDesignation(OcxStubLoader):
    """Stub loader for the OCX ``ShipDesignation`` entity."""
    entity_file = "shipdesignation.3docx"

class StubTonnageData(OcxStubLoader):
    """Stub loader for the OCX ``TonnageData`` entity."""
    entity_file = "tonnagedata.3docx"

class StubTonnage(OcxStubLoader):
    """Stub loader for the OCX ``Tonnage`` entity."""
    entity_file = "tonnage.3docx"

class StubDeadWeight(OcxStubLoader):
    """Stub loader for the OCX ``DeadWeight`` entity."""
    entity_file = "deadweight.3docx"


# Draught entities
class StubNormalBallastDraught(OcxStubLoader):
    """Stub loader for the OCX ``NormalBallastDraught`` entity."""
    entity_file = "normalballastdraught.3docx"

class StubHeavyBallastDraught(OcxStubLoader):
    """Stub loader for the OCX ``HeavyBallastDraught`` entity."""
    entity_file = "heavyballastdraught.3docx"

class StubSlammingDraughtEmptyFP(OcxStubLoader):
    """Stub loader for the OCX ``SlammingDraughtEmptyFP`` entity."""
    entity_file = "slammingdraughtemptyfp.3docx"

class StubSlammingDraughtFullFP(OcxStubLoader):
    """Stub loader for the OCX ``SlammingDraughtFullFP`` entity."""
    entity_file = "slammingdraughtfullfp.3docx"


# Deck/waterline entities
class StubLengthOfWaterline(OcxStubLoader):
    """Stub loader for the OCX ``LengthOfWaterline`` entity."""
    entity_file = "lengthofwaterline.3docx"

class StubFreeboardDeckHeight(OcxStubLoader):
    """Stub loader for the OCX ``FreeboardDeckHeight`` entity."""
    entity_file = "freeboarddeckheight.3docx"

class StubZPosOfDeck(OcxStubLoader):
    """Stub loader for the OCX ``ZPosOfDeck`` entity."""
    entity_file = "zposofdeck.3docx"

class StubUpperDeckArea(OcxStubLoader):
    """Stub loader for the OCX ``UpperDeckArea`` entity."""
    entity_file = "upperdeckarea.3docx"

class StubWaterPlaneArea(OcxStubLoader):
    """Stub loader for the OCX ``WaterPlaneArea`` entity."""
    entity_file = "waterplanearea.3docx"

class StubZPosDeckline(OcxStubLoader):
    """Stub loader for the OCX ``ZPosDeckline`` entity."""
    entity_file = "zposdeckline.3docx"


# Material property entities
class StubThermalExpansionCoefficient(OcxStubLoader):
    """Stub loader for the OCX ``ThermalExpansionCoefficient`` entity."""
    entity_file = "thermalexpansioncoefficient.3docx"


# ---------------------------------------------------------------------------
# UnitsML stub loader base class
# ---------------------------------------------------------------------------

class UnitsMLStubLoader:
    """Base class for UnitsML entity stub loaders.

    Subclasses must define ``entity_file``, the filename of the XML stub
    stored under the UnitsML stub directory.

    Stub files are self-contained XML documents (generated by
    ``Serializer.serialize_xml(global_ns="unitsml")``), so no namespace
    injection is required on load.

    The ``load()`` classmethod:

    1. Reads the self-contained XML stub file.
    2. Parses via lxml.etree.
    3. Returns the parsed XML element.

    Usage::

        from tests.stubs import UnitsMLUnit, UNITSML_STUBS_DIR

        unit = UnitsMLUnit.load()
    """

    #: XML stub filename, e.g. ``"unit.xml"``.  Must be set in each subclass.
    entity_file: ClassVar[str]

    @classmethod
    def load(cls) -> "etree._Element":
        """Parse and return the root XML element from the stub file.

        Returns:
            The parsed lxml.etree Element.

        Raises:
            FileNotFoundError: If the stub XML file does not exist.
        """
        import lxml.etree as etree

        xml_path = UNITSML_STUBS_DIR / cls.entity_file
        if not xml_path.exists():
            raise FileNotFoundError(
                f"Stub file not found: {xml_path}. "
                f"Run 'validator --generate' to create stubs."
            )
        return etree.fromstring(xml_path.read_bytes())

    @classmethod
    def load_raw(cls) -> str:
        """Load and return the raw XML string from the stub file.

        Returns:
            The self-contained XML string with namespace declaration.

        Raises:
            FileNotFoundError: If the stub XML file does not exist.
        """
        xml_path = UNITSML_STUBS_DIR / cls.entity_file
        if not xml_path.exists():
            raise FileNotFoundError(
                f"Stub file not found: {xml_path}. "
                f"Run 'validator --generate' to create stubs."
            )
        return xml_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Concrete UnitsML stub loaders — one subclass per UnitsML entity type
# ---------------------------------------------------------------------------

class UnitsMLUnit(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``Unit`` entity."""
    entity_file = "unit.xml"

class UnitsMLUnitSet(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``UnitSet`` entity."""
    entity_file = "unitset.xml"

class UnitsMLUnitsML(UnitsMLStubLoader):
    """Stub loader for the UnitsML root ``UnitsML`` entity."""
    entity_file = "unitsml.xml"

class UnitsMLUnitName(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``UnitName`` entity."""
    entity_file = "unitname.xml"

class UnitsMLUnitSymbol(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``UnitSymbol`` entity."""
    entity_file = "unitsymbol.xml"

class UnitsMLRootUnits(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``RootUnits`` entity."""
    entity_file = "rootunits.xml"

class UnitsMLEnumeratedRootUnit(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``EnumeratedRootUnit`` entity."""
    entity_file = "enumeratedrootunit.xml"

class UnitsMLDimension(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``Dimension`` entity."""
    entity_file = "dimension.xml"

class UnitsMLDimensionSet(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``DimensionSet`` entity."""
    entity_file = "dimensionset.xml"

class UnitsMLLength(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``Length`` dimension entity."""
    entity_file = "length.xml"

class UnitsMLTime(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``Time`` dimension entity."""
    entity_file = "time.xml"

class UnitsMLMass(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``Mass`` dimension entity."""
    entity_file = "mass.xml"

# New UnitsML stubs
class UnitsMLElectricCurrent(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``ElectricCurrent`` dimension entity."""
    entity_file = "electriccurrent.xml"

class UnitsMLAmountOfSubstance(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``AmountOfSubstance`` dimension entity."""
    entity_file = "amountofsubstance.xml"

class UnitsMLLuminousIntensity(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``LuminousIntensity`` dimension entity."""
    entity_file = "luminousintensity.xml"

class UnitsMLThermodynamicTemperature(UnitsMLStubLoader):
    """Stub loader for the UnitsML ``ThermodynamicTemperature`` dimension entity."""
    entity_file = "thermodynamictemperature.xml"
