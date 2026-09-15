"""CLI entrypoint for ocx-model-validator.

Usage::

    validator report frame-table MODEL.3docx [--format rich|markdown] [--destination FILE]
    validator report compartments MODEL.3docx ...
    validator report catalogues MODEL.3docx [--catalogue material|section|opening|all] ...
    validator report bom MODEL.3docx [--detailed] ...
    validator report all MODEL.3docx ...
    validator section create MODEL.3docx --frame FR20 -o section.json
    validator section export MODEL.3docx --frame FR20 [--rule-set DNV] -o section.hmx
    validator section plot section.json -o section.svg
    validator generate-stubs [--force]
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
import re
from types import SimpleNamespace

import typer
from loguru import logger
from rich.console import Console

from ocx_model_validator.reporting.model import Report
from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer

app = typer.Typer(
    name="validator",
    help="OCX model validator — tools for parsing, reporting and validating .3docx ship models.",
    no_args_is_help=True,
)
report_app = typer.Typer(help="Generate model reports.", no_args_is_help=True)
app.add_typer(report_app, name="report")
section_app = typer.Typer(help="Create, plot and export cross sections.",
                          no_args_is_help=True)
app.add_typer(section_app, name="section")


class ReportFormat(str, Enum):
    rich = "rich"
    markdown = "markdown"


_MODEL_ARG = typer.Argument(..., exists=True, readable=True,
                            help="Path to a .3docx model file.")
_FORMAT_OPT = typer.Option(None, "--format", "-f",
                           help="Output format (default: rich to stdout, "
                                "markdown with --destination).")
_DEST_OPT = typer.Option(None, "--destination", "-d",
                         help="Write the report to this file (Markdown).")


def _load_vessel(model: Path):
    """Parse and build the IR; exit code 1 on failure."""
    from ocx_model_validator.builders.factory import get_builder
    from ocx_model_validator.parsers.dynamic_loader import DeclarationOfOcxImport
    from ocx_model_validator.parsers.parser import OcxParser

    try:
        version = _detect_schema_version(model)
        parser = OcxParser()
        if version is None:
            root = parser.parse(str(model))
            version = root.schema_version
        else:
            logger.warning(
                "{} has no schemaVersion attribute and is being loaded as a "
                "bare fragment; units and catalogues will be unavailable.",
                model,
            )
            root = SimpleNamespace(
                vessel=parser.parse_from_string(
                    xml_str=model.read_text(encoding="utf-8"),
                    declaration=DeclarationOfOcxImport("ocx", version),
                ),
                schema_version=version,
            )
        builder = get_builder(version)
        return builder.build(root)
    except Exception as exc:
        logger.error("Failed to parse/build {}: {}", model, exc)
        raise typer.Exit(code=1) from exc


def _detect_schema_version(model: Path) -> str | None:
    xml = model.read_text(encoding="utf-8")
    schema_version = re.search(r'\bschemaVersion="([^"]+)"', xml)
    if schema_version:
        return None
    namespace_version = re.search(r"//V(\d)(\d)(\d)//OCX_Schema\.xsd", xml)
    if namespace_version:
        return ".".join(namespace_version.groups())
    return None


def _emit(report: Report, fmt: ReportFormat | None, destination: Path | None) -> None:
    if destination is not None:
        if fmt == ReportFormat.rich:
            raise typer.BadParameter(
                "--destination cannot be combined with --format rich")
        try:
            destination.write_text(get_renderer("markdown").render(report),
                                   encoding="utf-8")
        except OSError as exc:
            logger.error("Cannot write {}: {}", destination, exc)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Report written to {destination}")
        return
    if fmt is None or fmt == ReportFormat.rich:
        RichRenderer().render_to_console(report, Console())
    else:
        typer.echo(get_renderer("markdown").render(report), nl=False)


def _default_section_output(model: Path, frame: str | None,
                            x_mm: float | None, suffix: str = ".json") -> Path:
    tag = re.sub(r"[^\w.-]", "_", frame) if frame is not None else f"x{x_mm:g}"
    return Path(f"{model.stem}-{tag}{suffix}")


@section_app.command("create")
def section_create_cmd(
    model: Path = _MODEL_ARG,
    frame: str | None = typer.Option(None, "--frame",
                                     help="Frame label, e.g. FR20."),
    x_mm: float | None = typer.Option(None, "--x",
                                      help="Section x-position in mm."),
    output: Path | None = typer.Option(None, "--output", "-o",
                                       help="Output JSON file."),
) -> None:
    """Build a transverse cross-section and write the JSON document."""
    from ocx_model_validator.exeptions import GeometryError, SectionError
    from ocx_model_validator.sections.document import build_document, save_document

    if (frame is None) == (x_mm is None):
        raise typer.BadParameter("Provide exactly one of --frame or --x")
    vessel = _load_vessel(model)
    try:
        doc = build_document(vessel, str(model), x_mm=x_mm, frame=frame)
    except (GeometryError, SectionError) as exc:
        logger.error("Cannot build section for {}: {}", model, exc)
        raise typer.Exit(code=1) from exc
    out = output or _default_section_output(model, frame, x_mm)
    try:
        save_document(doc, out)
    except OSError as exc:
        logger.error("Cannot write {}: {}", out, exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Section written to {out}")


@section_app.command("export")
def section_export_cmd(
    model: Path = _MODEL_ARG,
    frame: str | None = typer.Option(None, "--frame",
                                     help="Frame label, e.g. FR20."),
    x_mm: float | None = typer.Option(None, "--x",
                                      help="Section x-position in mm."),
    rule_set: str = typer.Option("DNV", "--rule-set",
                                 help="Classification rule set: DNV, RV5 or CSR-H."),
    output: Path | None = typer.Option(None, "--output", "-o",
                                       help="Output Nauticus Hull XML (.hmx) file."),
) -> None:
    """Export a transverse cross-section as a Nauticus Hull XML (.hmx) document."""
    from ocx_model_validator.exeptions import GeometryError, SectionError
    from ocx_model_validator.sections.document import resolve_section
    from ocx_model_validator.sections.hmx_export import RULE_SETS, build_hmx, save_hmx

    if (frame is None) == (x_mm is None):
        raise typer.BadParameter("Provide exactly one of --frame or --x")
    if rule_set not in RULE_SETS:
        raise typer.BadParameter(
            f"Unsupported rule set {rule_set!r}; choose one of {', '.join(RULE_SETS)}")
    vessel = _load_vessel(model)
    try:
        frame_table, cross_section = resolve_section(vessel, x_mm=x_mm, frame=frame)
        root = build_hmx(vessel, cross_section, frame_table, rule_set=rule_set)
    except (GeometryError, SectionError, ValueError) as exc:
        logger.error("Cannot export HMX section for {}: {}", model, exc)
        raise typer.Exit(code=1) from exc
    out = output or _default_section_output(model, frame, x_mm, suffix=".hmx")
    try:
        save_hmx(root, out)
    except OSError as exc:
        logger.error("Cannot write {}: {}", out, exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"HMX section written to {out}")


@section_app.command("plot")
def section_plot_cmd(
    section: Path = typer.Argument(..., exists=True, readable=True,
                                   help="Cross-section JSON document."),
    output: Path | None = typer.Option(None, "--output", "-o",
                                       help="Output SVG file."),
) -> None:
    """Plot a cross-section JSON document as an SVG."""
    from ocx_model_validator.exeptions import SectionError
    from ocx_model_validator.sections.document import load_document
    from ocx_model_validator.sections.svg_plot import render_svg

    try:
        doc = load_document(section)
    except (SectionError, ValueError) as exc:
        logger.error("Cannot load {}: {}", section, exc)
        raise typer.Exit(code=1) from exc
    out = output or section.with_suffix(".svg")
    try:
        svg = render_svg(doc)
    except (KeyError, TypeError) as exc:
        logger.error("Invalid cross-section document {}: {}", section, exc)
        raise typer.Exit(code=1) from exc
    try:
        out.write_text(svg, encoding="utf-8")
    except OSError as exc:
        logger.error("Cannot write {}: {}", out, exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Plot written to {out}")


@report_app.command("frame-table")
def frame_table_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Frame table: frame 0 offset, spacing entries and frame positions."""
    from ocx_model_validator.reporting.generators import frame_table

    vessel = _load_vessel(model)
    _emit(frame_table.build(vessel, source_file=str(model)), fmt, destination)


