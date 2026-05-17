"""Abstract base for OCX IR builders."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ocx_model_validator.model.ir import IrVessel
from ocx_model_validator.utils import MetaData  # noqa: F401 – re-exported for back-compat


class UnsupportedSchemaVersionError(Exception):
    """Raised when no builder is registered for the given schema version."""


class IOcxBuilder(ABC):
    """Translate a parsed OCX root dataclass into a schema-neutral ``IrVessel``.

    Implement one concrete subclass per OCX schema version family (e.g. v3.x).
    """

    @abstractmethod
    def build(self, root) -> IrVessel:
        """Build and return a fully-populated ``IrVessel`` from the raw root."""

    @abstractmethod
    def supported_versions(self) -> list[tuple[int, int]]:
        """Return the (major, minor) version tuples this builder handles."""

