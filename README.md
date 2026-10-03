# OCX Model Validator

[![Python](https://img.shields.io/badge/python-%3E%3D3.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python library for parsing and validating [OCX](https://3docx.org/) `.3docx` ship-model files.
It translates versioned OCX xsdata dataclasses into a **schema-neutral Intermediate Representation (IR)**,
making downstream tools independent of any particular OCX schema version.

---

## Features

- Parses `.3docx` XML files using [xsdata](https://xsdata.readthedocs.io/) with dynamic schema-version detection
- Builds a typed, frozen IR (`IrVessel`, `IrPanel`, `IrPlate`, `IrBracket`, `IrStiffener`, …)
- Supports OCX schema **3.0 / 3.1 / 3.2** out of the box
- Converts UnitsML unit definitions to SI factors via `build_unit_registry`
- CLI subcommands for model reports and `validator generate-stubs [--force]` for auto-generating xsdata test stubs
- Duplicate-id and dangling-ref integrity checks built into the builder
- **Frame table extraction** (`ocx_model_validator.frame_table`): derives frame
  labels, positions and spacings (mm) from the model's X reference planes
- **Model reports** (`validator report …`): frame table, compartments,
  catalogues and bill of materials, rendered rich to stdout or as Markdown
- **MCP server** `ocx-mcp` exposing model loading, info, frame table,
  compartments and scantling write-back to LLM clients

---

## Installation

```bash
# requires Python ≥ 3.12 and uv
uv sync
```

Install with development dependencies:

```bash
uv sync --dev
```

---

## Quick start

```python
from ocx_model_validator.parsers.parser import OcxParser
from ocx_model_validator.builders.factory import get_builder

parser = OcxParser()
root   = parser.parse("path/to/model.3docx")

builder = get_builder(root.schema_version)   # dispatches on "3.1.0" etc.
ir      = builder.build(root)                # → IrVessel

print(ir.name, len(ir.panels), "panels")
for plate in ir.plates.values():
    print(plate.id, plate.thickness)
```

### Frame table extraction

```python
from ocx_model_validator.frame_table import build_frame_table

frame_table = build_frame_table(ir)
print(len(frame_table.positions), "frame positions,",
      len(frame_table.entries), "spacing entries")

label, x_mm = frame_table.nearest_frame(161_000.0)   # e.g. midship
```

### MCP server

Run the `ocx-mcp` server over stdio:

```bash
uv run ocx-mcp
```

MCP client configuration (e.g. `mcp.json`):

```json
{
  "mcpServers": {
    "ocx": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\PythonDev\\ocx-model-validator", "ocx-mcp"]
    }
  }
}
```

| Tool | Purpose |
|---|---|
| `load_model` | Parse a `.3docx` file and build the IR (kept in session state) |
| `get_model_info` | Vessel name, schema version and entity counts |
| `get_frame_table` | Frame 0 offset, spacing entries and frame positions (mm) |
| `get_compartments` | Compartment names, tank types, COGs, volumes and extents |
| `apply_scantlings` | Apply an `nh-optimisation/1` report to a `.3docx`: plate thicknesses plus stiffener `BarSection`s, written to a new file |

---

## Project structure

```
ocx-model-validator/
├── pyproject.toml
├── ocx_model_validator/
│   ├── __init__.py
│   ├── cli.py                  ← validator CLI entrypoint
│   ├── generate_stubs.py       ← xsdata stub generator
│   ├── exeptions.py            ← custom exception hierarchy
│   ├── utils.py                ← MetaData helpers
│   ├── frame_table.py          ← FrameTable, build_frame_table
│   ├── writeback.py            ← apply scantling reports to .3docx files
│   ├── model/
│   │   ├── ir/                 ← IR dataclasses (base, structural, sections, …)
│   │   └── units.py            ← UnitConverter, build_unit_registry, SI helpers
│   ├── reporting/
│   │   ├── model.py            ← Report, ReportSection, ReportTable
│   │   ├── generators/         ← frame table, compartments, catalogues, BOM
│   │   └── renderers/          ← rich and markdown renderers
│   ├── mcp/
│   │   ├── state.py            ← session state (loaded vessel)
│   │   └── server.py           ← FastMCP "ocx-mcp" server (5 tools)
│   ├── parsers/
│   │   ├── base_parser.py
│   │   ├── dynamic_loader.py   ← runtime xsdata module loader
│   │   └── parser.py           ← OcxParser (version detection)
│   └── builders/
│       ├── base.py             ← IOcxBuilder ABC
│       ├── factory.py          ← get_builder() registry
│       └── v3_builder.py       ← OcxV3Builder (v3.0 – v3.2)
└── tests/
    ├── conftest.py
    ├── stubs.py                ← stub loaders for each OCX entity
    ├── object_stubs.py         ← duck-typed helpers for unit tests
    ├── data/
    │   ├── ocx_310_stubs/      ← generated XML stubs for 3.1.0
    │   ├── ocx_320rc8_stubs/   ← generated XML stubs for 3.2.0rc8
    │   └── unitsml_stubs/      ← generated UnitsML stubs
    └── test_*.py
```

---

## CLI

```bash
# model reports (rich to stdout, or markdown to a file)
validator report frame-table  model.3docx
validator report compartments model.3docx
validator report catalogues   model.3docx --catalogue material
validator report bom          model.3docx
validator report panels       model.3docx
validator report plates       model.3docx
validator report stiffeners   model.3docx
validator report all          model.3docx --destination report.md

# generate xsdata stubs from .3docx models in ./models/
validator generate-stubs

# wipe and regenerate all stubs
validator generate-stubs --force
```

---

## Running tests

```bash
uv run pytest                  # unit tests (integration deselected by default)
uv run pytest -m integration   # end-to-end against a real .3docx model (slow)
```

The integration suite parses a full VLCC model and verifies frame table,
midship cross-section and document extraction against known values.

---

## Architecture

```
.3docx file
    │
    ▼
OcxParser.parse(xml_file)
    │  detects schemaVersion → loads versioned xsdata module at runtime
    │  → raw OCX root dataclass
    ▼
get_builder(schema_version)
    │  dispatches on (major, minor) → OcxV3Builder
    ▼
IOcxBuilder.build(root) → IrVessel   ← schema-neutral IR
    │
    ▼
frame_table.build_frame_table(vessel) → FrameTable      (X ref planes → frames)
reporting.generators → Report                           (frame table, compartments,
    │                                                    catalogues, BOM)
    ▼
validator CLI / ocx-mcp MCP server
```

---

## License

[MIT](LICENSE) © 2026 ocastrup