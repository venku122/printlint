"""Bounded OPC/3MF reader with production-extension component transforms."""

import json
import math
import posixpath
import zipfile
from collections import Counter

import numpy as np
import trimesh
from codec import tokenize_segmentation
from defusedxml import ElementTree as ET

from .report import add

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
UNITS = {
    "micron": 0.001,
    "millimeter": 1,
    "centimeter": 10,
    "inch": 25.4,
    "foot": 304.8,
    "meter": 1000,
}


def local(s):
    return s.rsplit("}", 1)[-1]


def children(e, n):
    return [x for x in e if local(x.tag) == n]


def attr(e, n, default=None):
    return next((v for k, v in e.attrib.items() if local(k) == n), default)


def metadata(e):
    return {x.get("key"): x.get("value", x.text or "") for x in children(e, "metadata")}


def matrix(s):
    if not s:
        return np.eye(4)
    a = np.array([float(v) for v in s.split()])
    if len(a) != 12 or not np.isfinite(a).all():
        raise ValueError("Invalid 3MF transform")
    m = np.eye(4)
    m[:3, :] = a.reshape(4, 3).T
    return m


def read_package(path, report):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        if len(names) > 10000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
            raise ValueError("Package exceeds safety limits (10000 members / 512 MiB uncompressed)")
        if any(i.file_size > 128 * 1024 * 1024 for i in infos):
            raise ValueError("Package member exceeds 128 MiB limit")
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise ValueError("Unsafe ZIP member path")
        bad = z.testzip()
        if bad:
            raise ValueError("ZIP CRC error")
        for n in ("[Content_Types].xml", "_rels/.rels"):
            if n not in names:
                raise ValueError("Missing required OPC resource " + n)
        ET.fromstring(z.read("[Content_Types].xml"))
        rels = ET.fromstring(z.read("_rels/.rels"))
        roots = [
            x.get("Target", "").lstrip("/") for x in rels if x.get("Type", "").endswith("/3dmodel")
        ]
        if len(roots) != 1 or roots[0] not in names:
            raise ValueError("Missing or ambiguous 3D model relationship")
        rootpath = roots[0]
        models = {n: ET.fromstring(z.read(n)) for n in names if n.endswith(".model")}
        cfg = (
            json.loads(z.read("Metadata/project_settings.config"))
            if "Metadata/project_settings.config" in names
            else {}
        )
        settings = (
            ET.fromstring(z.read("Metadata/model_settings.config"))
            if "Metadata/model_settings.config" in names
            else ET.fromstring("<config/>")
        )
    objects = {}
    paint = Counter()
    painted = 0
    opaque = 0
    assignments = []
    standard = []
    for name, model in models.items():
        if model.get("unit", "millimeter") not in UNITS:
            raise ValueError("Unsupported model unit")
        resources = next(iter(children(model, "resources")), [])
        ids = set()
        for e in resources:
            eid = e.get("id")
            if eid in ids:
                raise ValueError("Duplicate resource ID " + str(eid))
            ids.add(eid)
            if local(e.tag) in ("basematerials", "colorgroup"):
                standard.append(
                    {
                        "part": name,
                        "id": eid,
                        "type": local(e.tag),
                        "entries": [dict(x.attrib) for x in e],
                    }
                )
            if local(e.tag) == "object":
                objects[(name, eid)] = e
                for t in e.iter():
                    value = attr(t, "paint_color") or attr(t, "mmu_segmentation")
                    if value:
                        painted += 1
                        tokens = tokenize_segmentation(value)
                        if tokens:
                            paint.update(x[0] for x in tokens)
                        else:
                            opaque += 1
                    if local(t.tag) == "triangle" and t.get("pid"):
                        pid = t.get("pid")
                        res = next((v for v in resources if v.get("id") == pid), None)
                        indices = [
                            int(t.get(k, "0")) for k in ("p1", "p2", "p3") if t.get(k) is not None
                        ]
                        if res is None or any(i < 0 or i >= len(res) for i in indices):
                            add(
                                report,
                                "COLOR.CORE_REFERENCE",
                                "error",
                                "Invalid standard 3MF property reference",
                                {"pid": pid, "indices": indices},
                                object=eid,
                            )
    object_extruders = {}
    part_extruders = {}
    for o in children(settings, "object"):
        md = metadata(o)
        for e, kind in [(o, "object")] + [(p, "volume") for p in children(o, "part")]:
            d = metadata(e)
            if "extruder" in d:
                ex = int(d["extruder"])
                assignments.append(
                    {
                        "object": o.get("id"),
                        "part": e.get("id"),
                        "kind": kind,
                        "filament": ex,
                    }
                )
                if kind == "volume":
                    part_extruders[(o.get("id"), e.get("id"))] = ex
                if kind == "object":
                    object_extruders[o.get("id")] = ex
    plates = {}
    members = {}
    for idx, pl in enumerate(children(settings, "plate")):
        md = metadata(pl)
        pid = md.get("plater_id", str(idx + 1))
        plates[pid] = md
        for inst in children(pl, "model_instance"):
            d = metadata(inst)
            members.setdefault((d.get("object_id"), int(d.get("instance_id", "0"))), []).append(pid)
    report["plates"] = sorted(plates) or ["1"]
    build = next(iter(children(models[rootpath], "build")), [])
    instances = Counter()
    meshes = []
    tool_regions = []
    budget = {"nodes": 0, "meshes": 0, "triangles": 0}
    filament_tools = (
        [int(v) - 1 for v in cfg["filament_map"]]
        if cfg.get("filament_map")
        else [int(v) for v in cfg.get("filament_extruder", [])]
    )

    def tool_for(ex, fallback):
        return filament_tools[ex - 1] if 0 < ex <= len(filament_tools) else fallback

    def walk(name, oid, m, stack, label, plate, tool, depth=0):
        budget["nodes"] += 1
        if budget["nodes"] > 4096:
            raise ValueError("Expanded component node budget exceeded")
        key = (name, oid)
        if key in stack or depth > 64:
            raise ValueError("Cyclic or excessively deep component graph")
        if key not in objects:
            raise ValueError("Unresolved object reference " + str(key))
        o = objects[key]
        scale = UNITS[models[name].get("unit", "millimeter")]
        for mesh in children(o, "mesh"):
            vs = next(iter(children(mesh, "vertices")), [])
            ts = next(iter(children(mesh, "triangles")), [])
            budget["meshes"] += 1
            budget["triangles"] += len(ts)
            if budget["meshes"] > 1024 or budget["triangles"] > 2000000:
                raise ValueError(
                    "Expanded geometry budget exceeded (1024 meshes / 2 million triangles)"
                )
            root_oid = stack[0][1] if stack else oid
            tool = tool_for(part_extruders.get((root_oid, oid), 0), tool)
            v = np.array([[float(x.get(a, "nan")) for a in ("x", "y", "z")] for x in vs])
            f = np.array([[int(x.get(a, "-1")) for a in ("v1", "v2", "v3")] for x in ts])
            if v.size == 0 or f.size == 0:
                raise ValueError("Empty geometry")
            if not np.isfinite(v).all() or f.min() < 0 or f.max() >= len(v):
                raise ValueError("Invalid mesh vertices/indices")
            v = v * scale
            world = trimesh.transform_points(v, m)
            painted_tools = {}
            for face_idx, tri in enumerate(ts):
                val = attr(tri, "paint_color") or attr(tri, "mmu_segmentation")
                if val:
                    for ex, _ in tokenize_segmentation(val):
                        pt = tool_for(ex, -1)
                        if pt >= 0:
                            painted_tools.setdefault(pt, []).append(face_idx)
            for pt, faces in painted_tools.items():
                tool_regions.append(
                    {
                        "object": label + "/" + oid,
                        "plate": plate,
                        "tool": pt,
                        "x_min_mm": float(world[f[faces].ravel(), 0].min()),
                    }
                )
            fm = f[:, ::-1] if np.linalg.det(m[:3, :3]) < 0 else f
            meshes.append(
                (
                    trimesh.Trimesh(world, fm, process=False),
                    label + "/" + oid,
                    plate,
                    tool,
                )
            )
        for cs in children(o, "components"):
            for c in cs:
                target = attr(c, "path", name)
                if target.startswith("/"):
                    target = target.lstrip("/")
                elif target != name:
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                cm = matrix(c.get("transform"))
                cm[:3, 3] *= scale
                walk(
                    target,
                    c.get("objectid"),
                    m @ cm,
                    stack + (key,),
                    label,
                    plate,
                    tool,
                    depth + 1,
                )

    for i, it in enumerate(build):
        oid = it.get("objectid")
        ii = instances[oid]
        instances[oid] += 1
        if it.get("printable", "1") == "0":
            add(
                report,
                "PKG.NONPRINTING",
                "information",
                "Non-printable build item omitted from geometry checks",
                object=oid,
            )
            continue
        for pl in members.get((oid, ii), ["1"]):
            m = matrix(it.get("transform"))
            m[:3, 3] *= UNITS[models[rootpath].get("unit", "millimeter")]
            # Verified upstream PartPlateList uses ceil(sqrt(count)) columns and 20% gap.
            md = plates.get(pl, {})
            if "plate_origin" in md:
                origin = np.array([float(v) for v in md["plate_origin"].split()])
                m[:3, 3] -= origin
            elif len(plates) > 1 and any(
                "BambuStudio" in x.text or "OrcaSlicer" in x.text
                for x in children(models[rootpath], "metadata")
                if x.text
            ):
                cols = math.ceil(math.sqrt(len(plates)))
                idx = list(plates).index(pl)
                area = cfg.get("printable_area", ["0x0", "256x0", "256x256", "0x256"])
                pts = np.array([[float(c) for c in v.strip().split("x")] for v in area])
                size = np.ptp(pts, axis=0)
                m[:3, 3] -= np.array(
                    [(idx % cols) * size[0] * 1.2, -(idx // cols) * size[1] * 1.2, 0]
                )
            tool = 0
            ex = object_extruders.get(oid, 1)
            fs = (
                [int(v) - 1 for v in cfg["filament_map"]]
                if cfg.get("filament_map")
                else cfg.get("filament_extruder", [])
            )
            if ex > 0 and ex <= len(fs):
                tool = int(fs[ex - 1])
            walk(rootpath, oid, m, (), f"build:{i}", pl, tool)
    if not meshes:
        raise ValueError("No printable build geometry")
    return {
        "config": cfg,
        "tool_regions": tool_regions,
        "meshes": meshes,
        "painted_triangles": painted,
        "paint_counts": dict(sorted(paint.items())),
        "opaque_painted_triangles": opaque,
        "assignments": assignments,
        "standard_properties": standard,
        "objects": len(objects),
    }


def inspect_colors(data, policy, report, manifest=None):
    cfg = data["config"]
    palette = cfg.get("filament_colour", [])
    types = cfg.get("filament_type", [])
    tools = (
        [int(v) - 1 for v in cfg["filament_map"]]
        if cfg.get("filament_map")
        else cfg.get("filament_extruder", [])
    )
    used = set(data["paint_counts"]) | {
        a["filament"] for a in data["assignments"] if a["filament"] > 0
    }
    if not used and palette:
        used = {1}
    for i in sorted(used):
        if i < 1 or i > len(palette):
            add(
                report,
                "COLOR.REFERENCE",
                "error",
                "Filament assignment outside project palette",
                i,
                "Correct the assignment or add the intended filament.",
            )
    if data["opaque_painted_triangles"]:
        add(
            report,
            "COLOR.OPAQUE_PAINT",
            "warning",
            "Split-triangle paint cannot be decoded reliably by the installed community codec",
            data["opaque_painted_triangles"],
            "Inspect painted regions in Bambu/Orca; do not infer missing colors from incomplete decoding.",
        )
    unused = sorted(set(range(1, len(palette) + 1)) - used)
    if unused:
        add(
            report,
            "COLOR.UNUSED",
            "information",
            "Configured filaments with no known assignment",
            unused,
            "Remove only if confirmed unused in the slicer, including opaque painting.",
        )
    for i, t in enumerate(tools):
        if int(t) < 0 or int(t) >= len(policy["nozzles_mm"]):
            add(
                report,
                "COLOR.TOOL",
                "error",
                "Project filament assigned to unavailable toolhead",
                {"filament": i + 1, "tool": t},
                "Select a valid toolhead.",
            )
    physical = "unverified"
    if manifest:
        physical = "explicit_manifest_not_live_verified"
        for f in manifest.get("filaments", []):
            i = int(f["index"]) - 1
            if i < 0 or i >= len(palette):
                add(
                    report,
                    "COLOR.MANIFEST_REFERENCE",
                    "error",
                    "Manifest filament absent from project",
                    i + 1,
                )
                continue
            if f.get("color", "").upper() != palette[i].upper():
                add(
                    report,
                    "COLOR.PALETTE",
                    "warning",
                    "Manifest color differs from project",
                    {"index": i + 1, "expected": f.get("color"), "project": palette[i]},
                    "Check intended appearance and physical spool color.",
                )
            if f.get("material") and (i >= len(types) or f["material"] != types[i]):
                add(
                    report,
                    "COLOR.MATERIAL",
                    "error",
                    "Manifest material differs from project",
                    i + 1,
                    "Use compatible material settings and confirm the spool.",
                )
            t = f.get("tool")
            if t is not None and (
                t < 0 or t >= len(policy["nozzles_mm"]) or (i < len(tools) and t != int(tools[i]))
            ):
                add(
                    report,
                    "COLOR.TOOL",
                    "error",
                    "Manifest toolhead is unavailable or conflicts with the project",
                    t,
                    "Correct the tool assignment; tool numbers are zero-based.",
                )
    add(
        report,
        "COLOR.AMS",
        "information",
        "Physical AMS matching is " + physical,
        None,
        "Confirm loaded physical spools before manual printing; a project does not prove AMS contents.",
    )
    report["colors"] = {
        k: data[k]
        for k in (
            "painted_triangles",
            "paint_counts",
            "opaque_painted_triangles",
            "assignments",
            "standard_properties",
        )
    }
    report["colors"]["declared_manifest"] = manifest
    report["colors"].update(
        palette=palette,
        materials=types,
        tools=tools,
        used_filaments=sorted(used),
        unused_filaments=unused,
        physical_ams=physical,
        artistic_correctness="unverified",
    )
