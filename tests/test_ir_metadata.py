"""Unit tests for vessel metadata IR dataclasses."""
from __future__ import annotations

from ocx_model_validator.model.ir import (
    IrBuilderInformation,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
    IrTonnageData,
    Quantity,
)


def test_ship_designation_defaults():
    s = IrShipDesignation()
    assert s.ship_name is None and s.number_imo is None
    s2 = IrShipDesignation(ship_name="MV Test", number_imo="1234567")
    assert s2.ship_name == "MV Test" and s2.number_imo == "1234567"


def test_tonnage_data_defaults():
    t = IrTonnageData()
    assert t.tonnage is None and t.dead_weight is None


def test_principal_particulars_fields():
    pp = IrPrincipalParticulars(lpp=Quantity(200.0, "Um"))
    assert pp.lpp == Quantity(200.0, "Um")
    assert pp.moulded_breadth is None
    assert pp.block_coefficient is None


def test_statutory_data_fields():
    st = IrStatutoryData(port_registration="Oslo", flag_state="NO")
    assert st.port_registration == "Oslo" and st.flag_state == "NO"


def test_builder_information_defaults():
    b = IrBuilderInformation(yard="Yard X")
    assert b.yard == "Yard X"
    assert b.designer is None and b.year_of_build is None
