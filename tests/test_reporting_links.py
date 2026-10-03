"""Tests for internal cross-link emission by report generators."""
from ocx_model_validator.model.ir.base import ParentKind, ParentRef
from ocx_model_validator.model.ir.catalogues import IrMaterial
from ocx_model_validator.model.ir.sections import IrFlatBarSection
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators import catalogues as catalogues_gen

_PARENT = ParentRef(kind=ParentKind.VESSEL, id="V1")


def _vessel() -> IrVessel:
    v = IrVessel(id="V1", name="MV Test", schema_version="3.1.0")
    v.materials["M1"] = IrMaterial(id="M1", name="NV A36")
    v.materials["M2"] = IrMaterial(id="M2", name="AH36")
    v.sections["S1"] = IrFlatBarSection(id="S1", name="FB200x20")
    return v


def test_materials_table_row_anchors_follow_sorted_rows():
    report = catalogues_gen.build(_vessel(), which="material")
    table = report.sections[0].tables[0]
    # rows sorted by name: AH36 (M2) before NV A36 (M1)
    assert [r[0] for r in table.rows] == ["M2", "M1"]
    assert table.row_anchors == ["material-M2", "material-M1"]


def test_sections_table_row_anchors():
    report = catalogues_gen.build(_vessel(), which="section")
    table = report.sections[0].tables[0]
    assert table.row_anchors == ["section-S1"]


def test_openings_table_has_no_anchors():
    report = catalogues_gen.build(_vessel(), which="opening")
    assert report.sections[0].tables[0].row_anchors == []
