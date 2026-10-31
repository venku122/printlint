import hashlib
import json
import subprocess
import sys
import zipfile

import numpy as np
import trimesh

from printlint.core import check, colors


def cube(path, extents=(10, 10, 10)):
    m = trimesh.creation.box(extents)
    m.apply_translation(np.array(extents) / 2)
    m.export(path)
    return m


def project(
    path,
    mesh=None,
    paint=None,
    extruder=1,
    transform="1 0 0 0 1 0 0 0 1 20 20 0",
    plates=None,
):
    m = mesh if mesh is not None else trimesh.creation.box((10, 10, 10))
    m = m.copy()
    m.apply_translation((5, 5, 5))
    v = "".join(f'<vertex x="{a}" y="{b}" z="{c}"/>' for a, b, c in m.vertices)
    ts = "".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"'
        + (f' paint_color="{paint}"' if paint else "")
        + "/>"
        for a, b, c in m.faces
    )
    data = f'<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources><object id="1" type="model"><mesh><vertices>{v}</vertices><triangles>{ts}</triangles></mesh></object></resources><build><item objectid="1" transform="{transform}"/></build></model>'
    cfg = {
        "printer_model": "Bambu Lab X2D",
        "printer_settings_id": "Bambu Lab X2D 0.4 nozzle",
        "nozzle_diameter": ["0.4", "0.4"],
        "filament_colour": ["#000000", "#FF0000"],
        "filament_type": ["PLA", "PLA"],
        "filament_settings_id": ["PLA", "PLA"],
        "filament_extruder": ["0", "0"],
    }
    settings = (
        f'<config><object id="1"><metadata key="extruder" value="{extruder}"/></object>'
        + (
            plates
            or '<plate><metadata key="plater_id" value="1"/><model_instance><metadata key="object_id" value="1"/><metadata key="instance_id" value="0"/></model_instance></plate>'
        )
        + "</config>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
        )
        z.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>',
        )
        z.writestr("3D/3dmodel.model", data)
        z.writestr("Metadata/project_settings.config", json.dumps(cfg))
        z.writestr("Metadata/model_settings.config", settings)
    return path


def rules(r):
    return {d["rule_id"] for d in r["diagnostics"]}


def test_cube(tmp_path):
    p = tmp_path / "cube.stl"
    cube(p)
    r = check(p)
    assert r["exit_code"] == 0
    assert r["geometry"][0]["watertight"]
    assert r["geometry"][0]["dimensions_mm"] == [10, 10, 10]


def test_hole_and_nonmanifold(tmp_path):
    p = tmp_path / "bad.stl"
    m = cube(p)
    m.update_faces(np.arange(len(m.faces)) != 0)
    m.export(p)
    assert "GEO.OPEN" in rules(check(p))
    m = cube(p)
    m.faces = np.vstack([m.faces, m.faces[0]])
    m.export(p)
    assert "GEO.NONMANIFOLD" in rules(check(p))
    assert check(p)["exit_code"] == 1


def test_thin_and_oversize(tmp_path):
    p = tmp_path / "thin.stl"
    cube(p, (0.3, 10, 10))
    assert "GEO.THIN" in rules(check(p))
    cube(p, (300, 10, 10))
    assert check(p)["exit_code"] == 1
    assert "GEO.ENVELOPE" in rules(check(p))


