"""Real installed macOS applications; opt in for CI on other platforms."""

import os

import pytest

from printlint.policy import ROOT
from printlint.slicer import slice_project

pytestmark = pytest.mark.skipif(
    os.environ.get("PRINTLINT_INTEGRATION") != "1",
    reason="Set PRINTLINT_INTEGRATION=1 for actual macOS slicers",
)


def test_bambu_real_x2d(tmp_path):
    r = slice_project(ROOT / "tests/fixtures/x2d-cube.3mf", "bambu", tmp_path / "bambu")
    assert r["slicer"]["exit_status"] == 0
    assert r["slicer"]["source_unchanged"]
    assert r["statistics"]["plates"][0]["resolved_profile"]["printer_model"] == "Bambu Lab X2D"
    # Preserve upstream parser errors in diagnostics; exit status alone is not clean validation.
    assert any(d["rule_id"] == "SLICE.DIAGNOSTIC" for d in r["diagnostics"])


def test_orca_real_x2d(tmp_path):
    r = slice_project(ROOT / "tests/fixtures/orca-x2d-cube.3mf", "orca", tmp_path / "orca")
    assert r["exit_code"] == 0, r["diagnostics"]
    stats = r["statistics"]["plates"][0]
    assert stats["layer_count"] == 50
    assert stats["filament_g"][0] > 0
    assert stats["objects"]


def test_orca_fixture_has_gui_variant_metadata():
    import json
    import zipfile

    with zipfile.ZipFile(ROOT / "tests/fixtures/orca-x2d-cube.3mf") as z:
        cfg = json.loads(z.read("Metadata/project_settings.config"))
    assert cfg.get("filament_self_index")
    assert len(cfg["filament_self_index"]) == len(cfg["filament_extruder_variant"])
