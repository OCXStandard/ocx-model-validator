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
- **Cross-section extraction** (`ocx_model_validator.sections`): builds a Nauticus-style
  frame table from the model's X reference planes, intersects the 3D model at any
  longitudinal position (analytic lines/circles/arcs + de Boor NURBS evaluation with
  tangency refinement), and assembles stiffener/plate/compartment data into a
  JSON document (schema `nh-cross-section/2`)
- **MCP server** `ocx-mcp` exposing the parse → frame table → cross-section → JSON
  pipeline to LLM clients

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

### Cross-section extraction

```python
from ocx_model_validator.sections import build_frame_table, build_document, save_document

frame_table = build_frame_table(ir)
print(len(frame_table.positions), "frame positions,",
      len(frame_table.entries), "spacing entries")

label, x_mm = frame_table.nearest_frame(161_000.0)   # e.g. midship
doc = build_document(ir, source_file="model.3docx", x_mm=x_mm)

section = doc["cross_section"]
print(len(section["stiffeners"]), "stiffeners,", len(section["plates"]), "plates")
save_document(doc, "midship.json")
```

The document (schema `nh-cross-section/2`) contains four blocks — `frame_table`,
`cross_section`, `compartments` and `warnings` — with all coordinates in **mm**,
volumes in **m³** and yield stress in **MPa**, matching the input conventions of
the DNV Nauticus Hull `RulesAPI` (see the companion
[`nh-mcp`](../nh-mcp/) project).
The `cross_section.plates` entries are elementary plate panels (EPPs), split at
longitudinal stiffeners, with `_EPP{n}` name suffixes plus `bound_lower`,
`bound_upper` and `breadth_mm` fields.

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
| `build_cross_section` | Full `nh-cross-section/2` document at a frame label or x position |
| `save_cross_section` | Build the document and persist it to a JSON file |
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
│   ├── model/
│   │   ├── ir.py               ← all IR dataclasses
│   │   └── units.py            ← UnitConverter, build_unit_registry
│   ├── sections/
│   │   ├── units.py            ← quantity → mm/MPa conversion helpers
│   │   ├── geometry.py         ← curve/plane intersection engine
│   │   ├── frame_table.py      ← FrameTable, build_frame_table
│   │   ├── section_builder.py  ← CrossSection, build_cross_section
│   │   ├── segment_math.py     ← per-segment arc/chord geometry helpers
│   │   ├── epp.py              ← EppPlate, split_plates_to_epps (EPP splitting)
│   │   └── document.py         ← nh-cross-section/2 JSON document
│   ├── mcp/
│   │   ├── state.py            ← session state (loaded vessel)
│   │   └── server.py           ← FastMCP "ocx-mcp" server (7 tools)
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
validator report bom          model.3docx --detailed
validator report all          model.3docx --destination report.md

# cross sections: JSON document at a frame or x-position, then SVG plot
# (--frame / --x are repeatable: one output file per position)
validator section create model.3docx --frame FR20 -o section.json
validator section create model.3docx --x 50000 --x 60000
# attach hull-girder section properties from a JSON input file (see below)
validator section create model.3docx --x 90000 --section-props props.json
validator section plot section.json -o section.svg

# export cross sections as Nauticus Hull XML (2DLX default, or HMX)
validator section export model.3docx --frame FR20 -o section.2dlx
validator section export model.3docx --frame FR20 --frame FR30
validator section export model.3docx --x 50000 --format hmx --rule-set CSR-H

# generate xsdata stubs from .3docx models in ./models/
validator generate-stubs

# wipe and regenerate all stubs
validator generate-stubs --force
```

### Section properties JSON input (`--section-props`)

`validator section create` accepts a JSON file with hull-girder section
properties per longitudinal position (see `section_props_sample.json`):

```json
[
  {
    "x_pos": 165800.0,
    "z_n": 14.2659,
    "iy_n50": 1516.878,
    "iz_n50": 4446.297
  }
]
```

| Key | Unit | Description |
| --- | --- | --- |
| `x_pos` | mm | Longitudinal position the entry applies to (required). |
| `z_n` | m | Height of the hull girder's neutral axis above the baseline. |
| `iy_n50` | m⁴ | Hull-girder moment of inertia (net, half corrosion deducted) about the horizontal axis. |
| `iz_n50` | m⁴ | Hull-girder moment of inertia (net) about the vertical axis. |

The entry whose `x_pos` lies within 1 mm of the section position is merged
into the `cross_section.sect_props` block of the output document. If no entry
matches — or `--section-props` is omitted — a warning is recorded in the
document's `warnings` list.

Three further properties are derived from the OCX model (all in m) and must
**not** appear in the input file:

- `bx` — local breadth from the y-extent of the section plates (doubled for
  half-breadth models);
- `z_deck_corner` — height of the strength-deck edge (outboard-most
  deck-plate endpoint);
- `ibh` — height of the inner bottom, from inner-bottom/double-bottom typed
  plates, falling back to the second plate intersection with the vertical
  line y = 50 mm (the first being the bottom shell). Underivable values are
  `null` with a warning.

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
sections.build_frame_table(vessel) → FrameTable        (X ref planes → frames)
sections.build_cross_section(vessel, x_mm) → CrossSection   (plane intersection)
sections.build_document(vessel, ...) → dict            (nh-cross-section/2 JSON)
    │
    ▼
ocx-mcp MCP server / DNV Nauticus Hull rule checks (nh-mcp)
```

---

## License

[MIT](LICENSE) © 2026 ocastrup