#!/usr/bin/env python
"""Generate OCX and UnitsML XML stub files from 3DOCX models.

This script extracts entity XML snippets from OCX models stored
subdirectories under ``models`` and writes them to the corresponding stub
folders in tests/data/ocx_{version}_stubs.

**Workflow:**

1. Scans ``models/`` folders for model references.
2. For each model, parses the XML and extracts one XML snippet per unique entity type encountered.
3. Identify the 3Docx schema version from the source file and get the ocx and unitsml namespaces
4. Writes new OCX stubs to ``tests/data/ocx_{version}_stubs/<entity>.3docx``. Include the source file in a comment header.
   Add the namespace tag to the entity as shown below:

```
<!-- Source: TR03_TC11_nast.3docx -->
<ocx:BulbFlat "https://3docx.org/fileadmin//ocx_schema//V310//OCX_Schema.xsd">
          <ocx:Height numericvalue="0.2" unit="Um"/>
          <ocx:WebThickness numericvalue="0.01" unit="Um"/>
          <ocx:FlangeWidth numericvalue="0.03785" unit="Um"/>
        </ocx:BulbFlat>
```
5. Writes new UnitsML stubs to ``tests/data/unitsml_stubs/<entity>.xml`` following similar patteran as or ocx stubs.
6. Skips entities where a stub already exists.
7. Generates a report of missing stubs (entities in ``__all__`` without a stub).

**Usage**::

    uv run python /generate_stubs.py

**Output:**

- OCX stub files in ``tests/data/ocx_{version}_stubs/``
- UnitsML stub files in ``tests/data/unitsml_stubs/``
- Report printed to console showing generated/skipped/missing stubs.
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import lxml.etree as etree
from loguru import logger
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig
from xsdata.formats.dataclass.parsers.handlers import LxmlEventHandler

from ocx_model_validator.parsers.load_tools import (
    DeclarationOfOcxImport,
    DynamicLoader,
    MetaData,
    OcxVersion,
)
from ocx_model_validator.parsers.serializer import Serializer


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TESTS_DATA_DIR = Path(__file__).parent.parent / "tests" / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"
UNITSML_STUBS_DIR = TESTS_DATA_DIR / "unitsml_stubs"
STUBS_LOG_FILE = Path(__file__).parent.parent / "Stubs_Log.md"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StubGenerationReport:
    """Report of stub generation results for a single OCX version."""

    version: str
    generated: List[Tuple[str, str]] = field(default_factory=list)  # (entity, source_file)
    skipped: List[str] = field(default_factory=list)  # already existing
    missing: List[str] = field(default_factory=list)  # in __all__ but no stub
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (context, error_msg)

    def summary(self) -> str:
        """Generate a summary string for this version."""
        lines = [
            f"=== OCX {self.version} Stub Generation Report ===",
            f"Generated: {len(self.generated)} stubs",
            f"Skipped (already exist): {len(self.skipped)} stubs",
            f"Missing (no source found): {len(self.missing)} stubs",
            f"Errors: {len(self.errors)}",
        ]
        if self.generated:
            lines.append("\nGenerated stubs:")
            for entity, source in self.generated:
                lines.append(f"  - {entity}.3docx (from {source})")
        if self.skipped:
            lines.append(f"\nSkipped stubs: {', '.join(sorted(self.skipped)[:20])}")
            if len(self.skipped) > 20:
                lines.append(f"  ... and {len(self.skipped) - 20} more")
        if self.missing:
            lines.append(f"\nMissing stubs ({len(self.missing)} entities not found in models):")
            for entity in sorted(self.missing)[:30]:
                lines.append(f"  - {entity}")
            if len(self.missing) > 30:
                lines.append(f"  ... and {len(self.missing) - 30} more")
        if self.errors:
            lines.append("\nErrors:")
            for ctx, err in self.errors:
                lines.append(f"  - {ctx}: {err}")
        return "\n".join(lines)


@dataclass
class UnitsMLStubReport:
    """Report of UnitsML stub generation results."""

    generated: List[Tuple[str, str]] = field(default_factory=list)  # (entity, source_file)
    skipped: List[str] = field(default_factory=list)  # already existing
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (context, error_msg)

    def summary(self) -> str:
        """Generate a summary string for UnitsML stubs."""
        lines = [
            "=== UnitsML Stub Generation Report ===",
            f"Generated: {len(self.generated)} stubs",
            f"Skipped (already exist): {len(self.skipped)} stubs",
            f"Errors: {len(self.errors)}",
        ]
        if self.generated:
            lines.append("\nGenerated stubs:")
            for entity, source in self.generated:
                lines.append(f"  - {entity}.xml (from {source})")
        if self.skipped:
            lines.append(f"\nSkipped stubs: {', '.join(sorted(self.skipped)[:20])}")
            if len(self.skipped) > 20:
                lines.append(f"  ... and {len(self.skipped) - 20} more")
        if self.errors:
            lines.append("\nErrors:")
            for ctx, err in self.errors:
                lines.append(f"  - {ctx}: {err}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Namespace cache
# ---------------------------------------------------------------------------

_ns_cache: Dict[str, str] = {}

UNITSML_NS = "urn:oasis:names:tc:unitsml:schema:xsd:UnitsMLSchema_lite-0.9.18"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ocx_namespace(version: str) -> str:
    """Return the OCX XML namespace URI for *version*, cached after first call."""
    if version not in _ns_cache:
        declaration = DeclarationOfOcxImport("ocx", version)
        mod = DynamicLoader.import_module(declaration)
        _ns_cache[version] = mod.OcxXml.Meta.namespace
    return _ns_cache[version]


def _version_to_folder(version: str) -> str:
    """Convert a version string to a stub directory name.

    Example: ``"3.1.0"`` → ``"ocx_310_stubs"``
    """
    return f"ocx_{version.replace('.', '')}_stubs"


def _find_class_by_xml_name(module, xml_name: str):
    """Find an xsdata class in *module* whose XML element name matches *xml_name*.

    Tries fast path (Python class name == xml_name) first, then scans all
    module classes comparing ``MetaData.name(cls)`` for each.
    """
    cls = getattr(module, xml_name, None)
    if cls is not None:
        return cls
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        try:
            if MetaData.name(cls) == xml_name:
                return cls
        except Exception:
            pass
    return None


def _serialize_entity(
    element: etree._Element,
    declaration: DeclarationOfOcxImport,
    global_ns: str = "ocx",
) -> Optional[str]:
    """Serialize an lxml element to a self-contained XML string via Serializer.

    Steps:
    1. Serialize the lxml element to a string (namespace declarations included).
    2. Locate the matching xsdata class by XML element name using MetaData.
    3. Parse into a typed xsdata dataclass.
    4. Re-serialise via Serializer.serialize_xml() → clean XML with namespace.

    Args:
        element: The lxml element to serialize.
        declaration: OCX module declaration used to locate the xsdata class.
        global_ns: Namespace prefix for the output XML (``"ocx"`` or ``"unitsml"``).

    Returns ``None`` if any step fails (errors are logged as warnings).
    """
    local = etree.QName(element.tag).localname
    try:
        xml_str = etree.tostring(element, pretty_print=True, encoding="unicode")
        module = DynamicLoader.import_module(declaration)
        clazz = _find_class_by_xml_name(module, local)
        if clazz is None:
            logger.warning(f"No class found for XML element {local!r}")
            return None
        parser = XmlParser(
            handler=LxmlEventHandler,
            context=XmlContext(),
            config=ParserConfig(
                fail_on_unknown_properties=False,
                fail_on_unknown_attributes=False,
            ),
        )
        dataclass_instance = parser.from_string(xml_str, clazz)
        return Serializer(dataclass_instance).serialize_xml(global_ns=global_ns)
    except Exception as exc:
        logger.warning(f"Could not serialize {local!r}: {exc}")
        return None


def _write_stub(xml_str: str, path: Path, source_file: Path) -> bool:
    """Write *xml_str* to *path* with a source comment header.

    Inserts ``<!-- Source: <filename> -->`` immediately after the XML
    declaration (if present) so the file remains valid XML.

    Returns ``True`` if written, ``False`` if the file already exists.
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    comment = f"<!-- Source: {source_file.name} -->"
    if xml_str.lstrip().startswith("<?xml"):
        end = xml_str.index("?>") + 2
        xml_str = xml_str[:end] + "\n" + comment + xml_str[end:]
    else:
        xml_str = comment + "\n" + xml_str
    path.write_text(xml_str, encoding="utf-8")
    logger.debug(f"Wrote {path.name}")
    return True


