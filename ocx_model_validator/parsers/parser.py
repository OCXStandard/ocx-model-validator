"""OCX Parser module."""
import re
from abc import ABC
from pathlib import Path
from typing import TypeVar

import lxml

# 3rd party imports
import lxml.etree
from loguru import logger
from xsdata.exceptions import ParserError
from xsdata.formats.dataclass.context import XmlContext, XmlContextError
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig
from xsdata.formats.dataclass.parsers.handlers import LxmlEventHandler

from ..exeptions import SourceError, XmlParserError
from .base_parser import IParser
from .dynamic_loader import DeclarationOfOcxImport, DynamicLoader

T = TypeVar("T")

class OcxVersion:
    """Find the schema version of an 3Docx XML model."""

    @staticmethod
    def get_version(model: Path) -> str:
        """
        The schema version of the model.
        Args:
            model: The source file path or uri

        Returns:
            The schema version of the 3Docx XML model.
        """
        try:
            version = "NA"
            content = model.read_text(encoding="utf-8").split()
            for item in content:
                if "schemaVersion" in item:
                    version = item[item.find("=") + 2: -1]
            return version
        except SourceError as e:
            raise SourceError(e) from e

class OcxParser(IParser, ABC):
    """OcxParser class for 3Docx XML files.

    Args:
        fail_on_unknown_properties: Don't bail out on unknown properties.
        fail_on_unknown_attributes: Don't bail out on unknown attributes
        fail_on_converter_warnings: bool = Convert warnings to exceptions

    """

    def __init__(
            self,
            fail_on_unknown_properties: bool = False,
            fail_on_unknown_attributes: bool = False,
            fail_on_converter_warnings: bool = False,
    ):
        self._context = XmlContext()
        self._parser_config = ParserConfig(
            fail_on_unknown_properties=fail_on_unknown_properties,
            fail_on_unknown_attributes=fail_on_unknown_attributes,
            fail_on_converter_warnings=fail_on_converter_warnings,
        )

    def parse(self, xml_file: str) -> T:
        """Parse a 3Docx XML model from file and return the root dataclass.
        The OCX schema version is retrieved from the OCX file and the correct OCX data bindings are dynamically loaded.

        Args:
            xml_file: The 3Docx xml file or url to parse.

        Returns:
            The root dataclass instance of the parsed 3Docx XML.
        """
        try:
            file_path = Path(xml_file)
            tree = lxml.etree.parse(xml_file)
            root = tree.getroot()
            version = OcxVersion.get_version(file_path)
            declaration = DeclarationOfOcxImport("ocx", version)
            # Load target schema version module
            ocx_module = DynamicLoader.import_module(declaration)
            ocx_parser = XmlParser(
                handler=LxmlEventHandler,
                config=self._parser_config,
                context=self._context,
            )
            return ocx_parser.parse(root, ocx_module.OcxXml)
        except lxml.etree.XMLSyntaxError as e:
            logger.error(e)
            raise XmlParserError(e) from e
        except ImportError as e:
            logger.error(e)
            raise XmlParserError from e
        except XmlContextError as e:
            logger.error(e)
            raise XmlParserError from e
        except ParserError as e:
            logger.error(e)
            raise XmlParserError from e


    def parse_from_string(self, xml_str: str, declaration: DeclarationOfOcxImport) -> T:
        """Parse a 3Docx XML model from a string and return the OCX dataclass.

        Args:
            xml_str: The OCX XML string to parse.

        Returns:
            The OCX dataclass instance of the parsed OCX XML string.
        """
        try:
            # Load target schema version module (side effect: registers bindings)
            DynamicLoader.import_module(declaration)
            ocx_parser = XmlParser(
                handler=LxmlEventHandler,
                config=self._parser_config,
                context=self._context,
            )
            # Import the class
            pattern = r'<ocx:(\w+)'
            match = re.search(pattern, xml_str)
            entity_name = match.group(1) if match else None
            if entity_name is not None:
                ocx_class = DynamicLoader.import_class(module_declaration=declaration, class_name=entity_name)
                return ocx_parser.from_string(xml_str, ocx_class)
            else:
                raise ValueError(f'The OCX XML is not a valid OCX model: {xml_str}')
        except lxml.etree.XMLSyntaxError as e:
            logger.error(e)
            raise XmlParserError(e) from e
        except ImportError as e:
            logger.error(e)
            raise XmlParserError from e
        except XmlContextError as e:
            logger.error(e)
            raise XmlParserError from e
        except ParserError as e:
            logger.error(e)
            raise XmlParserError from e
