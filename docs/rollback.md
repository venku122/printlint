# Uninstall / rollback

Production slicer configuration was backed up privately before changes to `evidence/slicer-config-backup-20261031.tar.gz`; Codex configuration to `evidence/codex-config-backup.toml`. Their contents can include account data and must remain private. `evidence/production-config-hashes.json` records pre-change hashes of JSON/INI configuration; `evidence/production-preservation.json` records the final comparison.

No production slicer profile or working app was intentionally changed, so restoring them is normally unnecessary. Do not blanket-restore the archive over newer user edits. If needed, quit the relevant app and selectively restore the specific configuration/profile from the archive after reviewing differences.

To remove this toolchain:

1. Quit the experimental beta.
2. `codex mcp remove 3mf` removes only the new MCP registration. Do not replace the entire Codex config from backup if it now contains other changes.
3. Remove `/Users/tjt/.local/bin/printlint` (the new launcher only).
4. Remove `/Applications/OrcaSlicer-PrintLint-Beta.app` (the separate experimental copy only).
5. Remove this `printlint` directory after preserving any wanted reports/fixtures. Its uv environment, vendor clones, plugin data and experimental profiles are all inside it.

Keep `/Applications/BambuStudio.app`, `/Applications/OrcaSlicer.app`, both production Application Support directories, existing CAD tools and private printer configuration intact. No Homebrew packages were installed or upgraded for this task. No login items, printer settings or security exceptions were changed.

The default workflow was also added to `~/.codex/AGENTS.md` and the parent printing workspace `AGENTS.md`. If uninstalling PrintLint, remove only its workflow sections so future agents do not invoke a removed launcher. Pause/delete `monthly-printlint-update-check` in Scheduled. The GitHub repository remains a separate source backup. Remove only the PrintLint image tag if unwanted; never use Docker system-wide prune as an uninstall step.
