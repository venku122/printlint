# Architecture

`printlint` is a Python entry point. It reads STL with Trimesh and 3MF as a size-bounded OPC ZIP package using defusedxml. Model units, production-extension cross-part component references, nested transforms and mirrored winding are applied to build-item geometry before measurement. Cycles, missing resources, invalid vertex references and malformed transforms fail validation.

Vendor plate metadata associates object instances with plates. Recognized Bambu/Orca virtual plate origins follow upstream `PartPlateList`: ceil(sqrt(plate_count)) columns, 20% bed-width/depth spacing, negative Y for later rows. Explicit `plate_origin` overrides take precedence. Unknown vendor conventions are not inferred from object bounds.

Geometry checks use analysis copies only. Coincident STL vertices are welded on the copy; degenerate faces are counted and excluded from topology edge counts so their collapsed edges do not masquerade as solid non-manifold connections. Open surfaces warn by default (`surface_policy: error` can block). Separate components are information; ray-sampled thin features and downward surfaces warn. Envelope violations and genuine edges shared by >2 non-degenerate faces error. Self-intersections and mechanical suitability remain unverified.

All 3MF checks also launch the locally built official MCP server over ephemeral stdio. Its lib3mf strict/non-strict reader findings are preserved. Unreadable core packages block; readable vendor extensions that fail strict compliance warn. Infrastructure failures return 2. No HTTP listener or viewer is needed for these checks.

Color inspection combines core property groups, triangle property references, Bambu/Orca paint tokens, model-settings object/volume extruders, project palette and filament/tool maps. An optional manifest compares declared colors/materials/tools/AMS slots. Slot names are retained as declarations, never evidence of actual loaded spools. Complex paint is marked opaque.

Slicer adapters copy inputs and use independent data directories. They invoke installed app executables, retain subprocess logs, verify resolved output printer/process identities, and parse known G-code headers. Orca schema version 1 JSON supplies unit-labelled summary, filament breakdowns, objects and layers. Unknown fields are tolerated; missing metrics stay null. Bambu headers are not treated as a complete Orca statistics substitute.

Native Orca capabilities use only read-only host bindings. No files, network, subprocesses, threads, geometry mutations or G-code writes are requested. The slicing hook reads the worker's `ctx.object.model_object()` snapshot at `posSlice`; it never calls UI from the slicing thread. Heavy checks remain external.

Default loop: Generate → Export → CLI lint → Repair source → Slice configured project → Inspect report and slicer preview → Ready for manual printing. Timelapse preference belongs to the separately authorized manual send dialog.
