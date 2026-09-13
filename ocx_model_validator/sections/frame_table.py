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
class FrameTable:
    frame0_offset_mm: float
    positions: list[tuple[str, float]]      # (label, x_mm), sorted by x
    entries: list[tuple[str, float]]        # (label, spacing_mm) at spacing changes
    warnings: list[str] = field(default_factory=list)

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
    pos: list[tuple[str, float]] = []

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
        pos.append((_label(rp.name, pid), x))

    if not pos:
        raise SectionError("Model has no X reference planes with locations")

    # Sort by X position
    pos.sort(key=lambda lx: lx[1])

    # Remove near-coincident planes (< 1mm apart) and track duplicates
    filtered_pos: list[tuple[str, float]] = []
    seen_labels: dict[str, int] = {}  # label -> count
    
    for label, x in pos:
        # Check if this position is too close to the previous one
        if filtered_pos and x - filtered_pos[-1][1] < _SPACING_TOL_MM:
            warnings.append(f"Planes {filtered_pos[-1][0]!r} (x={filtered_pos[-1][1]}) and {label!r} (x={x}) are < 1mm apart; dropping {label!r}")
            continue
        
        filtered_pos.append((label, x))
        seen_labels[label] = seen_labels.get(label, 0) + 1
    
    # Warn about duplicate labels
    for label, count in seen_labels.items():
        if count > 1:
            warnings.append(f"Frame label {label!r} appears {count} times at different positions")
    
    pos = filtered_pos

    # Emit entries at spacing changes
    entries: list[tuple[str, float]] = []
    prev_spacing = None
    for i in range(len(pos) - 1):
        spacing = pos[i + 1][1] - pos[i][1]
        if prev_spacing is None or abs(spacing - prev_spacing) > _SPACING_TOL_MM:
            entries.append((pos[i][0], spacing))
            prev_spacing = spacing

    # frame0_offset: find frame 0 by numeric match (label parses to 0.0), else lowest x
    frame0_x = pos[0][1]
    for label, x in pos:
        try:
            if float(label) == 0.0:
                frame0_x = x
                break
        except ValueError:
            pass

    return FrameTable(
        frame0_offset_mm=frame0_x,
        positions=pos,
        entries=entries,
        warnings=warnings,
    )
