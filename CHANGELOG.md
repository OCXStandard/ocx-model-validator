# Changelog

## 0.4.0 — 2026-10-01

### Removed (breaking)

- The `ocx_model_validator.sections` package (cross-section building, JSON
  document, 2DLX/HMX export, SVG plot, EPP splitting, section properties).
  This functionality now lives in the `nh-sections` package of the
  [nh-mcp](https://github.com/ocastrup/nh-mcp) project.
- `validator section create/export/plot` CLI commands.
- `build_cross_section` and `save_cross_section` MCP tools (the `ocx-mcp`
  server now exposes 5 tools).
- 2DLX/HMX schemas, sample section artefacts and related tests.
- Unused `numpy` runtime dependency and `xmlschema` dev dependency.

### Changed

- Generic helpers formerly in `sections/` relocated into core:
  - `ocx_model_validator.frame_table` — `FrameTable`, `build_frame_table`,
    `frame_table_block`.
  - `ocx_model_validator.model.units` — `to_si`, `qty_mm`, `qty_m3`,
    `qty_kpa`, `point_mm`.
  - `ocx_model_validator.reporting.generators._compartment_data` —
    `build_compartments_block` and curve-point sampling helpers.
- `ocx` dependency pinned to the final `>=3.2.0` release.

## 0.3.0 and earlier

See the git history.
