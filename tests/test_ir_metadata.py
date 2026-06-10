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
    assert s.vessel_name is None and s.imo_number is None
    s2 = IrShipDesignation(vessel_name="MV Test", imo_number="1234567")
    assert s2.vessel_name == "MV Test" and s2.imo_number == "1234567"


def test_tonnage_data_defaults():
    t = IrTonnageData()
    assert t.gross_tonnage is None and t.net_tonnage is None


def test_principal_particulars_fields():
    pp = IrPrincipalParticulars(lpp=Quantity(200.0, "Um"))
    assert pp.lpp == Quantity(200.0, "Um")
    assert pp.moulded_breadth is None
    assert pp.block_coefficient is None


def test_statutory_data_holds_tonnage():
    st = IrStatutoryData(tonnage_data=IrTonnageData(gross_tonnage=Quantity(50000.0, "")))
    assert st.tonnage_data.gross_tonnage == Quantity(50000.0, "")
    assert st.freeboard_type is None


def test_builder_information_defaults():
    b = IrBuilderInformation(builder_name="Yard X")
    assert b.builder_name == "Yard X"
    assert b.yard_number is None and b.delivery_date is None
