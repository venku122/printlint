"""DfAM evidence for explicitly scoped critical geometry and slicer annotations."""

import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from .report import add, finish, new_report
from .statistics import parse_gcode
from .toolpaths import PROFILE_KEYS, SUPPORT, Toolpaths

PLATE = re.compile(r"(?:Metadata/)?plate_([1-9]\d*)\.gcode")
MAX_GCODE_BYTES = 128 * 1024 * 1024
CANONICAL = "https://github.com/venku122/printlint/blob/main/docs/dfam.md"


def finding(report, rule, status, geometry, reason, evidence, action, severity=None, plate=None):
    add(
        report,
        rule,
        severity or ("warning" if status == "WARN" else "information"),
        reason,
        action=action,
        object=geometry.get("name"),
        plate=plate,
    )
    report["diagnostics"][-1].update(
        status=status,
        affected_geometry=geometry,
        rationale=reason,
        evidence=evidence,
    )


def file_hash(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_spec(path, digest):
    if path is None:
        return []
    spec = json.loads(Path(path).read_text())
    if not isinstance(spec, dict) or spec.get("input_sha256") != digest:
        raise ValueError("DfAM spec input_sha256 must match the exact input bytes")
    source = spec.get("source")
    features = spec.get("features")
    if not isinstance(source, str) or not source.strip() or not isinstance(features, list):
        raise ValueError("DfAM spec requires source evidence and a features list")
    seen = set()
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("DfAM feature must be an object")
        name, plate = feature.get("name"), feature.get("plate")
        if not isinstance(name, str) or not name.strip() or not isinstance(plate, str):
            raise ValueError("DfAM feature requires name and string plate")
        if not re.fullmatch(r"[1-9]\d*", plate) or (plate, name) in seen:
            raise ValueError("DfAM features must have unique names on numbered plates")
        seen.add((plate, name))
        if type(feature.get("critical")) is not bool or feature.get("expect", "solid") not in (
            "solid",
            "clear",
            "support_clear",
        ):
            raise ValueError(
                "DfAM feature requires boolean critical and solid/clear/support_clear expectation"
            )
        rule = feature.get("rule_id", "DFAM-14")
        if rule not in ("DFAM-02", "DFAM-03", "DFAM-12", "DFAM-14"):
            raise ValueError("Unsupported DfAM witness rule")
        if (rule == "DFAM-12") != (feature.get("expect") == "support_clear"):
            raise ValueError("DFAM-12 witnesses require the support_clear expectation")
        thickness = feature.get("wall_thickness_mm")
        if thickness is not None and (
            rule != "DFAM-02" or type(thickness) not in (int, float) or not 0 < thickness <= 1e6
        ):
            raise ValueError("wall_thickness_mm must be a finite positive DFAM-02 measurement")
        points = feature.get("points_mm")
        if (
            not isinstance(points, list)
            or not points
            or not all(
                isinstance(p, list)
                and len(p) == 3
                and all(type(v) in (int, float) and abs(v) <= 1e6 for v in p)
                and p[2] > 0
                for p in points
            )
        ):
            raise ValueError("DfAM feature requires finite XYZ points_mm at positive model Z")
        risk = feature.get("accepted_risk")
        if risk is not None and (
            not isinstance(risk, dict)
            or not all(
                isinstance(risk.get(k), str) and risk[k].strip() for k in ("reason", "evidence")
            )
        ):
            raise ValueError("Accepted DfAM risk requires a reason and decision evidence")
    return [{**feature, "source": source} for feature in features]


def covered(point, segment):
    """Point inside a nominal rectangular bead with rounded ends."""
    x, y, _ = point
    sx, sy = segment.start
    dx, dy = segment.end[0] - sx, segment.end[1] - sy
    projection = ((x - sx) * dx + (y - sy) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, projection))
    return math.hypot(x - sx - t * dx, y - sy - t * dy) <= segment.width / 2


