"""Builder dual-path tests: OCX 3.2.0 names first, 3.1.0 fallback."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir import (
    IrCone3D,
    IrCylinder3D,
    IrExtrudedSurface,
    IrNurbsSurface,
    IrSphere3D,
    ParentKind,
    ParentRef,
)

PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _b() -> OcxV3Builder:
    return OcxV3Builder()


def _qty(value, unit):
    return NS(numericvalue=value, unit=unit)


def _cog(x, y, z, unit="Um"):
    return NS(coordinates=[x, y, z], unit=unit)


def test_mass_properties_from_320_element():
    raw = NS(mass_properties=NS(
        moulded_dry_weight=_qty(1200.0, "UKg"),
        physical_dry_weight=_qty(1250.0, "UKg"),
        moulded_center_of_gravity=_cog(1.0, 2.0, 3.0),
        physical_center_of_gravity=_cog(1.1, 2.1, 3.1),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 1200.0
    assert mp.physical_dry_weight.value == 1250.0
    assert mp.moulded_cog.x == 1.0
    assert mp.physical_cog.z == 3.1


def test_mass_properties_falls_back_to_physical_properties():
    raw = NS(physical_properties=NS(
        dry_weight=_qty(300.0, "UKg"),
        center_of_gravity=_cog(5.0, 6.0, 7.0),
    ))
    mp = _b()._mass_properties(raw)
    assert mp.moulded_dry_weight.value == 300.0
    assert mp.moulded_cog.y == 6.0
    assert mp.physical_dry_weight is None
    assert mp.physical_cog is None


def test_mass_properties_absent_returns_none():
    assert _b()._mass_properties(NS()) is None


def test_build_plate_populates_mass_properties():
    raw = NS(id="PL1", name="p", guidref=None, plate_material=None,
             net_area=None, function_type=None, outer_contour=None,
             mass_properties=NS(
                 moulded_dry_weight=_qty(42.0, "UKg"),
                 physical_dry_weight=None,
                 moulded_center_of_gravity=None,
                 physical_center_of_gravity=None))
    plate = _b()._build_plate(raw, PARENT)
    assert plate.mass_properties.moulded_dry_weight.value == 42.0


def _material_root(**mc_kwargs):
    defaults = {"material": [], "steel": [], "aluminium": []}
    defaults.update(mc_kwargs)
    return NS(class_catalogue=NS(material_catalogue=NS(**defaults)))


def test_build_materials_steel_and_aluminium_320():
    from ocx_model_validator.model.ir import IrVessel
    steel = NS(id="M1", name="NV A36", guidref=None, grade=NS(value="A36"),
               density=_qty(7850.0, "Ukgoverm3"),
               yield_stress=_qty(355.0, "UNOvermm2"),
               ultimate_stress=_qty(490.0, "UNOvermm2"),
               youngs_modulus=_qty(206000.0, "UNOvermm2"),
               poisson_ratio=_qty(0.3, "Unitless"),
               thermal_expansion_coefficient=None)
    alu = NS(id="M2", name="AW-5083", guidref=None,
             density=_qty(2660.0, "Ukgoverm3"),
             unwelded_yield_strength=_qty(125.0, "UNOvermm2"),
             welded_yield_strength=_qty(115.0, "UNOvermm2"),
             unwelded_tensile_strength=_qty(275.0, "UNOvermm2"),
             welded_tensile_strength=_qty(270.0, "UNOvermm2"),
             alloy_designation="5083",
             youngs_modulus=None, poisson_ratio=None,
             thermal_expansion_coefficient=None)
    root = _material_root(steel=[steel], aluminium=[alu])
    ir = IrVessel(id="v1")
    _b()._build_materials(root, ir)
    m1, m2 = ir.materials["M1"], ir.materials["M2"]
    assert m1.material_type == "steel"
    assert m1.grade == "A36" and m1.yield_stress.value == 355.0
    assert m2.material_type == "aluminium"
    assert m2.unwelded_yield_strength.value == 125.0
    assert m2.welded_tensile_strength.value == 270.0
    assert m2.alloy_designation == "5083"


def test_build_materials_legacy_material_fallback():
    from ocx_model_validator.model.ir import IrVessel
    legacy = NS(id="M9", name="steel", guidref=None, grade=None,
                density=_qty(7850.0, "Ukgoverm3"),
                yield_stress=_qty(235.0, "UNOvermm2"),
                ultimate_stress=None, youngs_modulus=None,
                poisson_ratio=None, thermal_expansion=None)
    root = _material_root(material=[legacy])
    ir = IrVessel(id="v1")
    _b()._build_materials(root, ir)
    m = ir.materials["M9"]
    assert m.material_type is None
    assert m.yield_stress.value == 235.0


def test_plate_material_renewal_thickness():
    raw = NS(id="PL2", name=None, guidref=None,
             plate_material=NS(local_ref="M1", guidref=None,
                               thickness=_qty(12.0, "Umm"),
                               renewal_thickness=_qty(10.5, "Umm"),
                               voluntary_thickness_addition=_qty(1.0, "Umm")),
             net_area=None, function_type=None, outer_contour=None)
    plate = _b()._build_plate(raw, PARENT)
    assert plate.thickness.value == 12.0
    assert plate.renewal_thickness.value == 10.5
    assert plate.voluntary_thickness_addition.value == 1.0


def test_stiffener_section_ref_scantlings():
    raw = NS(id="ST2", name=None, guidref=None, material_ref=None,
             function_type=None, end_cut_end1=None, end_cut_end2=None,
             trace_line=None, inclination=None,
             section_ref=NS(local_ref="SEC1", guidref=None,
                            web_renewal_thickness=_qty(6.0, "Umm"),
                            flange_renewal_thickness=_qty(7.0, "Umm"),
                            voluntary_web_thickness_addition=_qty(0.5, "Umm"),
                            voluntary_flange_thickness_addition=_qty(0.7, "Umm")))
    st = _b()._build_stiffener(raw, PARENT)
    assert st.section_ref.local_ref == "SEC1"
    assert st.web_renewal_thickness.value == 6.0
    assert st.flange_renewal_thickness.value == 7.0
    assert st.voluntary_web_thickness_addition.value == 0.5
    assert st.voluntary_flange_thickness_addition.value == 0.7


def test_round_bar_height_fallback():
    class RoundBar(NS):
        pass
    sec = RoundBar(id="S_RB", name=None, guidref=None,
                   height=_qty(30.0, "Umm"))
    ir_sec = _b()._build_section(sec)
    assert ir_sec.diameter.value == 30.0


def test_bar_section_catalogue_reference():
    class FlatBar(NS):
        pass
    class BarSection(NS):
        pass
    bar = BarSection(id="S_FB", name="FB100", guidref=None,
                     catalogue_reference="EN10058-FB100x10",
                     flat_bar=FlatBar(height=_qty(100.0, "Umm"),
                                      width=_qty(10.0, "Umm")))
    ir_sec = _b()._build_section(bar)
    assert ir_sec.catalogue_reference == "EN10058-FB100x10"
    assert ir_sec.height.value == 100.0


def _pt3(x, y, z, unit="Um"):
    return NS(coordinates=[x, y, z], unit=unit)


def _dir3(x, y, z):
    return NS(direction=[x, y, z])


def test_plane3d_point_on_surface_320():
    class Plane3D(NS):
        pass
    p = Plane3D(id="P1", point_on_surface=_pt3(4.5, -5.7, 1.5),
                normal=_dir3(1.0, 0.0, 0.0), udirection=None)
    ir = _b()._build_surface(p)
    assert ir.point_on_surface.x == 4.5
    assert ir.normal.x == 1.0


def test_plane3d_origin_fallback_310():
    class Plane3D(NS):
        pass
    p = Plane3D(id="P2", origin=_pt3(0.0, 1.0, 2.0),
                normal=_dir3(0.0, 0.0, 1.0), udirection=None)
    ir = _b()._build_surface(p)
    assert ir.point_on_surface.y == 1.0


class Sphere3D(NS):
    pass


class Cone3D(NS):
    pass


class Cylinder3D(NS):
    pass


class ExtrudedSurface(NS):
    pass


class NurbsSurface(NS):
    pass


@pytest.mark.parametrize(
    ("surface_cls", "ir_cls", "attrs"),
    [
        (Sphere3D, IrSphere3D, {"id": "S1", "radius": _qty(2.0, "Um")}),
        (Cone3D, IrCone3D, {"id": "CO1", "base_radius": _qty(2.0, "Um"), "tip_radius": _qty(0.5, "Um")}),
        (Cylinder3D, IrCylinder3D, {"id": "C1", "radius": _qty(2.0, "Um"), "height": _qty(10.0, "Um")}),
        (ExtrudedSurface, IrExtrudedSurface, {"id": "E1"}),
        (NurbsSurface, IrNurbsSurface, {"id": "N1"}),
    ],
)
def test_surfaces_extract_normal_and_point_on_surface(surface_cls, ir_cls, attrs):
    surface = surface_cls(
        normal=_dir3(1.0, 0.0, 0.0),
        point_on_surface=_pt3(2.0, 0.0, 5.0),
        **attrs,
    )
    ir = _b()._build_surface(surface)
    assert isinstance(ir, ir_cls)
    assert ir.normal.x == 1.0
    assert ir.point_on_surface.z == 5.0
