"""Exercise the real stdio boundary with a synthetic, oversized diagnostic response."""

import json
import subprocess
import zipfile

from printlint.policy import ROOT


def test_large_vendor_warning_response_is_readable_and_compact(tmp_path):
    target = tmp_path / "many-painted-faces.3mf"
    # One diagnostic per vendor-painted triangle produces a response above SDK's 10 MiB default.
    triangles = '<triangle v1="0" v2="1" v3="2" paint_color="4"/>\n' * 90000
    model = (
        '<?xml version="1.0"?><model unit="millimeter" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<resources><object id="1" type="model"><mesh><vertices>'
        '<vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>'
        '<vertex x="0" y="1" z="0"/></vertices><triangles>'
        + triangles
        + '</triangles></mesh></object></resources><build><item objectid="1"/></build></model>'
    )
    with zipfile.ZipFile(ROOT / "tests/fixtures/x2d-cube.3mf") as fixture:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for name in fixture.namelist():
                z.writestr(name, model if name == "3D/3dmodel.model" else fixture.read(name))
    result = subprocess.run(
        ["node", str(ROOT / "tools/mcp-inspect.mjs"), str(target)],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)["compliance"]["validation"]["nonStrict"]
    assert data["valid"] is True
    assert data["warningCount"] >= 90000
    assert sum(item.get("occurrences", 1) for item in data["warnings"]) == data["warningCount"]
    assert len(result.stdout) < 100000
