"""Shared utilities for ocx_model_validator."""
from __future__ import annotations

from typing import Any, Dict, TypeVar

T = TypeVar("T")


class MetaData:
    """Helpers for reading xsdata dataclass Meta attributes."""

    @staticmethod
    def meta_class_fields(data_class: Any) -> Dict:
        """Return the dataclass Meta fields as a plain dict."""
        return dict(data_class.Meta.__dict__.items())

    @staticmethod
    def class_name(data_class: Any) -> str:
        """Return the simple class name (no module prefix)."""
        declaration = str(data_class.__class__)
        return declaration[declaration.rfind(".") + 1: -2]

    @staticmethod
    def namespace(data_class: Any) -> str:
        """Return the OCX XML namespace of the dataclass."""
        return MetaData.meta_class_fields(data_class).get("namespace")

    @staticmethod
    def name(data_class: Any) -> str:
        """Return the OCX element name of the dataclass."""
        return MetaData.meta_class_fields(data_class).get("name")