# ---------------------------------------------------------------------------
# Model scanner
# ---------------------------------------------------------------------------

def scan_model(
    model_path: Path,
    ocx_ns: str,
) -> Tuple[Dict[str, etree._Element], Dict[str, etree._Element]]:
    """Parse *model_path* and return first-seen elements per entity type.

    Returns:
        ``(ocx_entities, unitsml_entities)`` — each is a ``{local_name: element}``
        dict of the first occurrence of each unique element type found in
        the respective namespace.
    """
    ocx_entities: Dict[str, etree._Element] = {}
    unitsml_entities: Dict[str, etree._Element] = {}
    try:
        tree = etree.parse(str(model_path))
        for element in tree.getroot().iter():
            tag = element.tag
            if not isinstance(tag, str):
                continue  # skip comments / processing instructions
            qname = etree.QName(tag)
            local, ns = qname.localname, qname.namespace
            if ns == ocx_ns and local not in ocx_entities:
                ocx_entities[local] = element
            elif ns == UNITSML_NS and local not in unitsml_entities:
                unitsml_entities[local] = element
    except Exception as exc:
        logger.error(f"Failed to parse {model_path.name}: {exc}")
    return ocx_entities, unitsml_entities


# ---------------------------------------------------------------------------
# Stub generators
# ---------------------------------------------------------------------------

