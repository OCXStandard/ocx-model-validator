"""Process-wide model state for the ocx-mcp server."""
from __future__ import annotations

from ocx_model_validator.model.ir.structural import IrVessel

vessel: IrVessel | None = None
source_file: str | None = None


def set_model(v: IrVessel, path: str) -> None:
    global vessel, source_file
    vessel, source_file = v, path


def reset() -> None:
    global vessel, source_file
    vessel = source_file = None
