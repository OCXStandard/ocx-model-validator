"""Neutral report data model consumed by renderers.

Cells are plain scalars with units already resolved by the generators.
Renderers never see IR objects or Quantity values. ``None`` renders as N/A.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Cell = str | int | float | None


@dataclass(frozen=True)
class ReportTable:
    """A single table: column headers plus rows of pre-formatted cells."""
    title: str
    columns: list[str]
    rows: list[list[Cell]]
    footer_rows: list[list[Cell]] = field(default_factory=list)  # totals, styled bold


@dataclass(frozen=True)
class ReportSection:
    """A titled group of tables with optional intro text and notes."""
    title: str
    intro: str | None = None
    tables: list[ReportTable] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    """Root report object: title, metadata key/values, and sections."""
    title: str
    metadata: dict[str, str] = field(default_factory=dict)
    sections: list[ReportSection] = field(default_factory=list)
