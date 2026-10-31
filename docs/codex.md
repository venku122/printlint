# Codex / official 3MF MCP

Registered with the installed Codex 0.166.0 CLI:

```sh
codex mcp add 3mf -- /opt/homebrew/bin/node /Users/tjt/src/3d_printing/printlint/vendor/3mf-mcp/dist/cli.js
codex mcp get 3mf --json
```

This writes the supported `[mcp_servers.3mf]` stdio configuration using the CLI, preserving other configured servers. No unauthenticated HTTP service is exposed. A new Codex session or MCP reload is required to expose newly registered tools in an already-running chat. The independent official MCP SDK client verified real requests against this exact local executable; no claim is made that this existing chat has hot-reloaded the server.

Use `load_model(path=...)`, retain its returned `modelId`, then call `check_compliance(model_id=...)`, `inspect_model`, `list_objects`, `inspect_object(resource_id=...)`, `list_build_items`, `inspect_materials`, and `validate_model` using that ID. Use pagination for large models. `check_compliance(path=...)` also returns diagnostics for unreadable files. The server's core materials view covers standard resources; vendor painting and palette mapping require `printlint colors` too.

A direct reproducible roundtrip is provided:

```sh
node tools/mcp-inspect.mjs "$PWD/tests/fixtures/x2d-cube.3mf" --full
```

The `--full` probe loads and inspects the model, lists mesh objects/build transforms, inspects materials/colors and returns compliance findings. The core CLI uses `check_compliance` through this bridge on each 3MF. Official upstream tests cover standard material resources as well as geometries; a vendor project without standard materials can correctly return an empty material group list.

Local visual rendering is optional and has not been enabled: structural validation works without browser/viewer dependencies. Review 3D appearance in the existing CAD/slicer tools. Do not equate a structurally nonempty color palette with artistic correctness.

Default agent workflow (persisted in `/Users/tjt/.codex/AGENTS.md` and workspace `AGENTS.md`; new Codex runs load the global instructions):

1. Keep parametric CAD source and export alongside it.
2. Run `printlint check` and `printlint colors` with JSON output; supply a local manifest if known.
3. Repair source defects, re-export and re-run. Do not silently fix the input or remap colors.
4. Save an explicit X2D project in the intended slicer and run `printlint slice ... --slicer bambu|orca` into a fresh directory. Both paths run full preflight before launching the slicer and save `preflight.json`. Errors and infrastructure failures block launch; warnings block with `--strict`. Policy and manifest apply to preflight. Direct GUI/MCP slicing requires a separate full check on the same final project; recheck after geometry, placement, filament or tool changes. Bambu Studio's manual Slice button is not intercepted; the Orca native hook is supplemental and process-specific.
5. Inspect diagnostics, material use, purge ratio, tool assignments, supports/islands and first-layer preview.
6. Describe the result as ready for **manual** printing only when relevant findings are resolved. Printer state, bed/plate, actual AMS spools and time-lapse send option are a separate live/manual check.

No automatic submission or print start is authorized by linting or slicing. The workspace's existing printer-control approval rules remain in force.
