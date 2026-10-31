# Third-party provenance

PrintLint's own CLI/plugin sources are tracked here; no license for original project code has been selected for public redistribution. This repository is private. Upstream components retain their own licenses.

- `config/bambu/` and embedded Bambu fixture settings: resolved official Bambu Studio X2D presets, from the installed 02.08.02.61 resource tree. Bambu Studio: https://github.com/bambulab/BambuStudio (AGPL-3.0; included in LICENSES/AGPL-3.0.txt).
- `config/orca/` and embedded Orca fixture settings: official OrcaSlicer X2D presets, from 2.5.0-beta. OrcaSlicer: https://github.com/OrcaSlicer/OrcaSlicer; source revision and wiki revision recorded in dependencies.json (AGPL-3.0).
- `tests/fixtures/3DBenchy.stl`: unmodified Creative Tools #3DBenchy model, https://github.com/CreativeTools/3DBenchy at the revision in dependencies.json, with its SHA-256 recorded there. Attribution: Creative Tools, https://www.3dbenchy.com/. It is a separately authored benchmark, not a PrintLint-generated design.
- Other test models are synthetic PrintLint fixtures. Statistics are actual captured outputs for those synthetic fixtures.
- The source repositories for official 3MF MCP (BSD-2-Clause), MMU Remapper (MIT), and the advisory 3D Print Validator are fetched at exact revisions during setup, not committed. Their upstream LICENSE files are retained. MMU's local patch changes packaging metadata only; see config/mmu-packaging.patch.
- Python/Node dependencies retain the licenses distributed in their pinned packages. Docker base images retain their upstream notices.
