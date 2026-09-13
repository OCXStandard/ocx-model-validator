"""IR: stiffener inclination records."""
from ocx_model_validator.model.ir.base import ParentKind, ParentRef
from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
from ocx_model_validator.model.ir.structural import IrInclination, IrStiffener


def test_inclination_fields():
    inc = IrInclination(
        web_direction=IrVector3D(0.0, 0.0, 1.0),
        flange_direction=None,
        position=IrPoint3D(1.0, 2.0, 3.0, "Um"),
    )
    assert inc.web_direction.z == 1.0
    assert inc.flange_direction is None
    assert inc.position.unit == "Um"


def test_stiffener_inclinations_default_empty():
    s = IrStiffener(id="S1", parent_ref=ParentRef(kind=ParentKind.VESSEL, id="V1"))
    assert s.inclinations == []