def _is_abstract_type(name: str, module) -> bool:
    """Return ``True`` if *name* is an abstract XSD type, not a concrete XML element.

    Uses ``MetaData`` to detect two cases:
    - Abstract type bindings: ``Meta.name`` ends with ``"_T"`` (e.g. ``BracketT``
      has ``Meta.name = "Bracket_T"``).  These are XSD complexType definitions
      used only for inheritance — they never appear as standalone XML elements.
    - Enums / simple types: class has no ``Meta`` attribute at all.

    Both kinds have no stub file equivalent.
    """
    cls = getattr(module, name, None)
    if cls is None:
        return False
    try:
        meta_name = MetaData.name(cls)
    except AttributeError:
        return True  # No Meta → enum or simple type, not an XML element
    return meta_name is not None and meta_name.endswith("_T")

def generate_ocx_stubs(
    version: str, model_paths: List[Path]
) -> StubGenerationReport:
    """Generate OCX stub files for *version* from *model_paths*.

    Creates ``tests/data/ocx_{version}_stubs/`` and writes one
    ``<entity_lower>.3docx`` per unique entity type found.  Existing files
    are skipped.  The report includes a missing-stub list derived from the
    module's ``__all__``.
    """
    report = StubGenerationReport(version=version)
    stub_dir = TESTS_DATA_DIR / _version_to_folder(version)
    stub_dir.mkdir(parents=True, exist_ok=True)

    declaration = DeclarationOfOcxImport("ocx", version)
    try:
        ocx_ns = _get_ocx_namespace(version)
    except Exception as exc:
        report.errors.append(("namespace", str(exc)))
        return report

    # Collect first-seen entities across all models for this version
    all_entities: Dict[str, etree._Element] = {}
    entity_sources: Dict[str, Path] = {}
    for model_path in model_paths:
        ocx_entities, _ = scan_model(model_path, ocx_ns)
        for local, element in ocx_entities.items():
            if local not in all_entities:
                all_entities[local] = element
                entity_sources[local] = model_path

    # Write stubs
    for local, element in all_entities.items():
        stub_path = stub_dir / f"{local.lower()}.3docx"
        xml_str = _serialize_entity(element, declaration)
        if xml_str is None:
            report.errors.append((local, "serialization failed"))
            continue
        if _write_stub(xml_str, stub_path, entity_sources[local]):
            report.generated.append((local, entity_sources[local].name))
        else:
            report.skipped.append(local)

    # Missing report: concrete elements in __all__ that have no stub file
    module = DynamicLoader.import_module(declaration)
    all_names: List[str] = DynamicLoader.get_all_class_names("ocx", version)
    for name in all_names:
        if _is_abstract_type(name, module):
            continue
        if not (stub_dir / f"{name.lower()}.3docx").exists():
            report.missing.append(name)

    return report


