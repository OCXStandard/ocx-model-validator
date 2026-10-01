"""Tests for parsers.parser — OcxParser, OcxVersion.

Exercises:
- OcxVersion.get_version() schema version extraction
- OcxParser.parse_from_string() with valid XML stubs
- OcxParser error handling for invalid XML
"""
from __future__ import annotations

import pytest

from ocx_model_validator.exeptions import XmlParserError
from ocx_model_validator.parsers.dynamic_loader import DeclarationOfOcxImport
from ocx_model_validator.parsers.parser import OcxParser, OcxVersion

# ---------------------------------------------------------------------------
# OcxVersion
# ---------------------------------------------------------------------------

class TestOcxVersion:

    def test_get_version_300(self, tmp_path):
        xml = (
            '<?xml version="1.0"?>'
            '<ocxXML schemaVersion="3.0.0" ></ocxXML>'
        )
        f = tmp_path / "model.3docx"
        f.write_text(xml, encoding="utf-8")
        assert OcxVersion.get_version(f) == "3.0.0"

    def test_get_version_310(self, tmp_path):
        xml = '<ocxXML schemaVersion="3.1.0" ></ocxXML>'
        f = tmp_path / "model.3docx"
        f.write_text(xml, encoding="utf-8")
        assert OcxVersion.get_version(f) == "3.1.0"

    def test_get_version_missing_returns_na(self, tmp_path):
        xml = '<ocxXML></ocxXML>'
        f = tmp_path / "model.3docx"
        f.write_text(xml, encoding="utf-8")
        assert OcxVersion.get_version(f) == "NA"


# ---------------------------------------------------------------------------
# OcxParser — initialization
# ---------------------------------------------------------------------------

class TestOcxParserInit:

    def test_defaults(self):
        p = OcxParser()
        assert p._parser_config.fail_on_unknown_properties is False
        assert p._parser_config.fail_on_unknown_attributes is False
        assert p._parser_config.fail_on_converter_warnings is False

    def test_custom_flags(self):
        p = OcxParser(
            fail_on_unknown_properties=True,
            fail_on_unknown_attributes=True,
        )
        assert p._parser_config.fail_on_unknown_properties is True
        assert p._parser_config.fail_on_unknown_attributes is True


# ---------------------------------------------------------------------------
# OcxParser — parse_from_string
# ---------------------------------------------------------------------------

class TestOcxParserFromString:

    def test_parse_material_stub(self, stub_dir_310, declaration_310):
        """parse_from_string correctly parses a Material XML snippet."""
        from tests.stubs import StubMaterial
        result = StubMaterial.load(stub_dir=stub_dir_310, declaration=declaration_310)
        assert result is not None
        assert hasattr(result, "id") or hasattr(result, "name")

    def test_parse_plate_stub(self, stub_dir_310, declaration_310):
        from tests.stubs import StubPlate
        result = StubPlate.load(stub_dir=stub_dir_310, declaration=declaration_310)
        assert result is not None

    def test_parse_panel_stub(self, stub_dir_310, declaration_310):
        from tests.stubs import StubPanel
        result = StubPanel.load(stub_dir=stub_dir_310, declaration=declaration_310)
        assert result is not None

    def test_parse_stiffener_stub(self, stub_dir_310, declaration_310):
        from tests.stubs import StubStiffener
        result = StubStiffener.load(stub_dir=stub_dir_310, declaration=declaration_310)
        assert result is not None

    def test_parse_bracket_stub(self, stub_dir_310, declaration_310):
        from tests.stubs import StubBracket
        result = StubBracket.load(stub_dir=stub_dir_310, declaration=declaration_310)
        assert result is not None

    def test_parse_no_ocx_element_raises(self):
        xml = "<NotOcx>content</NotOcx>"
        p = OcxParser()
        decl = DeclarationOfOcxImport("ocx", "3.1.0")
        with pytest.raises(ValueError, match="not a valid OCX model"):
            p.parse_from_string(xml, decl)

    def test_parse_invalid_xml_raises(self, tmp_path):
        bad = tmp_path / "bad.3docx"
        bad.write_text("<not valid xml", encoding="utf-8")
        p = OcxParser()
        with pytest.raises(XmlParserError):
            p.parse(str(bad))

    def test_parse_all_stub_versions(self, ocx_stub_version):
        """parse_from_string works for every stub version directory."""
        from tests.stubs import StubMaterial
        version, stub_dir, declaration = ocx_stub_version
        if not (stub_dir / StubMaterial.entity_file).exists():
            pytest.skip(f"{StubMaterial.entity_file} not available for OCX {version}")
        result = StubMaterial.load(stub_dir=stub_dir, declaration=declaration)
        assert result is not None
