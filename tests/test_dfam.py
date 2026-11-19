import json

from printlint.cli import main

HEADER = """; BambuStudio test fixture
; CONFIG_BLOCK_START
; printer_model = Bambu Lab X2D
; wall_generator = arachne
; outer_wall_line_width = 0.42
; filament_diameter = 1.75
; CONFIG_BLOCK_END
; EXECUTABLE_BLOCK_START
G90
M83
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; LAYER_HEIGHT: 0.2
G1 X10 Y10 Z0.2
"""
END = "; EXECUTABLE_BLOCK_END\n"


def audit(tmp_path, capsys, moves, spec=None, fmt="json", extra=()):
    import hashlib

    gcode = tmp_path / "plate_1.gcode"
    gcode.write_text(HEADER + moves + END)
    args = ["dfam", str(gcode), "--format", fmt, *extra]
    if spec is not None:
        settings = tmp_path / "features.json"
        settings.write_text(
            json.dumps(
                {
                    "input_sha256": hashlib.sha256(gcode.read_bytes()).hexdigest(),
                    "source": "Synthetic CAD witness coordinates",
                    "features": spec,
                }
            )
        )
        args.extend(["--dfam-spec", str(settings)])
    code = main(args)
    return code, json.loads(capsys.readouterr().out)


def feature(**overrides):
    return {
        "name": "hinge lip",
        "plate": "1",
        "critical": True,
        "points_mm": [[11, 10, 0.2], [13, 10, 0.2]],
        **overrides,
    }


def findings(result, rule):
    return [d for d in result["diagnostics"] if d["rule_id"] == rule]


def test_critical_feature_missing_with_travel_support_and_commented_motion(tmp_path, capsys):
    code, result = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G1 X12 E0.06
; G1 X14 E0.08
G1 X14
; FEATURE: Support
G1 X12 E0.06
""",
        [feature()],
    )
    [finding] = findings(result, "DFAM-14")
    assert code == 1
    assert finding["status"] == "WARN"
    assert finding["severity"] == "error"
    assert finding["affected_geometry"]["name"] == "hinge lip"
    assert finding["evidence"]["unmet_points_mm"] == [[13, 10, 0.2]]
    assert findings(result, "DFAM-12")[0]["status"] == "UNVERIFIED"


def test_audit_sarif_contains_path_evidence(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G1 X14 E0.14
""",
        [feature()],
        fmt="sarif",
    )
    [result] = [r for r in report["runs"][0]["results"] if r["ruleId"] == "DFAM-14"]
    assert code == 0
    assert result["properties"]["status"] == "PASS"
    assert result["properties"]["evidence"]["scope"] == "nominal_toolpath"


def test_missing_layer_and_unsupported_positive_arc_are_unverified(tmp_path, capsys):
    code, result = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G2 X14 Y10 I2 J0 E0.14
""",
        [feature()],
    )
    assert code == 1
    assert findings(result, "DFAM-14")[0]["status"] == "UNVERIFIED"


def test_absolute_e_retraction_and_bridge_roles(tmp_path, capsys):
    code, result = audit(
        tmp_path,
        capsys,
        """
M82
G92 E10
; FEATURE: Bridge
G1 E9.8
G1 X12 E10
G1 X14 E10.12
""",
        [feature(critical=False)],
    )
    assert code == 0
    assert findings(result, "DFAM-14")[0]["evidence"]["unmet_points_mm"] == [[11, 10, 0.2]]
    assert findings(result, "DFAM-04")[0]["evidence"]["roles"]["bridge"]["longest_run_mm"] == 2


def test_clearance_probe_and_risk_record(tmp_path, capsys):
    code, result = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G1 X14 E0.14
""",
        [
            feature(
                expect="clear",
                accepted_risk={
                    "reason": "Owner accepted local interference for this coupon",
                    "evidence": "Decision record 123",
                },
            )
        ],
        extra=("--strict",),
    )
    assert code == 0
    [finding] = findings(result, "DFAM-14")
    assert finding["status"] == "ACCEPTED_RISK"
    assert finding["evidence"]["original_status"] == "WARN"


