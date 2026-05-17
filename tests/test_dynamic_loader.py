"""Tests for parsers.dynamic_loader — DynamicLoader, DeclarationOfOcxImport."""
from __future__ import annotations

import pytest

from ocx_model_validator.parsers.dynamic_loader import (
    DeclarationOfOcxImport,
    DynamicLoader,
)
from ocx_model_validator.exeptions import DynamicLoaderError
from ocx_model_validator.utils import MetaData


class TestDeclarationOfOcxImport:

    def test_declaration_300(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        assert decl.get_declaration() == "ocx.ocx_300.ocx_300"

    def test_declaration_310(self):
        decl = DeclarationOfOcxImport("ocx", "3.1.0")
        assert decl.get_declaration() == "ocx.ocx_310.ocx_310"

    def test_get_version(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        assert decl.get_version() == "3.0.0"

    def test_get_name(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        assert decl.get_name() == "ocx"


class TestDynamicLoader:

    def test_import_module_for_ocx_300(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        module = DynamicLoader.import_module(decl)
        assert module is not None
        assert hasattr(module, "OcxXml")

    def test_import_module_for_ocx_310(self):
        decl = DeclarationOfOcxImport("ocx", "3.1.0")
        module = DynamicLoader.import_module(decl)
        assert module is not None
        assert hasattr(module, "OcxXml")

    def test_import_class_ocx_xml(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        cls = DynamicLoader.import_class(decl, "OcxXml")
        assert cls is not None
        assert cls.__name__ == "OcxXml"

    def test_import_class_not_found_raises(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        with pytest.raises(DynamicLoaderError, match="No class with name"):
            DynamicLoader.import_class(decl, "NonExistentClass")

    def test_get_all_class_names_300(self):
        names = DynamicLoader.get_all_class_names("ocx", "3.0.0")
        assert isinstance(names, list)
        assert len(names) > 0
        assert "OcxXml" in names

    def test_get_all_class_names_invalid_version(self):
        names = DynamicLoader.get_all_class_names("ocx", "99.0.0")
        assert names == []


class TestMetaData:

    def test_class_name(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        vessel_class = DynamicLoader.import_class(decl, "Vessel")
        instance = vessel_class()
        assert MetaData.class_name(instance) == "Vessel"

    def test_namespace_present(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        vessel_class = DynamicLoader.import_class(decl, "Vessel")
        instance = vessel_class()
        ns = MetaData.namespace(instance)
        assert ns is not None
        assert "3docx.org" in ns

    def test_meta_class_fields_is_dict(self):
        decl = DeclarationOfOcxImport("ocx", "3.0.0")
        vessel_class = DynamicLoader.import_class(decl, "Vessel")
        instance = vessel_class()
        fields = MetaData.meta_class_fields(instance)
        assert isinstance(fields, dict)
        assert "namespace" in fields