def test_painted_readonly_and_unknown_ams(tmp_path):
    p = project(tmp_path / "paint.3mf", paint="8")
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    r = colors(p)
    assert r["colors"]["painted_triangles"] == 12
    assert r["colors"]["physical_ams"] == "unverified"
    assert 2 in r["colors"]["used_filaments"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == before


def test_bad_filament(tmp_path):
    p = project(tmp_path / "bad.3mf", extruder=9)
    assert "COLOR.REFERENCE" in rules(colors(p))
    assert colors(p)["exit_code"] == 1


def test_transform_floating_and_bounds(tmp_path):
    p = project(tmp_path / "float.3mf", transform="1 0 0 0 1 0 0 0 1 250 20 10")
    r = check(p)
    assert "GEO.ENVELOPE" in rules(r)
    assert "GEO.FLOATING" in rules(r)
    assert r["geometry"][0]["bounds_mm"][0] == [250, 20, 10]


def test_multiple_plates(tmp_path):
    ps = "".join(
        f'<plate><metadata key="plater_id" value="{i}"/><model_instance><metadata key="object_id" value="1"/><metadata key="instance_id" value="0"/></model_instance></plate>'
        for i in (1, 2)
    )
    r = check(project(tmp_path / "multi.3mf", plates=ps))
    assert r["plates"] == ["1", "2"]
    assert {g["plate"] for g in r["geometry"]} == {"1", "2"}


def test_invalid_package(tmp_path):
    p = tmp_path / "broken.3mf"
    p.write_bytes(b"bad")
    assert check(p)["exit_code"] == 1
    assert "PKG.INVALID" in rules(check(p))


def test_cli_json_and_codes(tmp_path):
    p = tmp_path / "cube.stl"
    cube(p)
    r = subprocess.run(
        [sys.executable, "-m", "printlint", "check", str(p), "--json"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["exit_code"] == 0
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "printlint",
            "check",
            str(tmp_path / "absent.stl"),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert json.loads(r.stdout)["exit_code"] == 2


def test_tool_manifest(tmp_path):
    p = project(tmp_path / "tool.3mf")
    manifest = {
        "filaments": [
            {
                "index": 1,
                "color": "#FFFFFF",
                "material": "PETG",
                "tool": 3,
                "ams_slot": "A1",
            }
        ]
    }
    r = colors(p, manifest=manifest)
    assert {"COLOR.PALETTE", "COLOR.MATERIAL", "COLOR.TOOL"} <= rules(r)
    assert r["exit_code"] == 1


def test_vendor_plate_origin_normalization(tmp_path):
    # Standard 2-plate layout has ceil(sqrt(2))=2 columns and 1.2*256 stride.
    p = project(
        tmp_path / "multi2.3mf",
        transform="1 0 0 0 1 0 0 0 1 320 20 0",
        plates='<plate><metadata key="plater_id" value="1"/></plate><plate><metadata key="plater_id" value="2"/><model_instance><metadata key="object_id" value="1"/><metadata key="instance_id" value="0"/></model_instance></plate>',
    )
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    mem["3D/3dmodel.model"] = mem["3D/3dmodel.model"].replace(
        b"<resources>",
        b'<metadata name="Application">OrcaSlicer-2.5.0</metadata><resources>',
    )
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    r = check(p)
    assert "GEO.ENVELOPE" not in rules(r)
    assert r["geometry"][0]["bounds_mm"][0][0] == 12.8


def test_valid_benchy():
    from printlint.policy import ROOT

    r = check(ROOT / "tests/fixtures/3DBenchy.stl")
    assert r["exit_code"] == 0
    assert r["geometry"][0]["faces"] > 100000


def test_deterministic_report(tmp_path):
    p = tmp_path / "cube.stl"
    cube(p, (0.4, 10, 10))
    assert check(p) == check(p)


def test_sarif_and_strict(tmp_path):
    p = tmp_path / "thin.stl"
    cube(p, (0.3, 10, 10))
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "printlint",
            "check",
            str(p),
            "--strict",
            "--format",
            "sarif",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert json.loads(r.stdout)["version"] == "2.1.0"


def test_centimeter_build_transform(tmp_path):
    p = project(tmp_path / "units.3mf", transform="1 0 0 0 1 0 0 0 1 2 2 0")
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    mem["3D/3dmodel.model"] = mem["3D/3dmodel.model"].replace(
        b'unit="millimeter"', b'unit="centimeter"'
    )
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    r = check(p)
    assert r["geometry"][0]["bounds_mm"][0] == [20, 20, 0]


def test_manifest_error_is_json(tmp_path):
    p = tmp_path / "cube.stl"
    cube(p)
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "printlint",
            "check",
            str(p),
            "--manifest",
            str(bad),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert json.loads(r.stdout)["exit_code"] == 2


def test_colors_requires_project(tmp_path):
    p = tmp_path / "cube.stl"
    cube(p)
    assert colors(p)["exit_code"] == 2


def test_real_tool_mapping(tmp_path):
    p = project(tmp_path / "tool.3mf")
    with zipfile.ZipFile(p) as z:
        mem = {n: z.read(n) for n in z.namelist()}
    cfg = json.loads(mem["Metadata/project_settings.config"])
    cfg.pop("filament_extruder")
    cfg["filament_map"] = ["3", "1"]
    mem["Metadata/project_settings.config"] = json.dumps(cfg).encode()
    with zipfile.ZipFile(p, "w") as z:
        for n, d in mem.items():
            z.writestr(n, d)
    assert "COLOR.TOOL" in rules(colors(p))
