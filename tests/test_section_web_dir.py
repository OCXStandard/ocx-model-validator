"""Section builder: projected stiffener web direction."""
import math

from ocx_model_validator.model.ir.geometry import IrPoint3D, IrVector3D
from ocx_model_validator.model.ir.structural import IrInclination
from ocx_model_validator.sections.section_builder import SectionStiffener, _web_dir


def _mk_stiffener(inclinations):
    class _S:
        name = "L1"

    s = _S()
    s.inclinations = inclinations
    return s


def _to_mm(p: IrPoint3D):
    factor = 1000.0 if p.unit == "Um" else 1.0
    return (p.x * factor, p.y * factor, p.z * factor)


def test_web_dir_projects_and_normalizes():
    inc = IrInclination(web_direction=IrVector3D(0.0, 3.0, 4.0))
    warnings: list[str] = []
    y, z = _web_dir(_mk_stiffener([inc]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert math.isclose(y, 0.6)
    assert math.isclose(z, 0.8)
    assert warnings == []


def test_web_dir_picks_nearest_position():
    inc_a = IrInclination(
        web_direction=IrVector3D(0.0, 0.0, 1.0),
        position=IrPoint3D(0.0, 0.0, 0.0, "Um"),
    )
    inc_b = IrInclination(
        web_direction=IrVector3D(0.0, 1.0, 0.0),
        position=IrPoint3D(50.0, 0.0, 0.0, "Um"),
    )
    warnings: list[str] = []
    y, z = _web_dir(
        _mk_stiffener([inc_a, inc_b]), x_mm=49_000.0, to_mm=_to_mm, warnings=warnings
    )
    assert (y, z) == (1.0, 0.0)


def test_web_dir_missing_inclination_returns_none_and_warns():
    warnings: list[str] = []
    result = _web_dir(_mk_stiffener([]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert result == (None, None)
    assert any("no inclination" in w for w in warnings)


def test_web_dir_x_only_vector_is_degenerate():
    inc = IrInclination(web_direction=IrVector3D(1.0, 0.0, 0.0))
    warnings: list[str] = []
    result = _web_dir(_mk_stiffener([inc]), x_mm=0.0, to_mm=_to_mm, warnings=warnings)
    assert result == (None, None)
    assert warnings


def test_section_stiffener_has_web_dir_fields():
    s = SectionStiffener(
        name="L1",
        y_mm=0.0,
        z_mm=0.0,
        panel=None,
        profile_type=None,
        profile_dimensions=None,
        material_reh_mpa=None,
        spacing_mm=None,
    )
    assert s.web_dir_y is None
    assert s.web_dir_z is None
