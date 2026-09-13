"""Renderer protocol — all renderers turn a Report into a string."""
from __future__ import annotations

from typing import Protocol

from ocx_model_validator.reporting.model import Report


class ReportRenderer(Protocol):
    def render(self, report: Report) -> str:
        """Render the full report to a string."""
        ...
