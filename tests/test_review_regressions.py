import json
import zipfile

import pytest
from test_core import project, rules

from printlint.core import check, colors
from printlint.report import new_report
from printlint.slicer import log_severity, verify_profile


@pytest.mark.parametrize(
    "manifest", [[1], {"filaments": [{}]}, {"filaments": [{"index": 1, "tool": "1"}]}]
)
def test_bad_manifest_contract(tmp_path, manifest):
    r = colors(project(tmp_path / "m.3mf"), manifest=manifest)
    assert r["exit_code"] == 2
    assert "EXEC.FAILURE" in rules(r)


def test_changed_effective_profile_rejected():
    r = new_report()
    cfg = {
        "printer_model": "Bambu Lab X2D",
        "printer_settings_id": "X2D",
        "print_settings_id": "Standard",
        "nozzle_diameter": ["0.4", "0.4"],
        "layer_height": "0.2",
        "filament_type": ["PLA"],
    }
    text = "; printer_model = Bambu Lab X2D\n; printer_settings_id = X2D\n; print_settings_id = Standard\n; nozzle_diameter = 0.8,0.8\n; layer_height = 0.6\n; filament_type = ABS\n"
    verify_profile(cfg, text, r)
    assert len(r["diagnostics"]) == 3
    assert all(d["severity"] == "error" for d in r["diagnostics"])


@pytest.mark.parametrize(
    "line",
    [
        "[ERROR] parser failed",
        "fatal: crash",
        "got error when validate: bad",
        "run found error, exit",
    ],
)
def test_log_failure_case_independent(line):
    assert log_severity(line) == "error"


def test_component_budget(tmp_path):
    p = project(tmp_path / "dag.3mf")
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    s = mem["3D/3dmodel.model"].decode()
    cs = "".join(
        f'<object id="{i}" type="model"><components><component objectid="{i - 1}"/><component objectid="{i - 1}"/></components></object>'
        for i in range(2, 13)
    )
    s = s.replace("</resources>", cs + "</resources>").replace(
        '<item objectid="1"', '<item objectid="12"'
    )
    mem["3D/3dmodel.model"] = s.encode()
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    r = check(p)
    assert r["exit_code"] == 1
    assert "budget" in str(r["diagnostics"]).lower()


def test_part_tool_area(tmp_path):
    p = project(tmp_path / "parts.3mf", transform="1 0 0 0 1 0 0 0 1 10 20 0")
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    cfg = json.loads(mem["Metadata/project_settings.config"])
    cfg["filament_extruder"] = ["0", "1"]
    mem["Metadata/project_settings.config"] = json.dumps(cfg).encode()
    mem["Metadata/model_settings.config"] = mem["Metadata/model_settings.config"].replace(
        b"</object>", b'<part id="1"><metadata key="extruder" value="2"/></part></object>'
    )
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    assert "GEO.TOOL_AREA" in rules(check(p))


def test_paint_tool_area(tmp_path):
    p = project(tmp_path / "paint.3mf", paint="8", transform="1 0 0 0 1 0 0 0 1 10 20 0")
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    cfg = json.loads(mem["Metadata/project_settings.config"])
    cfg["filament_extruder"] = ["0", "1"]
    mem["Metadata/project_settings.config"] = json.dumps(cfg).encode()
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    assert "GEO.TOOL_AREA" in rules(check(p))
