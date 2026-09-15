# 2DLX Cross-Section Export — Design

**Date:** 2026-09-15
**Status:** Approved

## Problem

The HMX (`HullModel_HMX.xsd`) export is not backward compatible with older
Nauticus Hull installations. Nauticus Hull can import a standalone
cross-section in the older 2DLX format (`CrossSection_2DLX.xsd`, root element
`CROSS_SECTION`). We add a 2DLX export option alongside the existing HMX
export.

## Key insight

The 2DLX `CROSS_SECTION` body is structurally the same as the HMX `Scantling`
element the exporter already builds (`IDDATA`, `POSITION`, `MATERIAL`, `MISC`,
`PANEL`/`SHAPE`/`SEGMENT`/`PLATES`/`LONGS`/`CUTOUTS`/`TRVSTIFFS`). Both
schemas share `Base.xsd` types. The deltas are:

| Aspect | HMX (`Scantling`) | 2DLX (`CROSS_SECTION`) |
|---|---|---|
| Root | embedded in `HullModel/CrossSections` | standalone document root |
| `administrative` block | n/a | optional; we emit it |
| `SEGMENT` compartment refs | `LeftCompartment`/`RightCompartment` | omitted (XSD: "only used in HMX files") |
| `MaterialId` on `PLATE`/`LSTIFF` | references ShipData material table | omitted (no material catalogue exists) |
| Rule set | `ShipData` (`DNV`/`RV5`/`CSR-H`) | n/a |
| `ShipData`, `FrameTable`, `Compartments` | present | n/a |

## Architecture (chosen approach: shared body builders)

`ocx_model_validator/sections/hmx_export.py` keeps all body builders and is
parameterized so both formats reuse them. HMX output is unchanged.

- `_append_panel` / `_append_shape`: accept `comp_boxes: dict | None`. When
  `None`, no `LeftCompartment`/`RightCompartment` attributes are emitted.
- `_append_plates` / `_append_longs`: accept `materials: _MaterialIds | None`.
  When `None`, no `MaterialId` attribute is emitted.
- The scantling body loop (chain segmentation, stiffener assignment, and
  emission of `IDDATA`/`POSITION`/`MATERIAL`/`MISC`/`PANEL`s) is extracted
  into `_append_section_body(parent, vessel, cross_section, frame_table,
  extent, comp_boxes, materials, warnings)`. `_scantling` and `build_2dlx`
  both call it.
- The XML save logic (declaration, UTF-8, pretty print) becomes a shared
  helper used by `save_hmx` and `save_2dlx`.

New module `ocx_model_validator/sections/dlx_export.py`:

- `build_2dlx(vessel, cross_section, frame_table) -> etree._Element`
  - raises `ValueError` if `cross_section.plates` is empty (same as HMX)
  - root `CROSS_SECTION`; leading XML comment with de-duplicated warnings,
    same convention as HMX
  - calls the shared body with `comp_boxes=None, materials=None`
- `save_2dlx(root, path)` — shared save helper.

Rejected alternatives: (B) standalone duplicate exporter — ~300 duplicated
lines, double maintenance; (C) post-processing the HMX tree — fragile
strip-by-name coupling and needless ShipData/FrameTable work.

## 2DLX document layout

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CROSS_SECTION>
  <!-- warnings: ... (only when warnings exist) -->
  <administrative>
    <program name="ocx-model-validator" version="{package version}"/>
    <session_info date="15-Feb-2013" time="14:50:59"/>
  </administrative>
  <IDDATA>…</IDDATA>       <!-- NAME, DATE, SIGNATURE, COMMENTS: identical to HMX -->
  <POSITION>…</POSITION>   <!-- DISTAP (m), MIDSHIP; FromFrame/ToFrame omitted -->
  <MATERIAL>…</MATERIAL>   <!-- YIELDBOTT, YIELDDECK, YIELDBETW: identical to HMX -->
  <MISC>…</MISC>           <!-- STRUCTTYPE=SECTION, HSIDE, STDSPAN, STDSPACE -->
  <PANEL Name="…">…</PANEL><!-- one per plate chain, HMX rules minus deltas above -->
</CROSS_SECTION>
```

Content rules:

- `administrative/program`: `name="ocx-model-validator"`, `version` from
  package metadata (`importlib.metadata.version`), falling back to `"unknown"`
  if the distribution is not installed.
- `administrative/session_info`: schema-documented formats — date
  `%d-%b-%Y` (e.g. `15-Feb-2013`), time `%H:%M:%S`. The `user` attribute is
  omitted.
- `POSITION/FromFrame` and `ToFrame` are omitted; `DISTAP` is authoritative.
- `GlobalData` and `CONTMEMBER` are omitted (optional; nothing in the IR maps
  to them).
- Empty `CUTOUTS`/`TRVSTIFFS` wrappers are emitted per panel, mirroring the
  Nauticus empty-wrapper convention (same as HMX). Empty `LONGS` is likewise
  tolerated when a chain has no stiffeners.

## CLI

`validator section export` gains a format option:

```
validator section export MODEL.3docx (--frame FR20 | --x MM)
                         [--format 2dlx|hmx]      # default: 2dlx
                         [--rule-set DNV|RV5|CSR-H]  # hmx only
                         [-o FILE]
```

- Default output name: `<model-stem>-<tag>.2dlx` or `.hmx` depending on
  `--format` (via the existing `_default_section_output(..., suffix=...)`).
- Explicitly passing `--rule-set` together with `--format 2dlx` raises
  `typer.BadParameter` (usage error, exit 2). Detection: the `--rule-set`
  option defaults to `None`; HMX resolves `None` to `"DNV"`.
- Error handling mirrors the existing command: `GeometryError`,
  `SectionError`, `ValueError` → log + exit 1; `OSError` on write → exit 1.

## Testing

- New session-scoped `dlx_schema` fixture in `tests/conftest.py`, loading
  `tests/data/hmx_schema/CrossSection_2DLX.xsd` with XSD 1.1, mirroring
  `hmx_schema`.
- `tests/test_dlx_export.py`, mirroring `test_hmx_export.py`:
  - exported document validates against the 2DLX schema, allowing only the
    Nauticus empty-wrapper errors (`CUTOUTS`, `TRVSTIFFS`, `LONGS`)
  - bilge arc plate produces a signed-radius `SEGMENT`
  - `SEGMENT` elements carry no `LeftCompartment`/`RightCompartment`;
    `PLATE`/`LSTIFF` carry no `MaterialId`
  - `administrative` block present with program name/version
  - plate-less cross-section raises `ValueError`
- CLI tests in `tests/test_cli_section.py`:
  - `--format 2dlx` (and default) produce a `.2dlx` default output name
  - `--format hmx` keeps `.hmx`
  - `--rule-set` with `--format 2dlx` exits 2
  - unknown `--format` exits 2
- Full existing suite (including all HMX tests) must stay green — the
  refactor must not change HMX output.

## Documentation

Update the `cli.py` module docstring, `README.md`, and
`.github/copilot-instructions.md` usage blocks with the `--format` option and
a 2DLX example.

## Success criteria

1. `validator section export model.3docx --frame FRnn` writes a `.2dlx` file
   that Nauticus Hull imports cleanly.
2. `--format hmx` output is byte-identical to the pre-change HMX exporter.
3. All tests pass (`uv run pytest`).
