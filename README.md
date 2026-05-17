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
- CLI entrypoint `validator --generate [--force]` for auto-generating xsdata test stubs
- Duplicate-id and dangling-ref integrity checks built into the builder

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
# generate xsdata stubs from .3docx models in ./models/
validator --generate

# wipe and regenerate all stubs
validator --generate --force
```

---

## Running tests

```bash
uv run pytest
```

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
```

---

## License

[MIT](LICENSE) © 2026 ocastrup