def inspect_plate(report, text, plate, features, identity):
    toolpaths = Toolpaths(text)
    points = defaultdict(set)
    for feature in features:
        support = feature.get("expect") == "support_clear"
        for point in feature["points_mm"]:
            points[support, round(point[2], 6)].add(tuple(point))
    hits = {}
    incomplete_widths = set()
    for segment in toolpaths.segments():
        layer = segment.role in SUPPORT, segment.z
        if layer not in points:
            continue
        if segment.width is None:
            incomplete_widths.add(layer)
            continue
        for point in points[layer]:
            key = layer[0], point
            if key not in hits and covered(point, segment):
                hits[key] = segment
    evidence = {
        **identity,
        "scope": "nominal_toolpath",
        "slicer_version": toolpaths.version,
        "profile": toolpaths.profile,
        "parse_limitations": dict(toolpaths.issues),
        "layers_with_parse_limits": sorted(toolpaths.layer_issues),
    }
    for feature in features:
        targets = [tuple(p) for p in feature["points_mm"]]
        solid = feature.get("expect", "solid") == "solid"
        support = feature.get("expect") == "support_clear"
        present = [p for p in targets if (support, p) in hits]
        unmet = [p for p in targets if ((support, p) in hits) != solid]
        layers = {round(p[2], 6) for p in targets}
        layer_issues = {
            z: dict(toolpaths.layer_issues[z]) for z in layers & toolpaths.layer_issues.keys()
        }
        if (
            toolpaths.issues
            or not toolpaths.model_layers
            or layer_issues
            or any((support, z) in incomplete_widths for z in layers)
        ):
            status, reason = "UNVERIFIED", "Incomplete executable path evidence for witness check."
        elif not layers <= (
            toolpaths.model_layers | toolpaths.support_layers if support else toolpaths.model_layers
        ):
            status, reason = "UNVERIFIED", "A witness Z has no matching annotated model layer."
        elif unmet:
            status = "WARN"
            reason = (
                "Expected model extrusion is missing at specified witnesses."
                if solid
                else "Support extrusion intersects specified removal corridor witnesses."
                if support
                else "Model extrusion intersects specified clearance witnesses."
            )
        else:
            status, reason = (
                "PASS",
                "All specified witnesses match the nominal toolpath expectation.",
            )
        local = [hits[support, p] for p in present]
        feature_evidence = {
            **evidence,
            "witness_layer_issues": layer_issues,
            "unmet_points_mm": unmet,
            "covered_points_mm": present,
            "example_gcode_lines": [s.line for s in local[:8]],
        }
        if "wall_thickness_mm" in feature:
            widths = [s.width for s in local]
            nominal = configured_outer_width(toolpaths.profile)
            feature_evidence.update(
                wall_thickness_mm=feature["wall_thickness_mm"],
                configured_outer_line_width_mm=nominal,
                local_equivalent_width_range_mm=[min(widths), max(widths)] if widths else None,
            )
        feature_result(report, feature, status, reason, feature_evidence)
    if not any(f.get("rule_id", "DFAM-14") != "DFAM-12" for f in features):
        finding(
            report,
            "DFAM-14",
            "UNVERIFIED",
            {},
            "No source witnesses supplied for this plate.",
            evidence,
            "Identify critical CAD features and inspect actual toolpaths or supply a spec.",
            plate=plate,
        )
    inspect_roles(report, plate, toolpaths, evidence)
    slicer = "orca" if "OrcaSlicer" in (toolpaths.version or "") else "bambu"
    stats = parse_gcode(text, slicer) if toolpaths.version else {}
    estimates = {
        k: stats[k]
        for k in ("estimated_time_seconds", "filament_g", "filament_changes")
        if stats.get(k) is not None
    }
    finding(
        report,
        "DFAM-15",
        "UNVERIFIED",
        {},
        "Native estimates describe this plate; efficiency requires comparison against another "
        "candidate with equivalent functional coverage.",
        {**identity, "scope": "slicer_estimate", "estimates": estimates},
        "Compare time, mass, support, purge, tool changes and finish when optimization is relevant.",
        plate=plate,
    )


def feature_result(report, feature, status, reason, evidence):
    action = (
        "Inspect CAD and the native preview at these XYZ coordinates; revise geometry or slice "
        "settings and recheck the exact output. Review the required physical test separately."
    )
    severity = None
    if status in {"WARN", "UNVERIFIED"}:
        if feature.get("accepted_risk"):
            evidence.update(original_status=status, accepted_risk=feature["accepted_risk"])
            status = "ACCEPTED_RISK"
        elif feature["critical"]:
            severity = "error"
        else:
            severity = "warning"
    finding(
        report,
        feature.get("rule_id", "DFAM-14"),
        status,
        {
            "name": feature["name"],
            "expect": feature.get("expect", "solid"),
            "points_mm": feature["points_mm"],
            "critical": feature["critical"],
        },
        reason,
        {**evidence, "source": feature["source"]},
        action,
        severity=severity,
        plate=feature["plate"],
    )


