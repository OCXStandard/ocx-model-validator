"""Catalogue report generator — materials, cross sections, openings."""
from __future__ import annotations

import dataclasses

from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.reporting.generators._common import (
    qty_mm_cell,
    qty_mpa_cell,
    qty_t_per_m3_cell,
    report_metadata,
)
from ocx_model_validator.reporting.model import Cell, Report, ReportSection, ReportTable

# Non-dimension fields on IrSection subclasses (see model/ir/sections.py)
_SECTION_BASE_FIELDS = {"id", "name", "guidref", "section_type", "extra"}


def _materials_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    reg = vessel.unit_registry
    rows: list[list[Cell]] = []
    for m in sorted(vessel.materials.values(), key=lambda m: m.name or m.id):
        ctx = f"material {m.id}"
        rows.append([
            m.id, m.name, m.grade,
            qty_t_per_m3_cell(m.density, reg, notes, f"{ctx} density"),
            qty_mpa_cell(m.yield_stress, reg, notes, f"{ctx} yield"),
            qty_mpa_cell(m.ultimate_stress, reg, notes, f"{ctx} ultimate"),
            qty_mpa_cell(m.youngs_modulus, reg, notes, f"{ctx} E"),
        ])
    columns = ["Id", "Name", "Grade", "Density (t/m³)",
               "Yield (MPa)", "Ultimate (MPa)", "E (MPa)"]
    return ReportSection(title="Materials",
                         tables=[ReportTable("Materials", columns, rows)],
                         notes=notes)


def _section_type_name(section) -> str:
    if section.section_type:
        return section.section_type
    return type(section).__name__.removeprefix("Ir").removesuffix("Section")


def _sections_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    reg = vessel.unit_registry
    secs = sorted(vessel.sections.values(), key=lambda s: s.name or s.id)
    dim_names = sorted({
        f.name for s in secs for f in dataclasses.fields(s)
        if f.name not in _SECTION_BASE_FIELDS
        and isinstance(getattr(s, f.name, None), Quantity)
    })
    columns = ["Id", "Name", "Type"] + [f"{n} (mm)" for n in dim_names]
    rows: list[list[Cell]] = []
    for s in secs:
        row: list[Cell] = [s.id, s.name, _section_type_name(s)]
        for n in dim_names:
            value = getattr(s, n, None)
            if isinstance(value, Quantity):
                row.append(qty_mm_cell(value, reg, notes,
                                       f"section {s.id} {n}"))
            else:
                row.append(None)
        rows.append(row)
    return ReportSection(title="Cross sections",
                         tables=[ReportTable("Cross sections", columns, rows)],
                         notes=notes)


def _openings_section(vessel: IrVessel) -> ReportSection:
    notes: list[str] = []
    rows: list[list[Cell]] = []
    cat = vessel.hole_shape_catalogue
    if cat is None:
        notes.append("Model has no hole shape catalogue")
    else:
        for h in sorted(cat.holes.values(), key=lambda h: h.name or h.id):
            parametric = "; ".join(f"{k}={v}" for k, v in (h.parametric or {}).items())
            rows.append([h.id, h.name, parametric or None])
    return ReportSection(title="Openings",
                         tables=[ReportTable("Hole shapes",
                                             ["Id", "Name", "Parametric dimensions"],
                                             rows)],
                         notes=notes)


def build(vessel: IrVessel, which: str = "all", source_file: str = "") -> Report:
    """Build the catalogue report. ``which``: material|section|opening|all."""
    builders = {
        "material": _materials_section,
        "section": _sections_section,
        "opening": _openings_section,
    }
    if which != "all" and which not in builders:
        raise ValueError(f"unknown catalogue {which!r}; expected material|section|opening|all")
    keys = list(builders) if which == "all" else [which]
    sections = [builders[k](vessel) for k in keys]
    return Report(title="Catalogue report",
                  metadata=report_metadata(vessel, source_file),
                  sections=sections)