class CatalogueKind(str, Enum):
    material = "material"
    section = "section"
    opening = "opening"
    all = "all"


@report_app.command("compartments")
def compartments_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Compartments: name, tank type, volume, COG and extents."""
    from ocx_model_validator.reporting.generators import compartments

    vessel = _load_vessel(model)
    _emit(compartments.build(vessel, source_file=str(model)), fmt, destination)


@report_app.command("catalogues")
def catalogues_cmd(
    model: Path = _MODEL_ARG,
    catalogue: CatalogueKind = typer.Option(
        CatalogueKind.all, "--catalogue",
        help="Which catalogue to report."),
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Catalogues: materials, cross sections and openings."""
    from ocx_model_validator.reporting.generators import catalogues

    vessel = _load_vessel(model)
    _emit(catalogues.build(vessel, which=catalogue.value,
                           source_file=str(model)), fmt, destination)


@report_app.command("bom")
def bom_cmd(
    model: Path = _MODEL_ARG,
    detailed: bool = typer.Option(
        False, "--detailed",
        help="Add per-item rows below the summary.", is_flag=True),
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """Bill of material grouped by material, with weights and totals."""
    from ocx_model_validator.reporting.generators import bom

    vessel = _load_vessel(model)
    _emit(bom.build(vessel, detailed=detailed, source_file=str(model)),
          fmt, destination)


@report_app.command("all")
def all_cmd(
    model: Path = _MODEL_ARG,
    fmt: ReportFormat | None = _FORMAT_OPT,
    destination: Path | None = _DEST_OPT,
) -> None:
    """All reports merged into one document (report defaults; no per-report flags)."""
    from ocx_model_validator.reporting.generators import (
        bom,
        catalogues,
        compartments,
        frame_table,
        model_extent,
    )

    vessel = _load_vessel(model)
    source = str(model)
    parts = [
        model_extent.build(vessel, source_file=source),
        frame_table.build(vessel, source_file=source),
        compartments.build(vessel, source_file=source),
        catalogues.build(vessel, source_file=source),
        bom.build(vessel, source_file=source),
    ]
    merged = Report(
        title="Model report",
        metadata=parts[0].metadata,
        sections=[s for p in parts for s in p.sections],
    )
    _emit(merged, fmt, destination)


@app.command("generate-stubs")
def generate_stubs_cmd(
    force: bool = typer.Option(
        False, "--force",
        help="Delete existing stubs and regenerate all.", is_flag=True),
) -> None:
    """Generate XML test stubs from OCX models in ./models."""
    from ocx_model_validator.generate_stubs import main as generate_stubs

    generate_stubs(force=force)


def entrypoint() -> None:
    app()