def configured_outer_width(profile):
    # Percent, multi-value and unset widths need slicer-specific resolution.
    for key in ("outer_wall_line_width", "line_width"):
        value = str(profile.get(key, "0")).strip()
        if not re.fullmatch(r"[0-9]*\.?[0-9]+", value):
            return None
        width = float(value)
        if math.isfinite(width) and width > 0:
            return width
    return None


def add_mesh_findings(report, policy, profile):
    """Reuse existing mesh sampling; compare only to documented configured heuristics."""
    profile = {key: value for key, value in profile.items() if key in PROFILE_KEYS}
    width = configured_outer_width(profile)
    mesh_flags = {
        (d["object"], d["plate"], d["rule_id"]): d["measured_value"]
        for d in report["diagnostics"]
        if d["rule_id"] in {"GEO.THIN", "GEO.OVERHANG"}
    }
    for mesh in report["geometry"]:
        geometry = {"name": mesh["object"], "bounds_mm": mesh["bounds_mm"]}
        plate = mesh["plate"]
        evidence = {
            "scope": "sampled_mesh",
            "mesh_bounds_mm": mesh["bounds_mm"],
            "profile": profile,
            "thickness": mesh["thickness"],
        }
        sampled = mesh["thickness"].get("sampled_min_mm")
        finding(
            report,
            "DFAM-02",
            "WARN" if width and sampled and sampled < width else "UNVERIFIED",
            geometry,
            "Sampled solid thickness is below configured outer line width."
            if width and sampled and sampled < width
            else "Effective wall generation and critical wall continuity require native toolpaths.",
            {**evidence, "configured_outer_line_width_mm": width},
            "Check critical wall thickness against effective widths, perimeter and gap-fill paths.",
            plate=plate,
        )
        thin = mesh_flags.get((mesh["object"], plate, "GEO.THIN"))
        finding(
            report,
            "DFAM-03",
            "WARN" if thin else "UNVERIFIED",
            geometry,
            "Sampled solid feature is below the selected geometry-policy heuristic."
            if thin
            else "Minimum features and gaps require scoped CAD or native path evidence.",
            {
                **evidence,
                "policy": policy["printer_profile"],
                "policy_wall_heuristic_mm": policy["min_wall_mm"],
            },
            "Measure critical text, holes, ribs and gaps; confirm their paths on the final slice.",
            plate=plate,
        )
        overhang = mesh_flags.get((mesh["object"], plate, "GEO.OVERHANG"))
        finding(
            report,
            "DFAM-04",
            "WARN" if overhang else "UNVERIFIED",
            geometry,
            "Downward-facing regions meet the geometry-policy overhang heuristic."
            if overhang
            else "Native bridge anchoring and support have yet to be evaluated.",
            {
                **evidence,
                "policy_overhang_degrees": policy["overhang_degrees"],
                "candidate_area_mm2": overhang or 0,
            },
            "Review build orientation and locate candidate bridges/support in the native preview.",
            plate=plate,
        )


