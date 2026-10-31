# PrintLint development

Use uv sync / uv run in this directory, with the pinned Python environment and lockfile. Read parent AGENTS.md too. No printer networking or control is part of this toolchain.

Apply the parent default validation workflow to every CAD export and imported print model, before any CLI, GUI or MCP slice. Use printlint slice for either Bambu Studio or OrcaSlicer so full preflight automatically gates slicer launch; direct GUI/MCP tools require a separate check of the same final project. Revalidate after geometry, plate placement or filament/tool changes. Before calling a model ready, repair blocking findings, slice using explicit X2D presets and inspect the report/preview. A static pass never authorizes printing. Preserve the user's timelapse preference in a separately authorized manual send workflow.

Do not commit evidence/, vendor environments, private configuration, printer credentials, personal project metadata or screenshots. Synthetic test fixtures and official profile snapshots are safe local implementation artifacts. Record source revisions in dependencies.json and keep tests/fixtures/statistics labelled as actual captured slicer output.

Native plugin GUI acceptance is recorded in docs/validation-status.json and evidence/orca-native/native-acceptance.json. Future API/plugin changes require rechecking the actual manual action, deliberate FatalError slice block and clean reslice; unit tests alone are insufficient.
