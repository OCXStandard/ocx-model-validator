"""Derive the Nauticus frame table from OCX X reference planes."""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.exeptions import SectionError
from ocx_model_validator.model.ir.structural import IrVessel
from ocx_model_validator.sections.units import qty_mm

_SPACING_TOL_MM = 1.0


def _label(name: str | None, pid: str) -> str:
    """Extract frame label from ref plane name or ID.

    If name starts with 'X' followed by parseable float, return the float part.
    Otherwise, return the name verbatim (or ID if name is None).
    """
    raw = (name or pid).strip()
    if raw[:1].upper() == "X":
        rest = raw[1:]
        try:
            float(rest)
            return rest
        except ValueError:
            pass
    return raw


def _x_ref_plane_ids(vessel: IrVessel) -> list[str]:
    """Return X ref plane ids from the vessel's coordinate systems."""
    coordinate_systems = list(vessel.coordinate_systems.values())
    global_coordinate_systems = [
        cs for cs in coordinate_systems if getattr(cs, "is_global", False)
    ]
    source_coordinate_systems = global_coordinate_systems or coordinate_systems

    ids: list[str] = []
    seen: set[str] = set()
    for coordinate_system in source_coordinate_systems:
        for pid in coordinate_system.x_ref_plane_ids:
            if pid not in seen:
                ids.append(pid)
                seen.add(pid)
    return ids


@dataclass(frozen=True)
class FrameRow:
    label: str
    name: str | None
    x_mm: float
    display_grid: bool | None


@dataclass(frozen=True)
class FrameTable:
    frame0_offset_mm: float
    positions: list[tuple[str, float]]      # (label, x_mm), sorted by x
    entries: list[tuple[str, float]]        # (label, spacing_mm) at spacing changes
    warnings: list[str] = field(default_factory=list)
    frames: list[FrameRow] = field(default_factory=list)  # full rows, sorted by x

    def frame_to_x(self, frame: str) -> float:
        """Return x location in mm for a frame label."""
        for label, x in self.positions:
            if label == frame:
                return x
        raise SectionError(f"Unknown frame label {frame!r}")

    def nearest_frame(self, x_mm: float) -> tuple[str, float]:
        """Return the frame position nearest to x_mm."""
        return min(self.positions, key=lambda lx: abs(lx[1] - x_mm))


def build_frame_table(vessel: IrVessel) -> FrameTable:
    """Build a frame table from vessel X reference planes.

    Args:
        vessel: The IR vessel object with ref_planes and unit_registry.

    Returns:
        A FrameTable with sorted positions and spacing entries.

    Raises:
        SectionError: If no X reference planes with locations are found.
    """
    warnings: list[str] = []
    rows: list[FrameRow] = []

    ids = _x_ref_plane_ids(vessel)

    for pid in ids:
        rp = vessel.ref_planes.get(pid)
        if rp is None:
            warnings.append(f"X ref plane id {pid!r} not found")
            continue
        x = qty_mm(rp.location, vessel.unit_registry)
        if x is None:
            warnings.append(f"Ref plane {rp.name or pid!r} has no location; skipped")
            continue
        rows.append(FrameRow(
            label=_label(rp.name, pid),
            name=rp.name,
            x_mm=x,
            display_grid=getattr(rp, "display_grid", None),
        ))

    if not rows:
        raise SectionError("Model has no X reference planes with locations")

    # Sort by X position
    rows.sort(key=lambda r: r.x_mm)

    # Remove near-coincident planes (< 1mm apart) and track duplicates
    filtered_rows: list[FrameRow] = []
    seen_labels: dict[str, int] = {}  # label -> count

    for row in rows:
        # Check if this position is too close to the previous one
        if filtered_rows and row.x_mm - filtered_rows[-1].x_mm < _SPACING_TOL_MM:
            warnings.append(f"Planes {filtered_rows[-1].label!r} (x={filtered_rows[-1].x_mm}) and {row.label!r} (x={row.x_mm}) are < 1mm apart; dropping {row.label!r}")
            continue

        filtered_rows.append(row)
        seen_labels[row.label] = seen_labels.get(row.label, 0) + 1

    # Warn about duplicate labels
    for label, count in seen_labels.items():
        if count > 1:
            warnings.append(f"Frame label {label!r} appears {count} times at different positions")

    rows = filtered_rows

    # Emit entries at spacing changes — only planes with displayGrid=True
    # participate in the frame grid (missing attribute counts as grid).
    grid = [r for r in rows if r.display_grid is not False]
    entries: list[tuple[str, float]] = []
    prev_spacing = None
    for i in range(len(grid) - 1):
        spacing = grid[i + 1].x_mm - grid[i].x_mm
        if prev_spacing is None or abs(spacing - prev_spacing) > _SPACING_TOL_MM:
            entries.append((grid[i].label, spacing))
            prev_spacing = spacing

    # frame0_offset: find frame 0 by numeric match (label parses to 0.0), else lowest x
    frame0_x = rows[0].x_mm
    for row in rows:
        try:
            if float(row.label) == 0.0:
                frame0_x = row.x_mm
                break
        except ValueError:
            pass

    return FrameTable(
        frame0_offset_mm=frame0_x,
        positions=[(r.label, r.x_mm) for r in rows],
        entries=entries,
        warnings=warnings,
        frames=rows,
    )