def inspect_roles(report, plate, paths, evidence):
    incomplete = bool(paths.issues or paths.layer_issues) or not paths.model_layers
    widths = {k: [round(v, 5) for v in bounds] for k, bounds in paths.wall_widths.items()}
    finding(
        report,
        "DFAM-02",
        "UNVERIFIED",
        {"roles": sorted(widths)},
        "Role widths are nominal volume-equivalent estimates; wall compatibility requires "
        "critical CAD thickness and native path correspondence.",
        {**evidence, "wall_width_range_mm": widths},
        "Compare the actual outer/inner wall and gap-fill paths with each critical wall.",
        plate=plate,
    )
    roles = {}
    for role in ("bridge", "overhang", "support"):
        if role in paths.longest_run:
            length, z, line = paths.longest_run[role]
            longest, longest_line, start, end, longest_z = paths.longest_segment[role]
            roles[role] = {
                "segments": paths.counts[role],
                "longest_run_mm": round(length, 4),
                "z_mm": z,
                "end_line": line,
                "longest_segment_mm": round(longest, 4),
                "longest_segment_line": longest_line,
                "longest_segment_xyz_mm": [[*start, longest_z], [*end, longest_z]],
            }
    overhangs = {k: v for k, v in roles.items() if k != "support"}
    finding(
        report,
        "DFAM-04",
        "UNVERIFIED" if incomplete else "WARN" if overhangs else "NOT_APPLICABLE",
        {"roles": sorted(overhangs)},
        "Review annotated bridge and overhang runs."
        if overhangs
        else "No bridge or overhang runs identified in parsed model extrusion.",
        {**evidence, "roles": overhangs},
        "Inspect backing, anchors and free-air spans in the native preview; use profile-specific evidence.",
        plate=plate,
    )
    support = roles.get("support")
    finding(
        report,
        "DFAM-12",
        "UNVERIFIED" if support or incomplete else "NOT_APPLICABLE",
        {"roles": ["support"] if support else []},
        "Support extrusion requires a removal and contact-surface review."
        if support
        else "No support extrusion identified in parsed paths.",
        {**evidence, "support": support},
        "Inspect removal access, trapped interfaces and contact with critical surfaces in the native preview.",
        plate=plate,
    )


def read_gcode(path):
    if path.stat().st_size > MAX_GCODE_BYTES:
        raise ValueError("G-code exceeds the inspection size limit")
    return path.read_bytes()


def inspect_bytes(report, data, plate, features, artifact, member=None):
    inspect_plate(
        report,
        data.decode("utf-8"),
        plate,
        features,
        {
            "artifact": str(artifact),
            "member": member,
            "gcode_sha256": hashlib.sha256(data).hexdigest(),
            "input_sha256": report["dfam"]["input_sha256"],
        },
    )


def inspect_missing_plates(report, features, found):
    for feature in features:
        if feature["plate"] not in found:
            feature_result(
                report,
                feature,
                "UNVERIFIED",
                "Requested plate has no executable G-code.",
                {"scope": "nominal_toolpath", "available_plates": sorted(found)},
            )


def audit(path, spec=None, strict=False, plate=None):
    report = new_report()
    report["dfam"] = {"canonical_rules": CANONICAL, "physical_validation": "UNVERIFIED"}
    path = Path(path)
    try:
        if path.suffix.lower() == ".gcode" and path.stat().st_size > MAX_GCODE_BYTES:
            raise ValueError("G-code exceeds the inspection size limit")
        digest = file_hash(path)
        report["dfam"]["input_sha256"] = digest
        features = read_spec(spec, digest)
        by_plate = defaultdict(list)
        for feature in features:
            by_plate[feature["plate"]].append(feature)
        found = set()
        if path.suffix.lower() == ".gcode":
            match = PLATE.fullmatch(path.name)
            number = plate or (match[1] if match else "1")
            raw = read_gcode(path)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("G-code changed during inspection")
            inspect_bytes(report, raw, number, by_plate[number], path)
            found.add(number)
        elif path.suffix.lower() == ".3mf" and plate is None:
            total = 0
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    match = PLATE.fullmatch(info.filename)
                    if not match:
                        continue
                    number = match[1]
                    total += info.file_size
                    if (
                        number in found
                        or info.file_size > MAX_GCODE_BYTES
                        or total > 4 * MAX_GCODE_BYTES
                        or len(found) >= 64
                    ):
                        raise ValueError("Duplicate plate or G-code exceeds inspection limits")
                    inspect_bytes(
                        report, archive.read(info), number, by_plate[number], path, info.filename
                    )
                    found.add(number)
            if file_hash(path) != digest:
                raise ValueError("Sliced archive changed during inspection")
        else:
            raise ValueError("Use sliced 3MF or G-code; --plate is for a standalone G-code file")
        report["plates"] = sorted(found, key=int)
        if not found and not features:
            finding(
                report,
                "DFAM-14",
                "UNVERIFIED",
                {},
                "Archive has no executable plate G-code.",
                {"artifact": str(path)},
                "Audit the native sliced archive or exported G-code.",
                severity="warning",
            )
        inspect_missing_plates(report, features, found)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        report["execution_failure"] = True
        add(report, "EXEC.DFAM", "error", str(exc), action="Check the artifact and DfAM spec.")
    return finish(report, strict)
