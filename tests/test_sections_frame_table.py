"""FrameTable extraction from IR ref planes."""
import pytest

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.geometry import IrCoordinateSystem, IrRefPlane
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.sections.frame_table import FrameTable, build_frame_table


def _vessel(planes, x_ids=None):
    ir = IrVessel(id="v1")
    for p in planes:
        ir.ref_planes[p.id] = p
    ir.coordinate_systems["global"] = IrCoordinateSystem(
        id="global",
        is_global=True,
        x_ref_plane_ids=x_ids if x_ids is not None else [p.id for p in planes],
    )
    return ir


def _plane(pid, name, x_m):
    return IrRefPlane(id=pid, name=name, location=Quantity(x_m, "Um"))


def test_positions_sorted_and_labeled():
    ir = _vessel([_plane("b", "X4", 4.0), _plane("a", "X0", 0.0),
                  _plane("c", "X8.8", 8.8)])
    ft = build_frame_table(ir)
    assert ft.positions == [("0", 0.0), ("4", pytest.approx(4000.0)),
                            ("8.8", pytest.approx(8800.0))]


def test_entries_emitted_on_spacing_change():
    # 0, 4, 8 (spacing 4000) then 8.8, 9.6 (spacing 800)
    ir = _vessel([_plane(f"p{i}", n, x) for i, (n, x) in enumerate(
        [("X0", 0.0), ("X4", 4.0), ("X8", 8.0), ("X8.8", 8.8), ("X9.6", 9.6)])])
    ft = build_frame_table(ir)
    assert ft.entries == [("0", pytest.approx(4000.0)),
                          ("8", pytest.approx(800.0))]
    assert ft.frame0_offset_mm == pytest.approx(0.0)


def test_frame0_offset_falls_back_to_lowest():
    ir = _vessel([_plane("a", "X-2", -2.0), _plane("b", "X2", 2.0)])
    assert build_frame_table(ir).frame0_offset_mm == pytest.approx(-2000.0)


def test_non_numeric_names_kept_verbatim():
    ir = _vessel([_plane("a", "AP", 0.0), _plane("b", "X10", 10.0)])
    ft = build_frame_table(ir)
    assert ft.positions[0][0] == "AP"


def test_planes_without_location_skipped_with_warning():
    ir = _vessel([_plane("a", "X0", 0.0),
                  IrRefPlane(id="b", name="X5"), _plane("c", "X10", 10.0)])
    ft = build_frame_table(ir)
    assert len(ft.positions) == 2
    assert any("X5" in w or "b" in w for w in ft.warnings)


def test_no_x_planes_raises():
    with pytest.raises(SectionError):
        build_frame_table(_vessel([]))


def test_ignores_non_x_ref_planes_not_in_coordinate_system():
    ir = _vessel(
        [_plane("x0", "X0", 0.0), _plane("x5", "X5", 5.0), _plane("Z5", "Z5", 5.0)],
        x_ids=["x0", "x5"],
    )
    ft = build_frame_table(ir)
    assert ft.positions == [("0", pytest.approx(0.0)), ("5", pytest.approx(5000.0))]


def test_frame_to_x_and_nearest():
    ir = _vessel([_plane("a", "X0", 0.0), _plane("b", "X4", 4.0)])
    ft = build_frame_table(ir)
    assert ft.frame_to_x("4") == pytest.approx(4000.0)
    with pytest.raises(SectionError):
        ft.frame_to_x("99")
    assert ft.nearest_frame(3900.0) == ("4", pytest.approx(4000.0))


def test_frame0_numeric_match_x0_0_label():
    """Plane named X0.0 at 0.0 should be found even if a lower negative-x plane exists."""
    ir = _vessel([_plane("a", "X-2", -2.0), _plane("b", "X0.0", 0.0),
                  _plane("c", "X4", 4.0)])
    ft = build_frame_table(ir)
    assert ft.frame0_offset_mm == pytest.approx(0.0)


def test_frame0_numeric_match_x00_label():
    """Plane named X00 at 0.0 should be found."""
    ir = _vessel([_plane("a", "X-1", -1.0), _plane("b", "X00", 0.0),
                  _plane("c", "X5", 5.0)])
    ft = build_frame_table(ir)
    assert ft.frame0_offset_mm == pytest.approx(0.0)


def test_coincident_planes_dropped_with_warning():
    """Two planes < 1mm apart: keep first, drop second, append warning."""
    ir = _vessel([_plane("a", "X0", 0.0), _plane("b", "X0.5", 0.0005),
                  _plane("c", "X10", 10.0)])
    ft = build_frame_table(ir)
    # Should have 2 positions (first and last), middle one dropped
    assert len(ft.positions) == 2
    assert ft.positions == [("0", pytest.approx(0.0)), ("10", pytest.approx(10000.0))]
    # Warning should mention the dropped plane
    assert any("coincident" in w.lower() or "0.5" in w for w in ft.warnings)


def test_duplicate_labels_warning():
    """Two planes with the same label at different x positions should trigger warning."""
    ir = _vessel([_plane("a", "X4", 4.0), _plane("b", "X4", 8.0),
                  _plane("c", "X10", 10.0)])
    ft = build_frame_table(ir)
    # Should keep both positions (same label, different x)
    assert len(ft.positions) == 3
    assert ft.positions == [("4", pytest.approx(4000.0)), ("4", pytest.approx(8000.0)),
                            ("10", pytest.approx(10000.0))]
    # Warning should mention the duplicate label
    assert any("4" in w and ("duplicate" in w.lower() or "appears" in w.lower())
               for w in ft.warnings)
