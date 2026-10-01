"""Tests for OcxV3Builder — IR type construction from XML stubs.

Each test class exercises one builder method using stubs loaded from the
versioned stub directories.  Tests are parametrized over all available schema
versions via the ``ocx_stub_version`` fixture defined in conftest.py.

Covered IR types:
    IrMaterial, IrSection (all subtypes), IrPlate, IrBracket, IrStiffener,
    IrPillar, IrEdgeReinforcement, IrPanel

Missing IR classes are documented in ``MISSING_IR_CLASSES`` at the bottom.
The ``TestMissingIrClasses`` class confirms those gaps are still open so that
a developer who adds a new Ir* type is reminded to create a real builder test.
"""
from __future__ import annotations

import pytest

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import (
    IrBracket,
    IrBulbFlatSection,
    IrEdgeReinforcement,
    IrFlatBarSection,
    IrGenericSection,
    IrHalfRoundSection,
    IrISection,
    IrLSection,
    IrMaterial,
    IrPanel,
    IrPillar,
    IrPlate,
    IrRectangularTubeSection,
    IrSection,
    IrStiffener,
    IrTSection,
    IrTubeSection,
    IrVessel,
    ParentKind,
    ParentRef,
)
from tests.stubs import (
    StubBarSection,
    StubBracket,
    StubBulbFlat,
    StubDoubleBracket,
    StubEdgeReinforcement,
    StubFlatBar,
    StubHalfRoundBar,
    StubIBar,
    StubLBar,
    StubMaterial,
    StubPanel,
    StubPillar,
    StubPlate,
    StubRectangularTube,
    StubSingleBracket,
    StubStiffener,
    StubTBar,
    StubTube,
    StubUserDefinedBarSection,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Ns:
    """Minimal attribute-carrying namespace for wrapping builder inputs."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _load(stub_cls, stub_dir, declaration):
    """Load a stub; skip the test when the file is absent for this version."""
    try:
        return stub_cls.load(stub_dir=stub_dir, declaration=declaration)
    except FileNotFoundError:
        pytest.skip(f"Stub {stub_cls.entity_file!r} not found in {stub_dir.name}")


def _vessel_parent() -> ParentRef:
    return ParentRef(kind=ParentKind.VESSEL, id="vessel-test")


def _empty_ir() -> IrVessel:
    return IrVessel(id="vessel-test", schema_version="test")


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

class TestBuildMaterial:

    def test_returns_ir_material(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubMaterial, stub_dir, declaration)
        root = _Ns(class_catalogue=_Ns(
            material_catalogue=_Ns(material=[raw]),
            xsection_catalogue=None,
        ))
        ir = _empty_ir()
        OcxV3Builder()._build_materials(root, ir)
        assert len(ir.materials) == 1
        mat = next(iter(ir.materials.values()))
        assert isinstance(mat, IrMaterial)

    def test_material_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubMaterial, stub_dir, declaration)
        root = _Ns(class_catalogue=_Ns(
            material_catalogue=_Ns(material=[raw]),
            xsection_catalogue=None,
        ))
        ir = _empty_ir()
        OcxV3Builder()._build_materials(root, ir)
        mat = next(iter(ir.materials.values()))
        assert mat.id

    def test_material_has_quantity_fields(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubMaterial, stub_dir, declaration)
        root = _Ns(class_catalogue=_Ns(
            material_catalogue=_Ns(material=[raw]),
            xsection_catalogue=None,
        ))
        ir = _empty_ir()
        OcxV3Builder()._build_materials(root, ir)
        mat = next(iter(ir.materials.values()))
        has_qty = any([mat.density, mat.yield_stress, mat.youngs_modulus])
        assert has_qty, "Expected at least one quantity field populated in material stub"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

class TestBuildSections:

    def _build(self, stub_cls, stub_dir, declaration) -> IrSection:
        raw = _load(stub_cls, stub_dir, declaration)
        return OcxV3Builder()._build_section(raw)

    def test_bulbflat_returns_ir_bulbflat_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubBulbFlat, stub_dir, declaration)
        assert isinstance(result, IrBulbFlatSection)
        assert result.section_type == "BulbFlat"

    def test_flatbar_returns_ir_flatbar_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubFlatBar, stub_dir, declaration)
        assert isinstance(result, IrFlatBarSection)
        assert result.section_type == "FlatBar"

    def test_ibar_returns_ir_i_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubIBar, stub_dir, declaration)
        assert isinstance(result, IrISection)
        assert result.section_type == "IBar"

    def test_lbar_returns_ir_l_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubLBar, stub_dir, declaration)
        assert isinstance(result, IrLSection)
        assert result.section_type == "LBar"

    def test_tbar_returns_ir_t_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubTBar, stub_dir, declaration)
        assert isinstance(result, IrTSection)
        assert result.section_type == "TBar"

    def test_halfroundbar_returns_ir_halfround_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubHalfRoundBar, stub_dir, declaration)
        assert isinstance(result, IrHalfRoundSection)
        assert result.section_type == "HalfRoundBar"

    def test_tube_returns_ir_tube_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubTube, stub_dir, declaration)
        assert isinstance(result, IrTubeSection)
        assert result.section_type == "Tube"

    def test_rectangulartube_returns_ir_rectangulartube_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubRectangularTube, stub_dir, declaration)
        assert isinstance(result, IrRectangularTubeSection)
        assert result.section_type == "RectangularTube"

    def test_userdefined_returns_ir_generic_section(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubUserDefinedBarSection, stub_dir, declaration)
        assert isinstance(result, IrGenericSection)
        assert result.section_type == "Generic"

    def test_all_typed_sections_have_section_type(self, ocx_stub_version):
        """Section stubs capture the bare geometry element, which carries no id.

        The id lives on the containing BarSection element in the full model.
        We verify section_type dispatch works for all typed stubs instead.
        """
        _, stub_dir, declaration = ocx_stub_version
        typed_stubs = [
            (StubBulbFlat, "BulbFlat"),
            (StubFlatBar, "FlatBar"),
            (StubIBar, "IBar"),
            (StubLBar, "LBar"),
            (StubTBar, "TBar"),
            (StubHalfRoundBar, "HalfRoundBar"),
            (StubTube, "Tube"),
            (StubRectangularTube, "RectangularTube"),
        ]
        builder = OcxV3Builder()
        for stub_cls, expected_type in typed_stubs:
            raw = _load(stub_cls, stub_dir, declaration)
            ir_sec = builder._build_section(raw)
            assert ir_sec.section_type == expected_type, (
                f"{stub_cls.__name__} section_type={ir_sec.section_type!r}, expected {expected_type!r}"
            )

    def test_bar_section_stub_is_registered_in_ir(self, ocx_stub_version):
        """The BarSection wrapper stub carries an id and can be registered."""
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubBarSection, stub_dir, declaration)
        root = _Ns(class_catalogue=_Ns(
            xsection_catalogue=_Ns(bar_section=[raw]),
            material_catalogue=None,
        ))
        ir = _empty_ir()
        OcxV3Builder()._build_sections(root, ir)
        assert len(ir.sections) >= 1


# ---------------------------------------------------------------------------
# Plates
# ---------------------------------------------------------------------------

class TestBuildPlate:

    def test_returns_ir_plate(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPlate, stub_dir, declaration)
        plate = OcxV3Builder()._build_plate(raw, _vessel_parent())
        assert isinstance(plate, IrPlate)

    def test_plate_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPlate, stub_dir, declaration)
        plate = OcxV3Builder()._build_plate(raw, _vessel_parent())
        assert plate.id

    def test_plate_parent_ref_is_vessel(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPlate, stub_dir, declaration)
        parent = _vessel_parent()
        plate = OcxV3Builder()._build_plate(raw, parent)
        assert plate.parent_ref == parent

    def test_plate_has_material_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPlate, stub_dir, declaration)
        plate = OcxV3Builder()._build_plate(raw, _vessel_parent())
        assert plate.material_ref is not None

    def test_plate_has_thickness(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPlate, stub_dir, declaration)
        plate = OcxV3Builder()._build_plate(raw, _vessel_parent())
        assert plate.thickness is not None


# ---------------------------------------------------------------------------
# Brackets
# ---------------------------------------------------------------------------

class TestBuildBracket:

    def _build(self, stub_cls, stub_dir, declaration) -> IrBracket:
        raw = _load(stub_cls, stub_dir, declaration)
        return OcxV3Builder()._build_bracket(raw, _vessel_parent())

    def test_bracket_returns_ir_bracket(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        assert isinstance(self._build(StubBracket, stub_dir, declaration), IrBracket)

    def test_single_bracket_is_connection_reference(self, ocx_stub_version):
        """SingleBracket is a connection reference element, not a standalone bracket.

        _build_bracket() returns None because there is no id/material on it.
        These elements belong to ConnectionConfiguration (see MISSING_IR_CLASSES).
        """
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubSingleBracket, stub_dir, declaration)
        result = OcxV3Builder()._build_bracket(raw, _vessel_parent())
        assert result is None, "SingleBracket should not produce an IrBracket"

    def test_double_bracket_is_connection_reference(self, ocx_stub_version):
        """DoubleBracket is a connection reference element, not a standalone bracket."""
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubDoubleBracket, stub_dir, declaration)
        result = OcxV3Builder()._build_bracket(raw, _vessel_parent())
        assert result is None, "DoubleBracket should not produce an IrBracket"

    def test_bracket_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubBracket, stub_dir, declaration)
        assert result.id

    def test_bracket_has_arm_lengths(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        result = self._build(StubBracket, stub_dir, declaration)
        assert result.arm_length_u is not None or result.arm_length_v is not None

    def test_bracket_parent_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        parent = _vessel_parent()
        raw = _load(StubBracket, stub_dir, declaration)
        result = OcxV3Builder()._build_bracket(raw, parent)
        assert result.parent_ref == parent


# ---------------------------------------------------------------------------
# Stiffeners
# ---------------------------------------------------------------------------

class TestBuildStiffener:

    def test_returns_ir_stiffener(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubStiffener, stub_dir, declaration)
        result = OcxV3Builder()._build_stiffener(raw, _vessel_parent())
        assert isinstance(result, IrStiffener)

    def test_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubStiffener, stub_dir, declaration)
        result = OcxV3Builder()._build_stiffener(raw, _vessel_parent())
        assert result.id

    def test_has_section_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubStiffener, stub_dir, declaration)
        result = OcxV3Builder()._build_stiffener(raw, _vessel_parent())
        assert result.section_ref is not None

    def test_parent_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        parent = _vessel_parent()
        raw = _load(StubStiffener, stub_dir, declaration)
        result = OcxV3Builder()._build_stiffener(raw, parent)
        assert result.parent_ref == parent


# ---------------------------------------------------------------------------
# Pillars
# ---------------------------------------------------------------------------

class TestBuildPillar:

    def test_returns_ir_pillar(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPillar, stub_dir, declaration)
        result = OcxV3Builder()._build_pillar(raw, _vessel_parent())
        assert isinstance(result, IrPillar)

    def test_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPillar, stub_dir, declaration)
        result = OcxV3Builder()._build_pillar(raw, _vessel_parent())
        assert result.id

    def test_parent_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        parent = _vessel_parent()
        raw = _load(StubPillar, stub_dir, declaration)
        result = OcxV3Builder()._build_pillar(raw, parent)
        assert result.parent_ref == parent


# ---------------------------------------------------------------------------
# Edge reinforcements
# ---------------------------------------------------------------------------

class TestBuildEdgeReinforcement:

    def test_returns_ir_edge_reinforcement(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubEdgeReinforcement, stub_dir, declaration)
        result = OcxV3Builder()._build_edge_reinforcement(raw, _vessel_parent())
        assert isinstance(result, IrEdgeReinforcement)

    def test_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubEdgeReinforcement, stub_dir, declaration)
        result = OcxV3Builder()._build_edge_reinforcement(raw, _vessel_parent())
        assert result.id

    def test_has_section_ref(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubEdgeReinforcement, stub_dir, declaration)
        result = OcxV3Builder()._build_edge_reinforcement(raw, _vessel_parent())
        assert result.section_ref is not None


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

class TestBuildPanel:

    def test_returns_ir_panel(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        result = OcxV3Builder()._build_panel(raw, ir, ir.id)
        assert isinstance(result, IrPanel)

    def test_panel_has_id(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        result = OcxV3Builder()._build_panel(raw, ir, ir.id)
        assert result.id

    def test_panel_registers_child_plates(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        OcxV3Builder()._build_panel(raw, ir, ir.id)
        assert len(ir.plates) > 0, "Panel stub should contain at least one child plate"

    def test_panel_plate_refs_match_registered_plates(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        panel = OcxV3Builder()._build_panel(raw, ir, ir.id)
        for pid in panel.plate_ids:
            assert pid in ir.plates, f"Panel plate_id {pid!r} not found in ir.plates"

    def test_panel_bracket_refs_match_registered_brackets(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        panel = OcxV3Builder()._build_panel(raw, ir, ir.id)
        for bid in panel.bracket_ids:
            assert bid in ir.brackets, f"Panel bracket_id {bid!r} not found in ir.brackets"

    def test_panel_stiffener_refs_match_registered_stiffeners(self, ocx_stub_version):
        _, stub_dir, declaration = ocx_stub_version
        raw = _load(StubPanel, stub_dir, declaration)
        ir = _empty_ir()
        panel = OcxV3Builder()._build_panel(raw, ir, ir.id)
        for sid in panel.stiffener_ids:
            assert sid in ir.stiffeners, f"Panel stiffener_id {sid!r} not found in ir.stiffeners"


# ---------------------------------------------------------------------------
# Missing IR class documentation
# ---------------------------------------------------------------------------
# These OCX elements have generated stubs but no typed Ir* class in ir.py.
# The test below confirms each gap is still open.  When you add an Ir* class,
# remove the entry here and add a proper builder test above.

MISSING_IR_CLASSES = [
    # Geometry
    ("Positions",         "coordinate list sub-element"),
    ("CircumCircle3D",    "2D curve cross-section geometry"),
    # Grid / reference planes
    ("XRefPlanes",        "longitudinal reference planes"),
    ("YRefPlanes",        "transverse reference planes"),
    ("ZRefPlanes",        "horizontal reference planes"),
    # Structural connections
    ("WebStiffener",                     "web stiffener connection"),
    ("WebStiffenerWithSingleBracket",    "web stiffener with bracket"),
    # Features
    ("SlotParameters",    "slot geometry parameters"),
    # Holes
    ("HoleContourRef",    "hole contour reference"),
    ("InnerContour",      "inner contour of a section"),
    # Vessel metadata
    ("ClassNotation",     "partially in IrVessel.classification dict"),
    ("Tonnage",           "no dedicated IR class"),
]


class TestMissingIrClasses:
    """Living documentation of IR coverage gaps.

    Each parametrized case confirms that the named Ir* class does not yet
    exist.  When you add ``IrFoo`` to ir.py, the test for ``Foo`` will fail
    with a reminder to remove the entry from ``MISSING_IR_CLASSES`` and add
    a proper builder test.
    """

    @pytest.mark.parametrize(
        "ocx_name,reason",
        MISSING_IR_CLASSES,
        ids=[entry[0] for entry in MISSING_IR_CLASSES],
    )
    def test_ir_class_not_yet_implemented(self, ocx_name, reason):
        import ocx_model_validator.model.ir as ir_module

        ir_class_name = f"Ir{ocx_name}"
        assert not hasattr(ir_module, ir_class_name), (
            f"{ir_class_name} now exists in ir.py — remove {ocx_name!r} from "
            f"MISSING_IR_CLASSES in test_ir_builder.py and add a builder test for it."
        )
