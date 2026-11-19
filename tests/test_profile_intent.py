import json
import zipfile

from printlint.cli import main
from printlint.policy import ROOT
from printlint.slicer import SLICERS

FIXTURE = ROOT / "tests/fixtures/x2d-cube.3mf"
CONFIG = "Metadata/project_settings.config"


def project(tmp_path, name, bottom, gcode=None):
    path = tmp_path / name
    with zipfile.ZipFile(FIXTURE) as source, zipfile.ZipFile(path, "w") as out:
        for member in source.infolist():
            data = source.read(member)
            if member.filename == CONFIG:
                cfg = json.loads(data)
                cfg.update(bottom_shell_layers=str(bottom), top_surface_speed=["75", "200"])
                data = json.dumps(cfg)
            out.writestr(member.filename, data)
        if gcode is not None:
            out.writestr("Metadata/plate_1.gcode", gcode)
    return path


def expectations(tmp_path):
    spec = tmp_path / "expected.json"
    spec.write_text('{"bottom_shell_layers": 5, "top_surface_speed": [75]}')
    return spec


def test_wrong_job_input_blocks_before_slicer_launch(tmp_path, monkeypatch, capsys):
    path = project(tmp_path, "three.3mf", 3)
    marker = tmp_path / "launched"
    executable = tmp_path / "slicer"
    executable.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
    executable.chmod(0o755)
    monkeypatch.setitem(SLICERS, "bambu", executable)
    destination = tmp_path / "slice"
    assert (
        main(
            [
                "slice",
                str(path),
                "--slicer",
                "bambu",
                "--output",
                str(destination),
                "--expect-profile",
                str(expectations(tmp_path)),
                "--json",
            ]
        )
        == 1
    )
    assert not marker.exists()
    checks = json.loads((destination / "preflight.json").read_text())["profile_expectations"]
    assert [(c["field"], c["status"]) for c in checks] == [
        ("bottom_shell_layers", "MISMATCH"),
        ("top_surface_speed", "PASS"),
    ]
    assert json.loads(capsys.readouterr().out)["exit_code"] == 1


def test_final_receipt_rejects_emitted_mismatch_even_when_project_is_correct(tmp_path, capsys):
    path = project(
        tmp_path,
        "wrong.gcode.3mf",
        5,
        "; bottom_shell_layers = 3\n; top_surface_speed = 75,200\nG1 X2\n",
    )
    report = tmp_path / "details.json"
    assert (
        main(
            [
                "inspect-final",
                str(path),
                "--expect-profile",
                str(expectations(tmp_path)),
                "--report",
                str(report),
                "--json",
            ]
        )
        == 1
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "BLOCKED"
    assert len(summary["artifact"]["sha256"]) == 64
    assert len(summary["plates"][0]["gcode_sha256"]) == 64
    findings = json.loads(report.read_text())["profile_expectations"]
    assert {c["stage"] for c in findings} == {"archive", "gcode"}
    assert [(c["stage"], c["field"]) for c in findings if c["status"] == "MISMATCH"] == [
        ("gcode", "bottom_shell_layers")
    ]


def test_final_receipt_accepts_matching_values_and_keeps_preview_pending(tmp_path, capsys):
    path = project(
        tmp_path,
        "good.gcode.3mf",
        5,
        "; bottom_shell_layers = 5\n; top_surface_speed = 75,200\nG1 X2\n",
    )
    assert (
        main(
            ["inspect-final", str(path), "--expect-profile", str(expectations(tmp_path)), "--json"]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "NEEDS_REVIEW"
    assert summary["review"]["native_preview"] == "UNVERIFIED"
    assert all(c["status"] == "PASS" for c in summary["profile_expectations"])


def test_native_export_uses_wrapper_only_when_every_plate_matches(tmp_path, capsys):
    gcode = "; bottom_shell_layers = 5\n; top_surface_speed = 75,200\nG1 X2\n"
    wrapper = project(tmp_path, "wrapper.3mf", 5, gcode)
    wrong_wrapper = project(tmp_path, "wrong-wrapper.3mf", 5, gcode + "G1 X3\n")
    native = tmp_path / "native.gcode.3mf"
    with zipfile.ZipFile(wrapper) as source, zipfile.ZipFile(native, "w") as out:
        for name in (CONFIG, "Metadata/plate_1.gcode"):
            out.writestr(name, source.read(name))
    args = [
        "inspect-final",
        str(native),
        "--expect-profile",
        str(expectations(tmp_path)),
        "--json",
        "--validation-3mf",
    ]
    assert main([*args, str(wrapper)]) == 0
    good = json.loads(capsys.readouterr().out)
    assert good["validation_artifact"]["gcode_matches"] is True
    assert good["artifact"]["sha256"] != good["validation_artifact"]["sha256"]
    assert main([*args, str(wrong_wrapper)]) == 1
    bad = json.loads(capsys.readouterr().out)
    assert bad["validation_artifact"]["gcode_matches"] is False
    assert "FINAL.VALIDATION_HASH" in bad["diagnostics"]
