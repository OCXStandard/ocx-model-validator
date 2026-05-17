"""CLI entrypoint for ocx-model-validator.

Usage::

    validator --generate          # generate missing stubs
    validator --generate --force  # delete existing stubs and regenerate all
"""
from __future__ import annotations

import typer

app = typer.Typer(
    name="validator",
    help="OCX model validator — tools for parsing and validating .3docx ship models.",
    no_args_is_help=True,
)


@app.command()
def main(
    generate: bool = typer.Option(
        False,
        "--generate",
        help="Generate XML test stubs from OCX models in ./models.",
        is_flag=True,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="When used with --generate, delete existing stubs and regenerate all.",
        is_flag=True,
    ),
) -> None:
    """OCX model validator CLI."""
    if generate:
        from ocx_model_validator.generate_stubs import main as generate_stubs
        generate_stubs(force=force)
    else:
        typer.echo("No action specified. Use --help for available options.")
        raise typer.Exit(code=0)


def entrypoint() -> None:
    app()
