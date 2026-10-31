# PrintLint Implementation Plan

Goal: deliver an offline, read-only validation CLI with verified X2D slicing, official 3MF MCP and native Orca beta integration.
Architecture: Python package in the existing printing workspace; transformed 3MF scene traversal and deterministic Trimesh checks; optional community advisory; external stdio lib3mf compliance; isolated slicer subprocesses. Stable applications and production data remain untouched.
Spec: user directive in this chat, phases 1–8.

## Constraints
No printing, uploads, printer controls, profile overwrites, HTTP MCP service, global pip, or secret/project metadata commits. Node >=22, uv local Python. Unknown live AMS must be reported explicitly. Use source revisions and lockfiles.

## Tasks
- [ ] 1. Audit and private backups; pin source repositories, review community code, install isolated dependencies and beta.
- [ ] 2. Test-first CLI geometry/package/color checks. Modules policy.py, geometry.py, package.py, report.py, cli.py. Tests cover cube, Benchy, holes, nonmanifold, thin, bounds, transforms, invalid references, plates, tools and unknown AMS. Exit 0/1/2, strict and JSON/SARIF.
- [ ] 3. Test-first slicer adapters/stats. Copy project, preserve embedded X2D settings, separate datadir; capture logs/artifacts/statistics, report unsupported fields. Real X2D headless smoke test plus high purge statistics fixture.
- [ ] 4. Native Orca read-only manual and slicing capabilities using supported APIs. Actual beta execution and deliberate blocking failure; record unsupported hooks honestly.
- [ ] 5. Build/test official MCP, register actual stdio path using local Codex CLI, real 3MF geometry/material/compliance roundtrip.
- [ ] 6. Documentation, reproducible bootstrap/uninstall, full suite, doctor, unchanged-production hash verification and acceptance report.

## Review focus
Malformed ZIP/XML, reference cycles and cross-part transforms; resource limits; realistic vendor paint encoding; independent plate coordinate origins; absent/mismatched profiles; plugin read-only behavior; upstream API failures cannot become passes.

Execution: autonomous inline as requested. No additional design approval gate; user's explicit execution directive governs. Dedicated subdirectory rather than a worktree because parent workspace has no Git repository.

## Execution ledger

2026-10-31: Tasks 1, 2, 3, 5 and 6 implemented; task 4 source and isolated installation implemented, GUI acceptance blocked by locked Mac.
Ruling: existing parent is not a Git repository, so use isolated printlint subdirectory and source/lockfile pins; no personal project commits.
Ruling: preserve headless output as G-code/statistics; graphical sliced-3MF probes hung on locked desktop. No generated file is print authorization.
Ruling: Bambu reserved-tool log errors remain blocking diagnostics even with subprocess exit 0. No silent downgrade.
Ruling: retain complex paint as unknown, community score as advisory and actual AMS as unverified.
Final review: fresh reviewer identified five defects; 11 regressions added and fixed, complete suite 45/45 including two real slicer integration tests. No printer control calls found.
Remaining external blocker: unlock Mac, run manual plugin capability, select slicing hook on a temporary process, demonstrate deliberate FatalError block and clean rerun. Do not mark fully accepted until this evidence exists.

2026-10-31 follow-up: native manual Run passed; user selected custom pipeline picker; 12-triangle cube blocked by max_triangles=8/FatalError; defaults restored; fresh slice passed at original 0.20 mm. Geometry bytes unchanged. Full suite now 46 passing, including the GUI-metadata regression. Native acceptance is complete.
