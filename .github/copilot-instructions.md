# Copilot Instructions — ocx-model-validator

## Project layout

```
ocx-model-validator/           ← repo root (pyproject.toml here)
├── pyproject.toml
├── ocx_model_validator.md
├── ocx_model_validator/       ← Python package
│   ├── __init__.py             ← public API surface
│   ├── exeptions.py            ← exception hierarchy (note: intentional spelling)
│   ├── utils.py                ← MetaData helpers for xsdata dataclasses
│   ├── model/
│   │   ├── ir.py               ← all IR dataclasses (IrVessel, IrPanel, …)
│   │   └── units.py            ← UnitConverter, build_unit_registry
│   ├── parsers/
│   │   ├── base_parser.py      ← IParser, IModuleDeclaration interfaces
│   │   ├── dynamic_loader.py   ← DynamicLoader, DeclarationOfOcxImport
│   │   └── parser.py           ← OcxParser (detects version, delegates to DynamicLoader)
│   └── builders/
│       ├── base.py             ← IOcxBuilder ABC, UnsupportedSchemaVersionError
│       ├── factory.py          ← get_builder(version) — _BUILDER_REGISTRY dispatch
│       └── v3_builder.py       ← OcxV3Builder (handles all v3.x)
└── tests/
    ├── conftest.py             ← fixtures; discovers stub dirs matching ocx_\d+_stubs
    ├── stubs.py / object_stubs.py
    └── test_*.py
```

## Build, test, and lint

All commands are run from the repo root (where `pyproject.toml` lives).

```bash
# Install (including dev dependencies)
uv sync --dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_builders.py

# Run a single test by name
uv run pytest tests/test_builders.py::TestBuilderFactory::test_get_builder_310_returns_v3
```

## CLI

Two equivalent entrypoints are registered (`validator` and `ocx-validate`):

```bash
# Model reports (rich to stdout; markdown or html via --destination / --format)
validator report frame-table  model.3docx
validator report compartments model.3docx
validator report panels       model.3docx
validator report plates       model.3docx
validator report stiffeners   model.3docx
validator report all          model.3docx --destination report.md
validator report all          model.3docx --destination report.html

# Generate XML test stubs from .3docx models in ./models/
validator generate-stubs

# Wipe and regenerate all stubs
validator generate-stubs --force
```

The `models/` directory at the repo root is the source for stub generation. Place `.3docx` files there before running `validator generate-stubs`. Generated stubs land in `tests/data/ocx_{version}_stubs/` and `tests/data/unitsml_stubs/`.

## Architecture — the parse → build pipeline

```
.3docx file
    │
    ▼
OcxParser.parse(xml_file)
    │  1. Reads schemaVersion from XML text
    │  2. Builds DeclarationOfOcxImport("ocx", version)
    │  3. DynamicLoader.import_module() → loads versioned xsdata module
    │     e.g. version "3.1.0" → module path "ocx.ocx_310.ocx_310"
    │  4. xsdata XmlParser.parse(root, OcxXml) → raw OCX root dataclass
    │
    ▼
get_builder(root.schema_version)   ← looks up _BUILDER_REGISTRY[(major, minor)]
    │
    ▼
IOcxBuilder.build(root) → IrVessel   ← schema-neutral IR
```

**Key insight**: the versioned OCX Python data-bindings (`ocx` package) are loaded at runtime, not imported statically. `DeclarationOfOcxImport` encodes the naming convention: version `"3.1.0"` → package `ocx_310` → full path `ocx.ocx_310.ocx_310`.

## IR design conventions

- `IrVessel` is the single root. All structural parts (plates, stiffeners, brackets, materials, sections, compartments, pillars) are stored in **flat dicts keyed by `id`** for O(1) lookup.
- `IrPanel` holds *id references* to its children, not the child objects themselves.
- Every child carries a `ParentRef(kind=ParentKind.PANEL|VESSEL, ref=id)`.
- All IR dataclasses are **frozen** (`@dataclass(frozen=True)`).
- Every optional field defaults to `None` or `[]` — no field access ever raises `AttributeError`.
- Unit values on IR objects are raw **OCX unit id strings** (e.g. `"Umm"`, `"UNOvermm2"`). Use `UnitConverter` / `build_unit_registry` to resolve or convert to SI.

## Builder conventions

- All raw OCX attribute access in builders uses `getattr(obj, "field", None)` — never direct attribute access — so minor schema renames degrade gracefully.
- To support a new schema version family, add a new `IOcxBuilder` subclass and register it in `_BUILDER_REGISTRY` in `factory.py`.
- The `_MAJOR_FALLBACK` dict in `factory.py` handles unknown minor versions within a known major family.
- Section type detection in `OcxV3Builder` uses `_SECTION_TYPE_MAP` (substring matching on lowercased class names). More-specific keys must precede any key that is a substring of them.
- Geometry extraction uses `_pt`/`_vec` (unpack OCX `Point3D.coordinates`/`Vector3D.direction` lists into `IrPoint3D`/`IrVector3D`) and `_build_curve`/`_build_surface`, which dispatch on the lowercased OCX class name. The IR mirrors OCX field *semantics* but stays shallow — OCX wrapper elements (`SplitBy`, `TraceLine`, `MassProperties`, `XRefPlanes`, …) are flattened onto the parent IR object; deep sub-trees collapse to scalars/`Ref`s/id-lists/flat dicts.
- OCX 3.2.0 renamed/restructured several elements (`PhysicalProperties`→`MassProperties`, `Material`→`Steel`/`Aluminium`, `Origin`→`PointOnSurface` on `Plane3D`, `Occurrence` `str_*Ref` names, `UnboundedGridRef`/`UnboundedSurfaceRef`). The builder always reads the 3.2.0 name first and falls back to the 3.1.0 name; the IR follows 3.2.0 shapes (`IrMassProperties`, `IrMaterial.material_type`, `IrPlane3D.point_on_surface`).

## Test fixtures and stubs

- Test fixtures auto-discover stub directories matching `ocx_\d+_stubs` (digits only) under `tests/data/`. Directories with letters in the version portion (e.g. `ocx_320rc8_stubs`) are intentionally skipped by `conftest.py`.
- Stub directory naming: `ocx_{major}{minor}{patch}_stubs` — e.g. version `3.1.0` → `ocx_310_stubs`.
- Stub files: `<entity_lowercase>.3docx` for OCX entities; `<entity_lowercase>.xml` for UnitsML. No `xmlns` declarations needed — the loader injects the correct namespace.
- `conftest.py` provides `ocx_stub_version` (parametrized over all discovered versions), `stub_dir_310`, and `declaration_310`. The `_build_session(model_file)` helper in conftest parses and builds an IR in one call.
- When writing tests against raw OCX objects, use inline stub classes (see `test_builders.py`) rather than importing from the OCX package directly.

## Compatibility shim

`parsers/load_tools.py` is a legacy re-export shim. **Do not import from it in new code** — import directly from `parsers.parser`, `parsers.dynamic_loader`, or `utils` instead.

## Logging

All modules use `loguru` (`from loguru import logger`). No `print()` or stdlib `logging`.

## Exceptions

All custom exceptions are in `exeptions.py` (note: module name has a typo — do not rename):
- `XmlParserError(ValueError)` — xsdata/lxml parse failures
- `SourceError(ValueError)` — file/path issues
- `DynamicLoaderError(AttributeError)` — dynamic import failures
- `ConverterError(ValueError)` / `ConverterWarning(Warning)` — unit conversion
