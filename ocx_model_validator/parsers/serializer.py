"""Serializer module"""
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.serializers import JsonSerializer, XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from .base_parser import ISerializer, T
from .dynamic_loader import MetaData


class Serializer(ISerializer):
    """Serializer class"""


    def __init__(
            self,
            clazz: T,
            pretty_print: bool = True,
            pretty_print_indent: str = "  ",
            encoding: str = "utf-8",
    ):
        """
        Args:
            clazz: The dataclass to serialize.
            pretty_print: True to pretty print, False otherwise.
            pretty_print_indent: Pretty print indentation.
            encoding: The encoding code.
        Params:
            _model: The dataclass to serialize.
            _config: The serializer configuration.

        """
        self._clazz: T = clazz
        self._config = SerializerConfig(
            encoding=encoding,
            xml_version="1.0",
            xml_declaration=True,
            indent="    ",
            ignore_default_attributes=False,
            schema_location=None,
            no_namespace_schema_location=None,
            globalns=None,
        )

    def serialize_xml(self, global_ns: str = "ocx") -> str:
        """Serialize a 3Docx XML file with proper indentations.

        Returns:
              The dataclass xml serialisation as a string.

        Raises:
            SerializeError if failing
        """
        target_ns = MetaData.namespace(self._clazz)
        ns_map = {global_ns: target_ns}
        serializer = XmlSerializer(context=XmlContext(), config=self._config)
        return serializer.render(self._clazz, ns_map=ns_map)

    def serialize_json(self) -> str:
        """Serialize a 3Docx XML dataclass to JSON with proper indentations.

        Returns:
              The dataclass JSON serialisation.

        Raises:
            SerializeError if failing
        """
        serializer = JsonSerializer(context=XmlContext(), config=self._config)
        return serializer.render(self._clazz)


