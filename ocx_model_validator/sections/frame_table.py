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

    # Get the list of X ref plane ids. Try x_ref_plane_ids attribute first
    # (set by test helper), then fallback to all ref_plane ids.
    ids = getattr(vessel, "x_ref_plane_ids", None) or list(vessel.ref_planes.keys())

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

    # Emit entries at spacing changes
    entries: list[tuple[str, float]] = []
    prev_spacing = None
    for i in range(len(pos) - 1):
        spacing = pos[i + 1][1] - pos[i][1]
        if prev_spacing is None or abs(spacing - prev_spacing) > _SPACING_TOL_MM:
            entries.append((pos[i][0], spacing))
            prev_spacing = spacing

    # frame0_offset: look for label "0", else use lowest position
    by_label = dict(pos)
    frame0 = by_label.get("0", pos[0][1])

    return FrameTable(
        frame0_offset_mm=frame0,
        positions=pos,
        entries=entries,
        warnings=warnings,
    )
