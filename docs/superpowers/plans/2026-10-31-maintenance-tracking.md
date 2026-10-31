# PrintLint maintenance and source tracking

Goal: monthly read-only update review, private GitHub source tracking, and reproducible portable validation.

Approach: retain pinned native macOS slicer setup; add a Linux container for static geometry/color/official-MCP checks. A script remains useful for macOS integration. No automatic upgrades, print submission, production profile edits, or public repository/image publication.

1. Create a monthly thread automation through the supported Codex tool; verify creation and schedule. Notify only for actionable changes.
2. Audit the source export, exclude logs/private evidence/environments, and initialize a private venku122/printlint repository. Preserve upstream source/license provenance.
3. Replace the hardcoded Homebrew Node path with executable discovery, proven by regression tests. Add a pinned Docker build and native/container instructions. Run container static validation and the complete native integration suite.
4. Push the reviewed code/plugin/tests/docs, verify the private remote and committed file set, and document maintenance/rollback and container limitations.

Verification: official MCP build/tests, Python regression suite, real Bambu/Orca X2D slicing, Docker build and read-only/no-network STL+painted/core 3MF validation. The Linux container does not claim native slicer or GUI-plugin acceptance. Keep source pins and lockfile fixed.
