"""Tests for report generators."""
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_mpa_cell,
    qty_tonnes_cell,
    report_metadata,
)
from ocx_model_validator.model.ir.structural import IrVessel


def test_qty_mm_cell_converts():
    notes: list[str] = []
    assert qty_mm_cell(Quantity(0.5, "Um"), {}, notes, "x") == 500.0
    assert notes == []


def test_qty_cell_none_passthrough():
    notes: list[str] = []
    assert qty_mm_cell(None, {}, notes, "x") is None
    assert notes == []


def test_qty_cell_unknown_unit_falls_back_to_raw():
    notes: list[str] = []
    cell = qty_mm_cell(Quantity(12.5, "Ubogus"), {}, notes, "plate P1 thickness")
    assert cell == "12.5 Ubogus"
    assert notes == ["plate P1 thickness: unknown unit 'Ubogus'; raw value shown"]


def test_qty_mpa_cell_is_integer():
    notes: list[str] = []
    assert qty_mpa_cell(Quantity(235.0, "UMPa"), {}, notes, "x") == 235


def test_qty_tonnes_cell():
    notes: list[str] = []
    assert qty_tonnes_cell(Quantity(1500.0, "UKg"), {}, notes, "x") == 1.5


def test_report_metadata():
    vessel = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    md = report_metadata(vessel, "model.3docx")
    assert md["Vessel"] == "MV Test"
    assert md["Schema version"] == "3.1.0"
    assert md["Source"] == "model.3docx"
    assert "Generated" in md
