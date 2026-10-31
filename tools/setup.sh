#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v uv >/dev/null
command -v node >/dev/null
command -v npm >/dev/null
python3 - <<'PY'
import json,pathlib,subprocess
pins=json.load(open('dependencies.json'))
for name in ['3mf-mcp','mmu-remapper','3d-print-validator']:
 p=pathlib.Path('vendor')/name;pin=pins[name]
 if not p.exists():
  subprocess.run(['git','clone','--no-checkout',pin['url'],str(p)],check=True)
  subprocess.run(['git','-C',str(p),'checkout','--detach',pin['revision']],check=True)
 rev=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
 if rev!=pin['revision']:raise SystemExit('Revision mismatch: '+name)
p=pathlib.Path('vendor/mmu-remapper/pyproject.toml');s=p.read_text()
if 'long_description_content_type' in s:
 subprocess.run(['git','-C','vendor/mmu-remapper','apply',str(pathlib.Path('config/mmu-packaging.patch').resolve())],check=True)
PY
uv sync --frozen --python 3.12
(cd vendor/3mf-mcp && npm ci && npm test && npm run build)
uv run pytest -q
printf '%s\n' 'Ready. macOS slicer apps are preserved and installed separately; see docs/slicer-integration.md.'