def generate_unitsml_stubs(
    version: str, model_paths: List[Path]
) -> UnitsMLStubReport:
    """Generate UnitsML stub files from *model_paths*.

    Uses the same xsdata round-trip as OCX stubs: each UnitsML element is
    parsed into its typed xsdata dataclass (co-located in the OCX module) and
    re-serialised via ``Serializer.serialize_xml(global_ns="unitsml")`` so
    the stub is a self-contained XML document with a proper namespace
    declaration — no injection required on load.

    Writes stubs to ``tests/data/unitsml_stubs/``.
    """
    report = UnitsMLStubReport()
    UNITSML_STUBS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        declaration = DeclarationOfOcxImport("ocx", version)
        ocx_ns = _get_ocx_namespace(version)
    except Exception as exc:
        report.errors.append(("namespace", str(exc)))
        return report

    all_entities: Dict[str, etree._Element] = {}
    entity_sources: Dict[str, Path] = {}
    for model_path in model_paths:
        _, unitsml_entities = scan_model(model_path, ocx_ns)
        for local, element in unitsml_entities.items():
            if local not in all_entities:
                all_entities[local] = element
                entity_sources[local] = model_path

    for local, element in all_entities.items():
        stub_path = UNITSML_STUBS_DIR / f"{local.lower()}.xml"
        xml_str = _serialize_entity(element, declaration, global_ns="unitsml")
        if xml_str is None:
            report.errors.append((local, "serialization failed"))
            continue
        if _write_stub(xml_str, stub_path, entity_sources[local]):
            report.generated.append((local, entity_sources[local].name))
        else:
            report.skipped.append(local)

    return report


# ---------------------------------------------------------------------------
# Log writer
# ---------------------------------------------------------------------------

def _md_details(summary: str, body_lines: List[str], open: bool = False) -> str:
    """Render an HTML ``<details>`` / ``<summary>`` expandable block."""
    open_attr = " open" if open else ""
    inner = "\n".join(body_lines)
    return f"<details{open_attr}>\n<summary>{summary}</summary>\n\n{inner}\n\n</details>"


