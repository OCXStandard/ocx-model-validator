from __future__ import annotations

from ocx_model_validator.model.ir.arrangement import IrCompartment
from ocx_model_validator.model.ir.base import IrCog, ParentKind, ParentRef, Quantity, Ref
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.geometry import (
    IrCoordinateSystem,
    IrCurve3D,
    IrLine3D,
    IrPoint3D,
    IrPolyLine3D,
    IrRefPlane,
)
from ocx_model_validator.model.ir.sections import IrBulbFlatSection
from ocx_model_validator.model.ir.structural import IrPanel, IrPlate, IrStiffener, IrVessel


def q(value: float, unit: str) -> Quantity:
    return Quantity(value, unit)


def p(x: float, y: float, z: float, unit: str = "Um") -> IrPoint3D:
    return IrPoint3D(x=x, y=y, z=z, unit=unit)


def line(y: float, z: float, start_x: float = 0.0, end_x: float = 10.0) -> IrLine3D:
    return IrLine3D(curve_length=None, start=p(start_x, y, z), end=p(end_x, y, z))


def rectangle(y1: float, y2: float, z: float) -> IrPolyLine3D:
    return IrPolyLine3D(
        curve_length=None,
        vertices=[p(4.0, y1, z), p(6.0, y1, z), p(6.0, y2, z), p(4.0, y2, z)],
        is_closed=True,
    )


def four_hit_plate_contour() -> IrPolyLine3D:
    """Closed contour crossing x=5m at (y,z) mm: (0,0), (2000,50), (3000,45), (6000,0)."""
    return IrPolyLine3D(
        curve_length=None,
        vertices=[
            p(4.0, 0.0, 0.0),
            p(6.0, 0.0, 0.0),
            p(6.0, 2.0, 0.05),
            p(4.0, 2.0, 0.05),
            p(4.0, 3.0, 0.045),
            p(6.0, 3.0, 0.045),
            p(6.0, 6.0, 0.0),
            p(4.0, 6.0, 0.0),
        ],
        is_closed=True,
    )


def parent(panel_id: str) -> ParentRef:
    return ParentRef(ParentKind.PANEL, panel_id)


def make_synthetic_vessel() -> IrVessel:
    vessel = IrVessel(id="vessel-1")
    vessel.coordinate_systems["global"] = IrCoordinateSystem(
        id="global",
        is_global=True,
        x_ref_plane_ids=["fr0", "fr5", "fr10"],
    )
    vessel.ref_planes["fr0"] = IrRefPlane(id="fr0", name="X0", location=q(0.0, "Um"))
    vessel.ref_planes["fr5"] = IrRefPlane(id="fr5", name="X5", location=q(5.0, "Um"))
    vessel.ref_planes["fr10"] = IrRefPlane(id="fr10", name="X10", location=q(10.0, "Um"))
    vessel.materials["mat315"] = IrMaterial(
        id="mat315",
        name="NV-NS",
        yield_stress=q(315e6, "UPa"),
    )
    vessel.sections["hp300"] = IrBulbFlatSection(
        id="hp300",
        name="HP 300x11",
        height=q(300.0, "Umm"),
        web_thickness=q(11.0, "Umm"),
    )
    vessel.panels["panel-a"] = IrPanel(
        id="panel-a",
        name="Panel A",
        guidref="panel-a-guid",
        plate_ids=["plate-a1", "plate-a2"],
        stiffener_ids=["stiff-a1", "stiff-a2", "stiff-a-no-cross"],
    )
    vessel.panels["panel-b"] = IrPanel(
        id="panel-b",
        name="Panel B",
        stiffener_ids=["stiff-b1"],
    )
    vessel.plates["plate-a1"] = IrPlate(
        id="plate-a1",
        parent_ref=parent("panel-a"),
        name="Plate A1",
        guidref="plate-a1-guid",
        material_ref=Ref("mat315"),
        thickness=q(12.5, "Umm"),
        cog=IrCog(5.0, 0.25, 0.0, "Um"),
        outer_contour=rectangle(0.0, 2.0, 0.0),
    )
    vessel.plates["plate-a2"] = IrPlate(
        id="plate-a2",
        parent_ref=parent("panel-a"),
        name="Plate A2",
        material_ref=Ref("mat315"),
        thickness=q(10.0, "Umm"),
        cog=IrCog(5.0, 1.75, 1.0, "Um"),
        outer_contour=rectangle(0.0, 2.0, 1.0),
    )
    vessel.stiffeners["stiff-a1"] = IrStiffener(
        id="stiff-a1",
        parent_ref=parent("panel-a"),
        name="A bulb",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(0.4, 0.1),
    )
    vessel.stiffeners["stiff-a2"] = IrStiffener(
        id="stiff-a2",
        parent_ref=parent("panel-a"),
        name="A missing profile",
        material_ref=Ref("mat315"),
        trace=line(1.2, 0.1),
    )
    vessel.stiffeners["stiff-a-no-cross"] = IrStiffener(
        id="stiff-a-no-cross",
        parent_ref=parent("panel-a"),
        name="A no cross",
        trace=line(9.0, 9.0, start_x=0.0, end_x=4.0),
    )
    vessel.stiffeners["stiff-b1"] = IrStiffener(
        id="stiff-b1",
        parent_ref=parent("panel-b"),
        name="B alone",
        material_ref=Ref("mat315"),
        section_ref=Ref("hp300"),
        trace=line(3.0, 0.2),
    )
    vessel.compartments["ballast"] = IrCompartment(
        id="ballast",
        name="Ballast Tank",
        compartment_purpose="ballast water",
        volume=q(123.456, "Um3"),
        face_refs=[Ref("panel-a")],
        cog=IrCog(5.0, 1.0, 0.5, "Um"),
    )
    vessel.compartments["empty"] = IrCompartment(
        id="empty",
        name="Unclassified Space",
        face_refs=[Ref("missing-panel")],
    )
    return vessel
