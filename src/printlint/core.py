import zipfile
from pathlib import Path

import trimesh
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .compliance import compliance
from .geometry import inspect_mesh
from .package import inspect_colors, read_package
from .policy import load_policy, validate_manifest
from .report import add, finish, new_report


def run(path, policy=None, manifest=None, strict=False, geometry=True):
    r = new_report()
    path = Path(path)
    try:
        p = load_policy(policy) if not isinstance(policy, dict) else policy
        validate_manifest(manifest)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if not geometry and path.suffix.lower() != ".3mf":
            raise ValueError("Color inspection requires a 3MF project")
        if path.suffix.lower() == ".3mf":
            try:
                data = read_package(path, r)
            except (
                ValueError,
                zipfile.BadZipFile,
                KeyError,
                IndexError,
                TypeError,
                ET.ParseError,
                DefusedXmlException,
            ) as e:
                # Invalid input is a validation error; infrastructure is handled outside package parsing.
                add(r, "PKG.INVALID", "error", str(e))
                return finish(r, strict)
            compliance(path, r)
            inspect_colors(data, p, r, manifest)
            if geometry:
                for m, o, pl, t in data["meshes"]:
                    inspect_mesh(m, p, r, o, pl, tool=t)
                for region in data["tool_regions"]:
                    t = region["tool"]
                    if (
                        0 <= t < len(p["tool_x_min_mm"])
                        and region["x_min_mm"] < p["tool_x_min_mm"][t] - 0.01
                    ):
                        add(
                            r,
                            "GEO.TOOL_AREA",
                            "error",
                            "Painted faces outside selected toolhead printable area",
                            region,
                            "Repaint or reposition within that toolhead printable area.",
                            object=region["object"],
                            plate=region["plate"],
                        )
        elif path.suffix.lower() == ".stl":
            try:
                m = trimesh.load_mesh(path, process=False)
            except Exception as e:
                add(r, "GEO.INVALID", "error", str(e))
                return finish(r, strict)
            if geometry:
                inspect_mesh(m, p, r, path.name, "1", check_position=False)
            r["plates"] = ["1"]
        else:
            raise ValueError("Supported inputs: STL and 3MF")
    except (OSError, ValueError, RuntimeError, TypeError, IndexError, KeyError) as e:
        r["execution_failure"] = True
        add(
            r,
            "EXEC.FAILURE",
            "error",
            str(e),
            action="Check input paths, policy and installed dependencies.",
        )
    return finish(r, strict)


def check(path, **kwargs):
    return run(path, **kwargs)


def colors(path, **kwargs):
    return run(path, geometry=False, **kwargs)
