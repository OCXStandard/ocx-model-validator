"""Builder factory — maps a schema version string to the correct IOcxBuilder."""
from __future__ import annotations

from loguru import logger

from .base import IOcxBuilder, UnsupportedSchemaVersionError
from .v3_builder import OcxV3Builder

# Registry: (major, minor) → builder class.
# Add entries here as new schema families are supported.
_BUILDER_REGISTRY: dict[tuple[int, int], type[IOcxBuilder]] = {
    (3, 0): OcxV3Builder,
    (3, 1): OcxV3Builder,
    (3, 2): OcxV3Builder,
}

# Fallback: major-only registry for unknown minor versions within a known family.
_MAJOR_FALLBACK: dict[int, type[IOcxBuilder]] = {
    3: OcxV3Builder,
}


def get_builder(schema_version: str) -> IOcxBuilder:
    """Return an ``IOcxBuilder`` instance for the given schema version string.

    Args:
        schema_version: Version string such as ``"3.0.0"`` or ``"3.1.0"``.

    Returns:
        A ready-to-use builder instance.

    Raises:
        UnsupportedSchemaVersionError: If no builder exists for the version.
    """
    try:
        parts = [int(p) for p in schema_version.split(".") if p.isdigit()]
        major = parts[0] if parts else -1
        minor = parts[1] if len(parts) > 1 else 0
    except (ValueError, IndexError):
        major, minor = -1, 0

    cls = _BUILDER_REGISTRY.get((major, minor)) or _MAJOR_FALLBACK.get(major)

    if cls is None:
        raise UnsupportedSchemaVersionError(
            f"No builder registered for OCX schema version {schema_version!r}. "
            f"Registered versions: {sorted(_BUILDER_REGISTRY.keys())}"
        )

    logger.debug(
        f"Schema version {schema_version!r} → {cls.__name__}"
    )
    return cls()

