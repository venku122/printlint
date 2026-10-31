# Validation report — 2026-10-31

## Status

Installed and implemented CLI, dependencies, offline slicer adapters, native plugin source/isolated installation and official stdio MCP registration. **Native GUI acceptance is now complete:** after unlock, the manual action passed, the selected automatic hook blocked a deliberate violation, defaults were restored and clean fresh slices succeeded. Evidence is in `evidence/orca-native/`.

## Tests

- `PRINTLINT_INTEGRATION=1 uv run pytest -q`: **52 passed**, including both real installed macOS slicers; no integration skips in that run.
- Official 3MF MCP `npm test`: **18 passed across 7 files**. `npm ci`, TypeScript build and real stdio MCP requests succeeded.
- `ruff check src tests plugins`: passing after formatting/import cleanup.
- Reproducible `tools/setup.sh`: frozen uv install, npm ci, 18 upstream tests, build, and local non-integration suite rerun successfully.
- Separate beta code signature and Gatekeeper assessments both return 0; no security exception was needed.
- `printlint doctor --json`: exits 0 for installed core environment; records the verified native plugin acceptance without the former `DOCTOR.PLUGIN` warning. Strict operation remains useful for warning-sensitive CI.
- Production preservation: **8,192 JSON/INI files plus 3 main .conf files unchanged**. Both working app paths retained.

Coverage includes cube; original Benchy with reported degenerate/open-boundary advisories; non-manifold solid topology; open hole; thin wall; oversized mesh; build/component transforms and centimeter translation; painted face reads; invalid palette references; unknown physical AMS; all declared plates; tool and part/paint restrictions; real high-purge statistics; JSON/SARIF; strict mode; malformed inputs; deterministic sampling; bounded component DAG expansion; changed effective profiles; and case-independent fatal/error diagnostics.

## Source tracking and portable validation

Private GitHub source tracking and a digest-pinned Dockerfile/CI workflow were added. Native regression coverage now includes automatic preflight gates, PATH-based Node selection and Orca packaged-preset discovery. An initial native rerun caught the adapter treating binary `.opc` presets as missing; it now delegates native cache resolution to Orca and still rejects mismatched effective output profiles. The complete final native suite passed (52 tests), ruff passed and doctor returned zero.

The local Docker engine timed out on build/daemon requests, so no local container build success is claimed. GitHub CI builds the image, runs the upstream MCP and portable Python suites, and tests static checks with read-only models and networking disabled. Container acceptance must be assessed from that CI run. macOS application/GUI tests are outside the container's scope.

## Real offline slicing

| Test | Result | Available estimate |
|---|---|---|
| Bambu X2D cube | Process exit 0, explicit X2D output verified; upstream reserved-tool parser errors retained as validation errors | 9m19s, 0.73 g |
| Orca-native X2D cube | Clean slice and statistics export | 545.564 s, 0.6458 g, 50 layers, 0 filament changes |
| Orca X2D two-color / same-nozzle fixture | Slice successful, purge warning as expected | 5400.338 s, 50 filament changes, 19,999.981 mm³ flush / 1,025.122 mm³ model = 19.5099 ratio |

These are synthetic test objects, not the earlier scraper/bucket print. No uploads or physical prints occurred. First-layer adhesion, support adequacy and artistic color correctness still need visual inspection.

## Failed probes and corrections

1. Original MMU Remapper metadata did not build under modern setuptools. Fixed only package metadata through the recorded patch; remapping source unchanged.
2. Initial unmarked synthetic 3MF was sliced with generic defaults by Bambu. Added vendor project metadata to the test fixture and verified actual output settings. Adapter rejects missing markers and effective profile drift.
3. Bambu → Orca direct project failed on incompatible process value and newer application marker. No adapter bypass or automatic project rewrite added. A separate fixture was built from actual Orca X2D profiles.
4. Thumbnail-bearing sliced-3MF export probes hung while the desktop was locked; only those test subprocesses were stopped. Default headless workflow exports G-code/statistics without graphical export.
5. Initial multicolor prime tower was outside the plate; synthetic fixture placement corrected. No originals changed.
6. Automatic plate mapping chose separate toolheads and produced zero changes/flush. Explicit plate-level same-nozzle mapping gave genuine high-purge statistics. No statistics were invented to force a warning.
7. Upstream Benchy STL contains 563 degenerate faces. The validator reports them, excludes them only from analysis topology counts, and preserves the original source hash. The advisory distinction prevents collapsed triangles from creating false solid-edge errors.
8. Final review found component expansion, part/paint tool, profile-comparison, malformed-manifest and severity gaps. Eleven regression cases were added and pass after fixes. The full 45-test suite passed afterward.

## Native Orca completed checks

Read-only manual and pipeline capabilities are installed and activated in `evidence/orca-native/data`, with no extra permissions. The manual Run action returned zero findings. At max_triangles=8 the 12-triangle cube stopped with the expected ORCA.COMPLEXITY slicing error. Defaults were restored to 10,000,000, fresh slices completed, and the original 0.20 mm layer height was restored. Geometry part bytes compare identical between the baseline and final test projects; only deliberate configuration changes are recorded in native-acceptance.json. The custom picker needed a user-assisted selection because coordinate automation could not operate it.

## Prioritized follow-up

1. Use the isolated beta and select the lint hook in each intended test process; preserve the production stable setup.
2. Resolve/understand Bambu's reserved-tool parser errors before treating its CLI report as clean; Orca-native offline slicing is currently the cleaner test path.
3. Extend complex recursive vendor paint decoding using authoritative upstream semantics or the new native inspect-paint command; keep unknowns explicit meanwhile.
4. Add additional material manifests and policy thresholds based on actual intended projects, and visual slicer review for supports, adhesion and purge tradeoffs.
5. Optional browser-based MCP rendering after viewer prerequisites are verified; structural inspection needs no viewer.
