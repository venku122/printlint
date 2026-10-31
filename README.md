# PrintLint for macOS / X2D

Local, read-only STL/3MF validation, vendor color inspection, official lib3mf compliance, and actual offline slicing. Installed in `/Users/tjt/src/3d_printing/printlint` alongside the existing CAD workspace. No printer connection, upload, movement, heating or print submission is implemented.

## Daily use

```sh
printlint doctor
printlint check model.stl
printlint check project.3mf --json
printlint colors project.3mf
printlint colors project.3mf --manifest config/local-filaments.json
printlint check model.stl --advisory
printlint check project.3mf --strict --format sarif > findings.sarif
printlint slice bambu-project.3mf --slicer bambu --output /tmp/bambu-review
printlint slice orca-project.3mf --slicer orca --output /tmp/orca-review
```

Both `--slicer bambu` and `--slicer orca` automatically run full preflight on the exact copied project **before launching the slicer**. Errors and infrastructure failures block launch; warnings block with `--strict`. The report is saved as `preflight.json` and included in JSON output. `--policy` and `--manifest` also apply to this preflight.

This is the default Codex CAD/print workflow through global and workspace instructions. Revalidate after geometry, placement, filament or tool changes. Direct GUI/MCP slicing requires a separate `printlint check` on the same final input; Bambu Studio's manual Slice button is not intercepted. Orca's selected native hook is supplemental.

Output directories must be empty. Slicing copies the input into the output directory and uses a new slicer data directory. It preserves embedded settings, checks resolved printer/process identifiers in the G-code, and captures the subprocess exit status and diagnostics. Cross-slicer projects can fail: do not strip errors or substitute a generic printer.

Exit codes: **0** no blocking errors (warnings may exist), **1** validation errors, **2** execution/infrastructure failure. `--strict` makes warnings fail. Every diagnostic includes rule, severity, object/plate when known, measurement, explanation and corrective action. A pass is a static preflight, not authorization or proof of successful printing.

The launcher is `/Users/tjt/.local/bin/printlint`. Equivalent: `uv run --project /Users/tjt/src/3d_printing/printlint printlint ...`. Python is project-local, not system Python.

## Reproducibility and upkeep

Source and native plugin are tracked in the private `venku122/printlint` repository. A monthly read-only update check reports worthwhile changes without upgrading. See [maintenance](docs/maintenance.md).

A digest-pinned [Docker image](docs/container.md) runs geometry, color and official 3MF checks. Keep the native uv/script setup for actual macOS slicing and Orca plugin execution.

## Installed components

- Python 3.12.16 in `.venv`, managed by uv 0.13.6; exact Python package versions in `uv.lock`.
- Trimesh 5.2.0, NumPy/SciPy, Rtree spatial indexing, NetworkX, defusedxml.
- Official `3MFConsortium/3mf-mcp` 0.1.0-alpha.1 in `vendor/3mf-mcp`, built from the revision in `dependencies.json`; official WASM lib3mf 2.6.0-alpha.2. Node 26.13.0 / npm 11.20.0.
- MMU Remapper 0.1.0 in the local environment, source in `vendor/mmu-remapper`; packaging-only compatibility patch in `config/mmu-packaging.patch`.
- Community 3D Print Validator source in `vendor/3d-print-validator`, optional `--advisory` only. No native lib3mf or CadQuery dependency installed.
- Existing Bambu Studio 02.08.02.61 at `/Applications/BambuStudio.app` and Orca stable 2.4.2 at `/Applications/OrcaSlicer.app` retained.
- Separate official Orca 2.5.0-beta at `/Applications/OrcaSlicer-PrintLint-Beta.app`; experimental data at `evidence/orca-native/data`. Use `tools/orca-printlint` to launch this instance.

Exact upstream revisions, DMG checksum and source URLs are in `dependencies.json`. Slicer profile snapshots and policy provenance are in `config/`. The X2D defaults are 256 × 256 × 261 mm, two 0.4 mm nozzles, 0.42 mm line width and 0.20 mm layers, resolved from installed X2D presets. The second tool's X area begins at 20.5 mm. Policy thresholds such as two-line wall thickness are configurable heuristics.

## What is verified

STL and transformed/component 3MF geometry, bounded ZIP/XML reading, official compliance, simple painted face assignments, object/volume filament assignments, palette/manifests, unknown physical AMS state, JSON/SARIF/exit codes, deterministic geometry sampling, and real X2D offline slicing with both apps. Orca exports schema-versioned statistics, including actual purge/prime-tower and per-layer/object data. A two-color X2D test produced 50 changes and a 19.51 purge/model ratio and triggered the configured warning.

Bambu's process completes with X2D settings but its G-code parser logs `Invalid T command (T65279)` / `(T65535)` on the full embedded preset. PrintLint retains those as errors; it does not certify this output as clean. Orca's separate native fixture slices cleanly. Models are not sent to a printer.

**Native plugin GUI acceptance is verified:** the manual action reported zero findings; an eight-triangle budget blocked the 12-triangle cube with `ORCA.COMPLEXITY`; restoring 10,000,000 allowed fresh slices and the normal 0.20 mm preview. Geometry part bytes are unchanged. See [plugin steps](docs/slicer-integration.md).

## Limits

- Physical AMS spools are unverified. A supplied manifest is a declaration, not a live measurement. Appearance/artistic correctness is always unverified.
- MMU Remapper's codec understands simple paint tokens. Complex recursive split-triangle streams are counted but explicitly opaque; they must be inspected in the slicer.
- Ray-sampled thin walls, overhang area, disconnected/floating geometry are advisories. This does not prove minimum thickness, resolve supports/bridges, certify self-intersections, or test fit, strength or bed adhesion.
- STL units/placement are not embedded. STL is interpreted as mm; envelope checks use its dimensions. Configured 3MF checks use build positions and transforms.
- Original Benchy STL has 563 collapsed/degenerate faces. These are reported; topology is measured on an analysis copy excluding those faces to avoid counting zero-area triangles as solid non-manifold edges. No source is repaired. Remaining open boundaries warn; the sample has no blocking findings.
- Native plugin uses lightweight local mesh checks only. Full transformed bounds, painting, compliance and sampled thickness remain CLI preflight requirements.

## Reproduce / test

```sh
./tools/setup.sh
uv run pytest -q
PRINTLINT_INTEGRATION=1 uv run pytest -q
uv run ruff check src tests plugins
node tools/mcp-inspect.mjs "$PWD/tests/fixtures/x2d-cube.3mf" --full
```

The setup script verifies pinned source revisions, applies the recorded packaging patch, installs the frozen uv environment, and runs official MCP tests/build and the local suite. macOS apps are separate signed downloads; the existing applications are never replaced. `tests/fixtures/statistics/` contains real Orca outputs for deterministic CI tests, not invented estimates. Fixtures contain no printer identities or credentials.

See [architecture](docs/architecture.md), [slicer integration](docs/slicer-integration.md), [Codex/MCP](docs/codex.md), [community review](docs/community-review.md), [validation report](docs/validation-report.md) and [rollback](docs/rollback.md).
