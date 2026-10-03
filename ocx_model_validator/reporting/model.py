"""Neutral report data model consumed by renderers.

Cells are plain scalars with units already resolved by the generators.
Renderers never see IR objects or Quantity values. ``None`` renders as N/A.
``Link`` cells are internal cross-references: ``target`` names a row anchor
(see ``ReportTable.row_anchors``); renderers that cannot link render the text.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Link:
    """Internal cross-reference: display text plus a target anchor id (no '#')."""

    text: str
    target: str


Cell = str | int | float | Link | None


@dataclass(frozen=True)
class ReportTable:
    """A single table: column headers plus rows of pre-formatted cells."""

    title: str
    columns: list[str]
    rows: list[list[Cell]]
    footer_rows: list[list[Cell]] = field(default_factory=list)  # totals, styled bold
    # Optional anchor id per row (parallel to ``rows``); shorter list = no
    # anchor for the remaining rows. Empty (default) = no anchors.
    row_anchors: list[str | None] = field(default_factory=list)


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
