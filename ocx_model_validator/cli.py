"""CLI entrypoint for ocx-model-validator.

Usage::

    validator report frame-table MODEL.3docx [--format rich|markdown] [--destination FILE]
    validator report compartments MODEL.3docx ...
    validator report catalogues MODEL.3docx [--catalogue material|section|opening|all] ...
    validator report bom MODEL.3docx [--detailed] ...
    validator report all MODEL.3docx ...
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
    folder_version = re.search(r"ocx_(\d)(\d)(\d+)_stubs", model.parent.name)
    if folder_version:
        return ".".join(folder_version.groups())
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
