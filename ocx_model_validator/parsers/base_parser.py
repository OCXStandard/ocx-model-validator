"""Interfaces module."""

# System imports
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

import packaging.version


class IModuleDeclaration(ABC):
    """Abstract module import declaration Interface"""

    @staticmethod
    @abstractmethod
    def get_declaration() -> str:
        """Abstract Method: Return the module declaration string."""
        pass


class IParser(ABC):
    """Abstract parser interface."""

    @abstractmethod
    def parse(self, model: str) -> T:
        """
        Abstract method for parsing a data model,

        Args:
            model: the data model source

        Returns:
            the root dataclass of the parsed data model.
        """
        pass

class ISerializer(ABC):
    """Abstract serializer interface"""

    def __init__(self, clazz: T):
        self.clazz = clazz

    @abstractmethod
    def serialize_xml(self, to_file: str) -> str:
        """Abstract XML serialize to file method"""
        pass

    @abstractmethod
    def serialize_json(self) -> str:
        """Abstract XML serialize to string method"""
        pass
