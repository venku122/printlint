# Maintenance policy

The monthly PrintLint update check is a Codex thread automation, scheduled for the first day of each month at 09:00 America/Chicago. It reviews official upstream sources and local pins without installing or upgrading anything. It stays quiet without actionable changes and avoids repeating unchanged findings. Its saved prompt covers security/stability fixes, relevant X2D/AMS features, slicer CLI/statistics compatibility and the experimental Orca Python API. The Mac must be awake with the app running for local checks; inspect Scheduled for run/failure history.

## Upgrade procedure

1. Read `dependencies.json`, `uv.lock`, `Dockerfile` digests and actual installed slicer versions; compare official release notes and security advisories. Report concrete benefit and compatibility risk. A new commit alone is not an upgrade recommendation.
2. Back up relevant slicer/custom profiles and Codex configuration privately. Work on a branch; keep current production slicers functional. Do not broadly restore old backups over newer user edits.
3. For approved updates only, change exact source revisions, regenerate lockfiles intentionally and review the MMU packaging patch against its new revision. Do not replace a known source pin with a moving branch. `tools/setup.sh` reinstalls pinned versions; it is not an updater.
4. Run the full native suite with `PRINTLINT_INTEGRATION=1 uv run pytest -q`, official MCP tests/build, ruff, and a fresh container build/smoke check. Compare real X2D printer/process/material settings, statistics schema, warnings, purge ratios and unchanged input hashes. Do not hide Bambu's known reserved-tool parser errors.
5. For an Orca/plugin update, verify the actual manual action, deliberate invalid-job block, and clean reslice after restoring thresholds. Unit tests or container tests cannot replace native GUI acceptance. Keep beta data isolated.
6. Promote only tested revisions after authorization, record evidence privately and update the status/report. Revert the code/lock/digest commit or select the retained previous image/app for rollback. Restore individual profiles only when necessary and reviewed.

## Tracking and automation boundaries

Repository: private `venku122/printlint`. Track CLI/plugin sources, tests, synthetic fixtures, preset snapshots, dependency pins and documentation. Exclude `evidence/`, logs, environments, downloaded vendor repositories, credentials and real print projects. Fresh checkout dependencies are reconstructed from verified pins.

GitHub CI builds and tests the portable image on pushes/PRs; it does not publish an image, update dependencies, run native macOS GUI tests or print. There is no automatic dependency-upgrade bot. Source tracking does not back up private native acceptance screenshots or the user's live profiles.

Cancel/pause the monthly check through the Codex Scheduled interface. The automation id is `monthly-printlint-update-check`.
