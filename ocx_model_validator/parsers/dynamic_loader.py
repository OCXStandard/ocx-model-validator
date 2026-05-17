"""Dynamically load OCX dataclasses."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import re
import sys
from abc import ABC
from types import ModuleType
from typing import Any, Dict, List, TypeVar

from loguru import logger

from ocx_model_validator.exeptions import DynamicLoaderError  # noqa: F401 – re-exported
from ocx_model_validator.utils import MetaData  # noqa: F401 – re-exported
from .base_parser import IModuleDeclaration

T = TypeVar("T")


class ModuleDeclaration(IModuleDeclaration, ABC):
    """General module declaration

    Args:
        package:the package name
        sub_module: The submodule name
        name: The method name
    """

    def __init__(self, package: str, sub_module: str, name: str):
        self._module = sub_module
        self._package = package
        self._method = name

    def get_declaration(self) -> str:
        """Return the module import declaration."""
        return f"{self._package}.{self._module}.{self._method}"


class DeclarationOfOcxImport(IModuleDeclaration):
    """Declaration of the ocx module."""

    def __init__(self, name: str, version: str):
        self._name = name
        self._version = version

    def get_declaration(self) -> str:
        """Return the module import declaration."""
        ocx_pkg = f'{self._name}_{self._version.replace(".", "")}'
        return f"{self._name}.{ocx_pkg}.{ocx_pkg}"

    def get_version(self) -> str:
        """Return the OCX module version."""
        return self._version

    def get_name(self) -> str:
        """Return the declared module name."""
        return self._name

class DynamicLoader:
    """Dynamically loads modules, classes of functions from a module declaration."""

    @classmethod
    def _load(cls, declaration: str) -> Any:
        """Internal Method: Import the object from the declaration.

        Args:
            declaration: The module declaration string.
        Returns:
            Return the loaded object, None if failed.
        """
        obj_type = None
        if (spec := importlib.util.find_spec(declaration)) is not None:
            obj_type = importlib.util.module_from_spec(spec)
            sys.modules[declaration] = obj_type
            spec.loader.exec_module(obj_type)
            # logger.debug(f"Loaded object {declaration!r} from location {spec.origin!r}")
        else:
            logger.error(f"No object {declaration!r}")
        return obj_type

    @classmethod
    def import_module(cls, module_declaration: IModuleDeclaration) -> ModuleType:
        """

        Args:
            module_declaration: The declaration of the pyton module to load

        Returns:
            Return the loaded module, None if failed.
        """
        module_to_load = module_declaration.get_declaration()
        return cls._load(module_to_load)

    @classmethod
    def import_class(
            cls, module_declaration: IModuleDeclaration, class_name: str
    ) -> Any:
        """
        The module import declaration.
        Args:
            class_name: The class name to load form the declared module
            module_declaration: The declaration of the python module to be loaded

        Returns:
            Return the loaded class, None if failed.
        """
        module_to_load = module_declaration.get_declaration()
        module = cls._load(module_to_load)
        # Fast path: Python class name matches the XML element name directly.
        obj = getattr(module, class_name, None)
        if obj is not None:
            return obj
        # Fallback: scan module classes for one whose Meta.name equals class_name.
        # Handles capitalization differences like IBar → Ibar, TBar → Tbar.
        for _, klass in inspect.getmembers(module, inspect.isclass):
            if klass.__module__ != module.__name__:
                continue
            try:
                if klass.Meta.name == class_name:
                    return klass
            except AttributeError:
                pass
        raise DynamicLoaderError(
            f"No class with name {class_name!r} in module {module_to_load!r}"
        )

    @classmethod
    def get_all_class_names(cls, module_name: str, version: str) -> List:
        """Return all class names in the module by the ``__all__`` variable.

        Args:
            module_name: The module name
            version: The module version

        Returns:
            The list of available module class names.
        """
        all_names = []
        ocx_pkg = f'{module_name}_{version.replace(".", "")}'
        ocx_module = f"{module_name}.{ocx_pkg}"
        if (spec := importlib.util.find_spec(ocx_module)) is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[ocx_module] = module
            spec.loader.exec_module(module)
            logger.debug(f"Found module {ocx_module!r} in location {spec.origin}")
            all_names = module.__all__
        else:
            logger.error(f"No module with name {module_name!r} and version {version!r}")
        return all_names