def write_log(
    reports: List[StubGenerationReport], unitsml_report: UnitsMLStubReport
) -> None:
    """Write a nicely-formatted Markdown stub generation log to ``STUBS_LOG_FILE``."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []

    # ── Title & timestamp ───────────────────────────────────────────────────
    lines += [
        "# 🗂️ Stub Generation Log",
        "",
        f"> **Generated:** {now}",
        "",
        "---",
        "",
    ]

    # ── Summary table ───────────────────────────────────────────────────────
    lines += [
        "## Summary",
        "",
        "| Schema | Generated | Skipped | Missing | Errors |",
        "|--------|----------:|--------:|--------:|-------:|",
    ]
    for r in reports:
        status = "✅" if r.errors == [] else "⚠️"
        lines.append(
            f"| {status} OCX {r.version} "
            f"| {len(r.generated)} "
            f"| {len(r.skipped)} "
            f"| {len(r.missing)} "
            f"| {len(r.errors)} |"
        )
    u = unitsml_report
    u_status = "✅" if not u.errors else "⚠️"
    lines.append(
        f"| {u_status} UnitsML "
        f"| {len(u.generated)} "
        f"| {len(u.skipped)} "
        f"| — "
        f"| {len(u.errors)} |"
    )
    lines += ["", "---", ""]

    # ── Per-version OCX sections ─────────────────────────────────────────────
    for r in reports:
        lines += [f"## OCX {r.version}", ""]

        # Generated stubs — expandable
        if r.generated:
            stub_rows = [
                f"| `{entity}.3docx` | `{source}` |"
                for entity, source in r.generated
            ]
            block = _md_details(
                f"📦 Generated stubs &nbsp;({len(r.generated)})",
                [
                    "| Stub file | Source model |",
                    "|-----------|-------------|",
                ] + stub_rows,
            )
            lines += [block, ""]

        # Errors
        if r.errors:
            lines += ["### ⚠️ Errors", ""]
            for ctx, err in r.errors:
                lines.append(f"- **`{ctx}`** — {err}")
            lines.append("")

        # Missing stubs — expandable
        if r.missing:
            missing_rows = [f"- `{m}`" for m in sorted(r.missing)]
            block = _md_details(
                f"❌ Missing stubs &nbsp;({len(r.missing)} entities not found in models)",
                missing_rows,
            )
            lines += [block, ""]

        # Skipped stubs — expandable (only if non-empty)
        if r.skipped:
            skipped_rows = [f"- `{s}.3docx`" for s in sorted(r.skipped)]
            block = _md_details(
                f"⏭️ Skipped stubs &nbsp;({len(r.skipped)} already exist)",
                skipped_rows,
            )
            lines += [block, ""]

        lines += ["---", ""]

    # ── UnitsML section ──────────────────────────────────────────────────────
    lines += ["## UnitsML", ""]

    if u.generated:
        stub_rows = [
            f"| `{entity}.xml` | `{source}` |"
            for entity, source in u.generated
        ]
        block = _md_details(
            f"📦 Generated stubs &nbsp;({len(u.generated)})",
            [
                "| Stub file | Source model |",
                "|-----------|-------------|",
            ] + stub_rows,
        )
        lines += [block, ""]

    if u.errors:
        lines += ["### ⚠️ Errors", ""]
        for ctx, err in u.errors:
            lines.append(f"- **`{ctx}`** — {err}")
        lines.append("")

    if u.skipped:
        skipped_rows = [f"- `{s}.xml`" for s in sorted(u.skipped)]
        block = _md_details(
            f"⏭️ Skipped stubs &nbsp;({len(u.skipped)} already exist)",
            skipped_rows,
        )
        lines += [block, ""]

    STUBS_LOG_FILE.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Log written to {STUBS_LOG_FILE}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(force: bool = False) -> None:
    """Discover models, generate stubs for every schema version found.

    Args:
        force: When ``True``, delete existing stubs before regenerating.
    """
    if not MODELS_DIR.exists():
        logger.error(f"Models directory not found: {MODELS_DIR}")
        return

    model_files = list(MODELS_DIR.rglob("*.3docx"))
    if not model_files:
        logger.warning(f"No .3docx models found under {MODELS_DIR}")
        return

    logger.info(f"Found {len(model_files)} model file(s) in {MODELS_DIR}")

    if force:
        for stub_dir in TESTS_DATA_DIR.glob("ocx_*_stubs"):
            if stub_dir.is_dir():
                logger.info(f"--force: removing {stub_dir}")
                import shutil
                shutil.rmtree(stub_dir)

    # Group models by schema version
    version_models: Dict[str, List[Path]] = {}
    for model_path in model_files:
        try:
            version = OcxVersion.get_version(model_path)
            if version == "NA":
                logger.warning(f"No schemaVersion in {model_path.name}; skipping")
                continue
            version_models.setdefault(version, []).append(model_path)
        except Exception as exc:
            logger.error(f"Could not read version from {model_path.name}: {exc}")

    if not version_models:
        logger.warning("No versioned models found.")
        return

    reports: List[StubGenerationReport] = []
    first_version: Optional[str] = None

    for version in sorted(version_models):
        paths = version_models[version]
        logger.info(f"OCX {version}: processing {len(paths)} model(s)")
        report = generate_ocx_stubs(version, paths)
        reports.append(report)
        print(report.summary())
        print()
        if first_version is None:
            first_version = version

    # UnitsML stubs — scan all models, use first version for namespace lookup
    if first_version is not None:
        unitsml_report = generate_unitsml_stubs(first_version, model_files)
        print(unitsml_report.summary())
    else:
        unitsml_report = UnitsMLStubReport()

    write_log(reports, unitsml_report)


if __name__ == "__main__":
    main()
