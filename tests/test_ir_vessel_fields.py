"""Unit tests for new IrVessel collection and metadata fields."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBuilderInformation,
    IrBulkCargo,
    IrCoordinateSystem,
    IrDesignView,
    IrGaseousCargo,
    IrHoleShapeCatalogue,
    IrLiquidCargo,
    IrMember,
    IrPrincipalParticulars,
    IrRefPlane,
    IrSeam,
    IrShipDesignation,
    IrStatutoryData,
    IrSurface,
    IrSurfaceCollection,
    IrUnitCargo,
    IrVessel,
    ParentKind,
    ParentRef,
)


def test_new_collection_dicts_default_empty():
    v = IrVessel(id="v1")
    for attr in (
        "seams", "members", "liquid_cargoes", "gaseous_cargoes",
        "bulk_cargoes", "unit_cargoes", "coordinate_systems", "ref_planes",
        "surfaces", "surface_collections", "design_views",
        "connection_configurations",
    ):
        assert getattr(v, attr) == {}, attr
    assert v.hole_shape_catalogue is None


def test_typed_metadata_fields_default_none():
    v = IrVessel(id="v1")
    assert v.ship_designation is None
    assert v.principal_particulars is None
    assert v.statutory_data is None
    assert v.builder_info is None
    assert v.classification is None


def test_typed_metadata_assignment():
    v = IrVessel(id="v1")
    v.ship_designation = IrShipDesignation(vessel_name="MV Test")
    v.principal_particulars = IrPrincipalParticulars()
    v.statutory_data = IrStatutoryData()
    v.builder_info = IrBuilderInformation(builder_name="Yard X")
    assert v.ship_designation.vessel_name == "MV Test"
    assert isinstance(v.builder_info, IrBuilderInformation)


def test_new_lookup_helpers():
    v = IrVessel(id="v1")
    parent = ParentRef(kind=ParentKind.VESSEL, id="v1")
    v.seams["s1"] = IrSeam(id="s1")
    v.members["m1"] = IrMember(id="m1", parent_ref=parent)
    assert v.get_seam("s1").id == "s1"
    assert v.get_member("m1").id == "m1"
    assert v.get_seam("missing") is None
    assert v.get_member("missing") is None


def test_collections_accept_their_types():
    v = IrVessel(id="v1")
    v.liquid_cargoes["lc"] = IrLiquidCargo(id="lc")
    v.gaseous_cargoes["gc"] = IrGaseousCargo(id="gc")
    v.bulk_cargoes["bc"] = IrBulkCargo(id="bc")
    v.unit_cargoes["uc"] = IrUnitCargo(id="uc")
    v.coordinate_systems["cs"] = IrCoordinateSystem(id="cs")
    v.ref_planes["rp"] = IrRefPlane(id="rp")
    v.surfaces["sf"] = IrSurface(id="sf")
    v.surface_collections["scoll"] = IrSurfaceCollection(id="scoll")
    v.design_views["dv"] = IrDesignView(id="dv")
    v.hole_shape_catalogue = IrHoleShapeCatalogue(id="cat")
    assert v.liquid_cargoes["lc"].id == "lc"
    assert v.hole_shape_catalogue.id == "cat"
