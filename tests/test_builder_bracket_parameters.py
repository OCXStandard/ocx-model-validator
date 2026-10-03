"""Builder extraction of the full BracketParameters set onto IrBracket.

Covers nose dimensions, free edge radius, reinforcement type, the
FeatureCope sub-element and the FlangeEdgeReinforcement sub-element.
Uses inline stub objects (builders access raw OCX fields via getattr).
"""
from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir.base import ParentKind, ParentRef, Quantity


class _Qty:
    def __init__(self, value: float, unit: str = "Umm"):
        self.numericvalue = value
        self.unit = unit


class _Enum:
    def __init__(self, value: str):
        self.value = value


class _FeatureCope:
    def __init__(self):
        self.id = "FC1"
        self.name = "Cope"
        self.cope_radius = _Qty(30.0)
        self.cope_length = _Qty(80.0)
        self.cope_height = _Qty(40.0)


class _FlangeEdgeReinforcement:
    def __init__(self):
        self.flange_width = _Qty(100.0)
        self.radius = _Qty(25.0)


class _Point:
    def __init__(self, coords, unit="Um"):
        self.coordinates = coords
        self.unit = unit


class _Vector:
    def __init__(self, direction):
        self.direction = direction


class _BracketParameters:
    def __init__(self):
        self.arm_length_u = _Qty(300.0)
        self.arm_length_v = _Qty(350.0)
        self.origin = _Point([10.0, 2.0, 8.0])
        self.udirection = _Vector([1.0, 0.0, 0.0])
        self.vdirection = _Vector([0.0, 0.0, 1.0])
        self.unose = _Qty(50.0)
        self.vnose = _Qty(60.0)
        self.free_edge_radius = _Qty(400.0)
        self.has_edge_reinforcement = True
        self.number_of_supports = 2
        self.reinforcement_type = _Enum("Flanged")
        self.feature_cope = _FeatureCope()
        self.flange_edge_reinforcement = _FlangeEdgeReinforcement()


class _Bracket:
    def __init__(self):
        self.id = "BR1"
        self.name = "Tripping bracket"
        self.guidref = None
        self.plate_material = None
        self.physical_properties = None
        self.bracket_parameters = _BracketParameters()


def _build():
    parent = ParentRef(kind=ParentKind.PANEL, id="PAN1")
    return OcxV3Builder()._build_bracket(_Bracket(), parent)


def test_bracket_nose_and_free_edge_radius():
    b = _build()
    assert b.unose == Quantity(50.0, "Umm")
    assert b.vnose == Quantity(60.0, "Umm")
    assert b.free_edge_radius == Quantity(400.0, "Umm")


def test_bracket_reinforcement_type():
    b = _build()
    assert b.reinforcement_type == "Flanged"


def test_bracket_feature_cope():
    b = _build()
    fc = b.feature_cope
    assert fc is not None
    assert fc.id == "FC1"
    assert fc.name == "Cope"
    assert fc.cope_radius == Quantity(30.0, "Umm")
    assert fc.cope_length == Quantity(80.0, "Umm")
    assert fc.cope_height == Quantity(40.0, "Umm")


def test_bracket_flange_edge_reinforcement():
    b = _build()
    assert b.flange_width == Quantity(100.0, "Umm")
    assert b.flange_radius == Quantity(25.0, "Umm")


def test_bracket_origin_and_directions():
    b = _build()
    assert (b.origin.x, b.origin.y, b.origin.z) == (10.0, 2.0, 8.0)
    assert b.origin.unit == "Um"
    assert (b.udirection.x, b.udirection.y, b.udirection.z) == (1.0, 0.0, 0.0)
    assert (b.vdirection.x, b.vdirection.y, b.vdirection.z) == (0.0, 0.0, 1.0)


def test_bracket_without_parameters_defaults():
    br = _Bracket()
    br.bracket_parameters = None
    b = OcxV3Builder()._build_bracket(
        br, ParentRef(kind=ParentKind.VESSEL, id="V1"))
    assert b.unose is None
    assert b.vnose is None
    assert b.free_edge_radius is None
    assert b.reinforcement_type is None
    assert b.feature_cope is None
    assert b.flange_width is None
    assert b.flange_radius is None
    assert b.origin is None
    assert b.udirection is None
    assert b.vdirection is None
