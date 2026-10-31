# Slicer integration

Bambu executable: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio` (02.08.02.61). Stable Orca: `/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer` (2.4.2). Experimental Orca: `/Applications/OrcaSlicer-PrintLint-Beta.app/Contents/MacOS/OrcaSlicer` (2.5.0-beta).

The CLI uses `--datadir`, `--slice 0`, and `--outputdir`; Orca beta additionally uses `--export-statistics` and `--logfile`. No `--repair`, generic preset substitution, arrangement or orientation flags are used. Output G-code and resolved profile fields are retained. Exporting thumbnail-bearing sliced 3MF hung in the locked desktop session, so the default adapter exports G-code and statistics without graphics. Those probe processes were terminated; no production slicer process was terminated.

Bambu projects need recognized `BambuStudio:3mfVersion` metadata; without it the app can treat a package as generic and ignore embedded settings. PrintLint checks markers before slicing and output identity after slicing. Bambu and Orca process schemas differ: a Bambu project hit `raft_first_layer_expansion: -1 not in range` in Orca, and a newer Bambu application marker hit Orca's version gate. Neither was bypassed in the adapter. The separate Orca-native test fixture was generated from installed Orca X2D profile snapshots, with an Orca application marker, and succeeds.

Profiles in `config/bambu/` and `config/orca/` are resolved copies for provenance and fixture construction, not replacements for production presets. Beta ships profile packs and expands data internally; existing expanded system profiles were discovered under `~/Library/Application Support/OrcaSlicer/system/`. A matching preset name alone is insufficient; resolved G-code printer/process fields are checked.

Orca statistics schema v1 is parsed by documented keys and units. Raw JSON remains beside G-code. Purge/model ratio and maximum change thresholds are policy settings. Missing data is null; not all slicer versions export a breakdown. The real two-color fixture forces `filament_map_mode=Manual` and `filament_maps=1 1` at the plate level; changing only project-level mapping was overridden by automatic plate mapping. The final fixture yields 50 changes and about 20,000 mm³ flush, which triggers the ratio warning.

## Native plugin

Source: `plugins/printlint_native.py`. Installed only at `evidence/orca-native/data/orca_plugins/PrintLint/printlint_native.py`. Launch `./tools/orca-printlint`; do not double-click the beta app without the data-directory argument if you want isolation.

The plugin registers `PrintLint manual check` (Script) and `PrintLint slicing check` (SlicingPipeline). It requests no extra permissions and does not import compiled geometry dependencies. Parameters exposed by the host JSON config include enabled, max_triangles, min_feature_mm and block_nonmanifold. Default checks report non-manifold native meshes, import repairs, small local dimensions and triangle budget.

**Verified native UI acceptance on 2026-10-31; repeatable test procedure:**

1. Launch the isolated beta, finish any first-run UI, and open `tests/fixtures/orca-x2d-cube.3mf`.
2. In Plugins, enable PrintLint and Run `PrintLint manual check`. Verify findings/result dialog.
3. Select `PrintLint slicing check` in the process slicing-pipeline plugin picker (enabling a capability alone does not select it). Use only a temporary test project/process, not a production preset.
4. Set its `max_triangles` to 8: the 12-triangle cube intentionally violates policy. Slice. Verify `ExecutionResult.failure(FatalError, ...)` prevents successful completion and displays `ORCA.COMPLEXITY`.
5. Restore 10,000,000, slice again, verify success. Confirm the input hash/profile settings and geometry/G-code were not modified by the plugin.

Native automatic warnings are log/result messages; upstream's safe pipeline hook does not add GUI active-step warnings because it executes after step completion. Blocking FatalError is converted to a slicing error by the official hook. This behavior was verified inside the actual Orca GUI: zero findings from manual check, FatalError at a temporary eight-triangle limit, then clean reslicing after restoring defaults. The native GUI saved the selected capability reference as `printlint_native;;PrintLint slicing check`. Simply injecting the field into a project before UI selection did not activate it during the initial import. A user-assisted picker selection was required because that custom control was inaccessible to automation.

Full transformed geometry, color painting, mesh source defects and wall sampling remain external CLI preflight. Orca may repair meshes on import; native checks cannot reconstruct the original invalid source.

Sources: [Bambu CLI](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage), [Orca plugin API](https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugin_development), [slicing hook](https://github.com/OrcaSlicer/OrcaSlicer/wiki/slicing), [statistics](https://github.com/OrcaSlicer/OrcaSlicer/wiki/import_export).

The original synthetic CLI fixture lacked GUI-required `filament_self_index` metadata. The Orca fixtures now include the actual variant/self-index fields copied from the native GUI export, and a regression test verifies them. This did not alter the source models or production profiles.