def test_spec_cannot_be_reused_after_reslice(tmp_path, capsys):
    audit(tmp_path, capsys, "; FEATURE: Outer wall\nG1 X14 E0.14\n", [feature()])
    gcode = tmp_path / "plate_1.gcode"
    gcode.write_text(gcode.read_text().replace("X14", "X12"))
    assert main(["dfam", str(gcode), "--dfam-spec", str(tmp_path / "features.json"), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["rule_id"] == "EXEC.DFAM"


def test_wall_nominal_and_actual_width_evidence(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        "; FEATURE: Outer wall\nG1 X14 E0.14\n",
        [
            feature(rule_id="DFAM-02", wall_thickness_mm=0.392),
        ],
    )
    (wall,) = [d for d in findings(report, "DFAM-02") if d["object"] == "hinge lip"]
    assert code == 0
    assert wall["status"] == "PASS"
    assert wall["evidence"]["configured_outer_line_width_mm"] == 0.42
    assert wall["evidence"]["wall_thickness_mm"] == 0.392
    assert wall["evidence"]["local_equivalent_width_range_mm"][0] > 0.4


def test_minimum_gap_uses_actual_model_paths(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        "; FEATURE: Outer wall\nG1 X14 E0.14\n",
        [
            feature(rule_id="DFAM-03", expect="clear"),
        ],
    )
    [gap] = findings(report, "DFAM-03")
    assert code == 1
    assert gap["evidence"]["unmet_points_mm"] == [[11, 10, 0.2], [13, 10, 0.2]]


def test_support_in_reviewed_removal_corridor(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G1 X12 E0.07
; FEATURE: Support interface
G1 X14 E0.07
""",
        [feature(rule_id="DFAM-12", expect="support_clear")],
    )
    (access,) = [d for d in findings(report, "DFAM-12") if d["object"] == "hinge lip"]
    assert code == 1
    assert access["evidence"]["unmet_points_mm"] == [[13, 10, 0.2]]


def test_mesh_findings_opt_in(tmp_path, capsys):
    import trimesh

    thin = tmp_path / "wall.stl"
    trimesh.creation.box(extents=(0.2, 10, 10)).export(thin)
    assert main(["check", str(thin), "--dfam", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert findings(report, "DFAM-02")[0]["status"] == "UNVERIFIED"
    assert findings(report, "DFAM-03")[0]["status"] == "WARN"
    assert "GEO.THIN" in {d["rule_id"] for d in report["diagnostics"]}
    assert main(["check", str(thin), "--json"]) == 0
    assert not findings(json.loads(capsys.readouterr().out), "DFAM-03")


def test_missing_requested_plate_blocks_critical_witness(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        "; FEATURE: Outer wall\nG1 X14 E0.14\n",
        [
            feature(plate="2"),
        ],
    )
    assert code == 1
    (missing,) = [d for d in findings(report, "DFAM-14") if d["plate"] == "2"]
    assert missing["status"] == "UNVERIFIED"


def test_non_target_arc_does_not_hide_known_missing_feature(tmp_path, capsys):
    code, report = audit(
        tmp_path,
        capsys,
        """
; FEATURE: Outer wall
G1 X11.5 E0.08
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; LAYER_HEIGHT: 0.2
G1 Z0.4
; FEATURE: Outer wall
G2 X14 Y10 I1.25 J0 E0.14
""",
        [feature()],
    )
    [missing] = findings(report, "DFAM-14")
    assert code == 1
    assert missing["status"] == "WARN"
    assert missing["evidence"]["layers_with_parse_limits"] == [0.4]


def test_sliced_archive_matches_member_and_payload_hash(tmp_path, capsys):
    import hashlib
    import zipfile

    path = tmp_path / "sliced.3mf"
    payload = (HEADER + "; FEATURE: Outer wall\nG1 X14 E0.14\n" + END).encode()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Metadata/plate_2.gcode", payload)
    assert main(["dfam", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    [finding] = findings(report, "DFAM-14")
    assert finding["plate"] == "2"
    assert finding["status"] == "UNVERIFIED"
    assert finding["evidence"]["member"] == "Metadata/plate_2.gcode"
    assert finding["evidence"]["gcode_sha256"] == hashlib.sha256(payload).hexdigest()


def test_slice_option_keeps_static_gate_and_inspects_emitted_gcode(tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    from printlint import slicer
    from printlint.policy import ROOT

    launcher = tmp_path / "bambu"
    launcher.touch()
    monkeypatch.setitem(slicer.SLICERS, "bambu", launcher)
    monkeypatch.setattr(slicer, "verify_profile", lambda cfg, text, report: {})

    def fake_slice(command, cwd, **kwargs):
        preflight = json.loads((cwd / "preflight.json").read_text())
        assert findings(preflight, "DFAM-03")
        assert preflight["exit_code"] == 0
        assert Path(command[-1]) == cwd / "input.3mf"
        (cwd / "plate_1.gcode").write_text(HEADER + "; FEATURE: Bridge\nG1 X14 E0.14\n" + END)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(
        slicer, "subprocess", SimpleNamespace(run=fake_slice, TimeoutExpired=TimeoutError)
    )
    result = slicer.slice_project(
        ROOT / "tests/fixtures/x2d-cube.3mf", "bambu", tmp_path / "slice", dfam=True
    )
    assert result["exit_code"] == 0
    assert any(
        d["status"] == "WARN" and d["evidence"]["scope"] == "nominal_toolpath"
        for d in findings(result, "DFAM-04")
    )
    assert findings(result, "DFAM-14")[0]["status"] == "UNVERIFIED"
