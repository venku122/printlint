import json
import subprocess

from printlint.compliance import compliance
from printlint.policy import ROOT
from printlint.report import new_report


def test_official_compliance_real_file():
    r = new_report()
    compliance(ROOT / "tests/fixtures/x2d-cube.3mf", r)
    assert r["compliance"]["parseable"] is True
    assert r["compliance"]["validation"]["nonStrict"]["valid"] is True


def test_mcp_build_geometry_colors():
    p = subprocess.run(
        [
            "node",
            str(ROOT / "tools/mcp-inspect.mjs"),
            str(ROOT / "tests/fixtures/x2d-cube.3mf"),
            "--full",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["list_build_items"]
    assert r["list_objects"]
    assert r["inspect_materials"]


def test_mcp_standard_materials():
    p = subprocess.run(
        [
            "node",
            str(ROOT / "tools/mcp-inspect.mjs"),
            str(ROOT / "tests/fixtures/core-colored.3mf"),
            "--full",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["inspect_materials"]["materialGroups"]["total"] == 1
    assert r["inspect_materials"]["materialGroups"]["items"][0]["entryCount"] == 2
