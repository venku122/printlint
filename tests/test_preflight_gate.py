import json
import re
import zipfile

from printlint.policy import ROOT
from printlint.slicer import SLICERS, slice_project


def copied_project(tmp_path, defect=False):
    p = tmp_path / "model.3mf"
    with zipfile.ZipFile(ROOT / "tests/fixtures/x2d-cube.3mf") as z:
        members = {n: z.read(n) for n in z.namelist()}
    if defect:
        s = members["3D/3dmodel.model"].decode()
        triangle = re.search(r"<triangle\s[^>]*/>", s).group()
        members["3D/3dmodel.model"] = s.replace("</triangles>", triangle + "</triangles>").encode()
    with zipfile.ZipFile(p, "w") as z:
        for n, d in members.items():
            z.writestr(n, d)
    return p


def fake_slicer(tmp_path, monkeypatch):
    marker = tmp_path / "launched"
    exe = tmp_path / "slicer"
    exe.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 93\n')
    exe.chmod(0o755)
    monkeypatch.setitem(SLICERS, "bambu", exe)
    return marker


def test_geometry_error_blocks_slicer(tmp_path, monkeypatch):
    marker = fake_slicer(tmp_path, monkeypatch)
    r = slice_project(copied_project(tmp_path, defect=True), "bambu", tmp_path / "out")
    assert not marker.exists(), "Invalid geometry reached the slicer"
    assert r["exit_code"] == 1
    assert any(d["rule_id"] == "GEO.NONMANIFOLD" for d in r["diagnostics"])
    assert json.loads((tmp_path / "out/preflight.json").read_text())["exit_code"] == 1


def test_manifest_failure_blocks_slicer(tmp_path, monkeypatch):
    marker = fake_slicer(tmp_path, monkeypatch)
    r = slice_project(copied_project(tmp_path), "bambu", tmp_path / "out", manifest=[1])
    assert not marker.exists()
    assert r["exit_code"] == 2


def test_strict_warning_blocks_slicer(tmp_path, monkeypatch):
    marker = fake_slicer(tmp_path, monkeypatch)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"min_wall_mm": 20}))
    r = slice_project(copied_project(tmp_path), "bambu", tmp_path / "out", policy, strict=True)
    assert not marker.exists()
    assert r["preflight"]["exit_code"] == 1


def test_warning_permits_slicer_without_strict(tmp_path, monkeypatch):
    marker = fake_slicer(tmp_path, monkeypatch)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"min_wall_mm": 20}))
    r = slice_project(copied_project(tmp_path), "bambu", tmp_path / "out", policy)
    assert marker.exists()
    assert r["preflight"]["exit_code"] == 0
    assert any(d["rule_id"] == "GEO.THIN" for d in r["diagnostics"])


def test_orca_packaged_profiles_defer_to_output_verification(tmp_path, monkeypatch):
    exe = tmp_path / "Orca.app/Contents/MacOS/OrcaSlicer"
    exe.parent.mkdir(parents=True)
    marker = tmp_path / "orca-launched"
    exe.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 93\n')
    exe.chmod(0o755)
    profiles = exe.parent.parent / "Resources/profiles"
    profiles.mkdir(parents=True)
    # Discovery only: Orca itself must parse the cache and output-profile checks remain mandatory.
    (profiles / "BBL.opc").write_bytes(b"ZCRO")
    monkeypatch.setitem(SLICERS, "orca", exe)
    monkeypatch.setenv("HOME", str(tmp_path))
    r = slice_project(copied_project(tmp_path), "orca", tmp_path / "out")
    assert marker.exists(), "Packaged native profiles were incorrectly treated as absent"
    assert any(d["rule_id"] == "SLICE.PROFILE_CACHE" for d in r["diagnostics"])
    assert r["exit_code"] != 0, "An unverified slicer result must never pass"
