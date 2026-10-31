from printlint.policy import load_policy
from printlint.report import new_report
from printlint.statistics import inspect_statistics, parse_gcode


def test_bambu_gcode_statistics():
    text = "; estimated printing time (normal mode) = 1h 2m 3s\n; filament used [g] = 12.4, 2.0\n; filament used [mm] = 4000, 700\n; total filament change = 12\n"
    r = parse_gcode(text, "bambu")
    assert r["estimated_time_seconds"] == 3723
    assert r["filament_g"] == [12.4, 2.0]
    assert r["filament_changes"] == 12


def test_purge_actual_statistics():
    r = new_report()
    inspect_statistics(
        {"filament_changes": 600, "model_volume_mm3": 1000, "purge_volume_mm3": 2100},
        load_policy(),
        r,
    )
    assert {d["rule_id"] for d in r["diagnostics"]} == {"SLICE.PURGE", "SLICE.CHANGES"}


def test_missing_statistics_unknown():
    r = parse_gcode("; hello", "orca")
    assert r["estimated_time_seconds"] is None
    assert r["filament_changes"] is None


def test_bambu_actual_header():
    text = "; model printing time: 4m 10s; total estimated time: 9m 19s\n; total filament length [mm] : 239.43\n; total filament weight [g] : 0.73\n"
    r = parse_gcode(text, "bambu")
    assert r["estimated_time_seconds"] == 559
    assert r["filament_g"] == [0.73]


def test_profile_fallback_rejected(tmp_path):
    from test_core import project

    from printlint.slicer import slice_project

    r = slice_project(project(tmp_path / "generic.3mf"), "bambu", tmp_path / "out")
    assert r["exit_code"] == 1
    assert "SLICE.PROFILE" in {d["rule_id"] for d in r["diagnostics"]}


def test_orca_statistics_schema():
    import json

    from printlint.policy import ROOT
    from printlint.slicer import orca_statistics

    d = json.loads((ROOT / "tests/fixtures/statistics/orca-cube.json").read_text())
    r = orca_statistics(d)
    assert r["filament_changes"] == 0
    assert r["layer_count"] == 50
    assert len(r["layers"]) == 50
    assert r["objects"]


def test_real_high_purge_statistics_warn():
    import json

    from printlint.policy import ROOT
    from printlint.slicer import orca_statistics

    raw = json.loads((ROOT / "tests/fixtures/statistics/orca-highpurge.json").read_text())
    stats = orca_statistics(raw)
    r = new_report()
    inspect_statistics(stats, load_policy(), r)
    assert stats["filament_changes"] == 50
    assert stats["purge_volume_mm3"] > 19000
    assert "SLICE.PURGE" in {d["rule_id"] for d in r["diagnostics"]}
