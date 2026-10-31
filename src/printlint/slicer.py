"""Offline slicing only. No networking, upload or print interfaces."""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .core import check
from .policy import load_policy
from .report import add, finish, new_report
from .statistics import inspect_statistics, parse_gcode

SLICERS = {
    "bambu": Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
    "orca": Path("/Applications/OrcaSlicer-PrintLint-Beta.app/Contents/MacOS/OrcaSlicer"),
    "orca-stable": Path("/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"),
}


def orca_statistics(raw):
    if raw.get("version") != 1:
        raise ValueError("Unsupported Orca statistics schema version")
    units = raw.get("units", {})
    if any(
        units.get(k) != v
        for k, v in {
            "time": "s",
            "volume": "mm3",
            "weight": "g",
            "length": "mm",
        }.items()
    ):
        raise ValueError("Unexpected Orca statistics units")
    s = raw.get("summary", {})
    fs = s.get("filaments", [])

    def total(kind, key):
        return (
            sum(f[kind][key] for f in fs)
            if fs and all(key in f.get(kind, {}) for f in fs)
            else None
        )

    return {
        "estimated_time_seconds": s.get("time"),
        "filament_g": [f.get("weight") for f in fs] if fs else None,
        "filament_mm": [f.get("length") for f in fs] if fs else None,
        "filament_changes": s.get("filament_changes"),
        "purge_volume_mm3": total("flush", "volume"),
        "model_volume_mm3": total("model", "volume"),
        "prime_tower_g": total("prime_tower", "weight"),
        "layer_count": s.get("layer_count"),
        "layers": raw.get("layers"),
        "objects": raw.get("objects"),
        "raw_statistics_version": raw["version"],
    }


def slice_project(path, slicer, output=None, policy=None, strict=False, manifest=None):
    r = new_report()
    path = Path(path)
    try:
        p = load_policy(policy)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() != ".3mf":
            add(
                r,
                "SLICE.PROFILE",
                "error",
                "Slicing requires a configured 3MF project, not bare geometry",
                action="Save a project with explicit printer/process/filaments in the intended slicer.",
            )
            return finish(r, strict)
        with zipfile.ZipFile(path) as z:
            cfg = json.loads(z.read("Metadata/project_settings.config"))
            model = z.read("3D/3dmodel.model").decode()
        keys = (
            "printer_model",
            "printer_settings_id",
            "print_settings_id",
            "filament_settings_id",
            "nozzle_diameter",
            "printable_area",
            "printable_height",
            "layer_height",
            "line_width",
            "filament_type",
            "filament_colour",
            "filament_density",
        )
        if not all(
            cfg.get(k)
            for k in (
                "printer_model",
                "printer_settings_id",
                "print_settings_id",
                "filament_settings_id",
            )
        ) or not ("BambuStudio:3mfVersion" in model or "OrcaSlicer" in model):
            add(
                r,
                "SLICE.PROFILE",
                "error",
                "Project lacks a recognized vendor marker or explicit configured presets",
                action="Save the project from Bambu Studio/OrcaSlicer; generic fallback is forbidden.",
            )
            return finish(r, strict)
        exe = SLICERS[slicer]
        if not exe.is_file():
            raise FileNotFoundError(str(exe))
        # Bambu and Orca schemas are not interchangeable. Require a native model profile.
        if slicer.startswith("orca"):
            profile_root = exe.parent.parent / "Resources/profiles"
            supported = False
            for f in list(profile_root.rglob("*.json")) + list(
                (Path.home() / "Library/Application Support/OrcaSlicer/system").rglob("*.json")
            ):
                if f.name == cfg["printer_settings_id"] + ".json":
                    supported = True
                    break
            if not supported and any(profile_root.glob("*.opc")):
                # New Orca builds package native presets in binary .opc caches.
                # Let Orca resolve them; verify_profile below must still compare
                # the actual sliced output with every critical embedded setting.
                add(
                    r,
                    "SLICE.PROFILE_CACHE",
                    "information",
                    "Orca uses packaged presets; preset resolution will be checked in sliced output",
                    cfg["printer_settings_id"],
                    "Review output-profile diagnostics; no generic fallback is accepted.",
                )
                supported = True
            if not supported:
                add(
                    r,
                    "SLICE.PROFILE",
                    "error",
                    "This Orca build has no native profile matching the project printer",
                    cfg["printer_settings_id"],
                    "Use a compatible Orca project/profile. X2D is supported by the installed Bambu Studio; do not substitute another printer.",
                )
                return finish(r, strict)
        dest = (
            Path(output).resolve() if output else Path(tempfile.mkdtemp(prefix="printlint-slice-"))
        )
        dest.mkdir(parents=True, exist_ok=True)
        if any(dest.iterdir()):
            raise ValueError(
                "Output directory must be empty to prevent stale artifacts or overwrites"
            )
        copy = dest / "input.3mf"
        shutil.copy2(path, copy)
        # Validate the exact copy that the slicer will receive, not a potentially changing source.
        preflight = check(copy, policy=policy, manifest=manifest, strict=strict)
        r["preflight"] = preflight
        r["diagnostics"].extend(preflight["diagnostics"])
        (dest / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True))
        if preflight["exit_code"]:
            if preflight["exit_code"] == 2:
                r["execution_failure"] = True
            add(
                r,
                "SLICE.PREFLIGHT_BLOCKED",
                "error",
                "PrintLint preflight stopped slicing",
                preflight["exit_code"],
                "Resolve the preflight findings and rerun; no slicer was launched.",
            )
            return finish(r, strict)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        data = dest / "slicer-data"
        data.mkdir()
        cmd = [
            str(exe),
            "--debug",
            "3",
            "--datadir",
            str(data),
            "--slice",
            "0",
            "--outputdir",
            str(dest),
        ]
        if slicer == "orca":
            cmd += ["--export-statistics"]
        if slicer.startswith("orca"):
            cmd += ["--logfile", str(dest / "slicer-debug.log")]
        cmd += [str(copy)]
        proc = subprocess.run(cmd, cwd=dest, capture_output=True, text=True, timeout=600)
        log = proc.stdout + "\n" + proc.stderr
        if (dest / "slicer-debug.log").exists():
            log += "\n" + (dest / "slicer-debug.log").read_text(errors="replace")
        (dest / "process.log").write_text(log)
        r["slicer"] = {
            "name": slicer,
            "exit_status": proc.returncode,
            "command": cmd,
            "output_directory": str(dest),
            "source_sha256": digest,
            "source_unchanged": hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "project_presets": {k: cfg.get(k) for k in keys},
        }
        for line in log.splitlines():
            if re.search(
                r"warning|\[error\]|\bfatal\b|not in range|run found error|got error when validate|Version Check:.*not supported",
                line,
                re.I,
            ):
                add(
                    r,
                    "SLICE.DIAGNOSTIC",
                    log_severity(line),
                    line[:1000],
                    action="Review the full process log; correct incompatible settings before using the artifact.",
                )
        if proc.returncode:
            add(
                r,
                "SLICE.FAILED",
                "error",
                "Slicer process failed",
                proc.returncode,
                "Inspect process.log; use a native compatible project.",
            )
            return finish(r, strict)
        gcodes = sorted(dest.glob("plate_*.gcode"))
        if not gcodes:
            raise RuntimeError("Slicer returned success but produced no G-code")
        r["statistics"] = {"plates": []}
        r["artifacts"] = [
            str(f) for f in sorted(dest.iterdir()) if f.is_file() and f.name != "input.3mf"
        ]
        for g in gcodes:
            text = g.read_text(errors="replace")
            parsed = parse_gcode(text, slicer)
            outputcfg = verify_profile(cfg, text, r)
            statsfile = g.with_suffix(".statistics.json")
            if statsfile.exists():
                parsed.update(orca_statistics(json.loads(statsfile.read_text())))
            else:
                add(
                    r,
                    "SLICE.STATISTICS_PARTIAL",
                    "information",
                    "No structured statistics file; only verified G-code headers are available",
                    g.name,
                    "Use Orca 2.5 statistics export for per-object/layer and purge breakdowns.",
                )
            parsed["plate"] = g.stem
            parsed["resolved_profile"] = outputcfg
            r["statistics"]["plates"].append(parsed)
            inspect_statistics(parsed, p, r)
        if not r["slicer"]["source_unchanged"]:
            raise RuntimeError("Input file unexpectedly changed")
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
        subprocess.TimeoutExpired,
    ) as e:
        r["execution_failure"] = True
        add(
            r,
            "EXEC.SLICE",
            "error",
            str(e),
            action="Check the project, executable and empty output directory; see process.log if present.",
        )
    return finish(r, strict)


def log_severity(line):
    if re.search(
        r"\[error\]|\bfatal\b|not in range|run found error|got error when validate|Version Check:.*not supported",
        line,
        re.I,
    ):
        return "error"
    return "warning"


def verify_profile(cfg, text, report):
    keys = (
        "printer_model",
        "printer_settings_id",
        "print_settings_id",
        "nozzle_diameter",
        "printable_area",
        "printable_height",
        "layer_height",
        "line_width",
        "filament_type",
        "filament_colour",
        "filament_settings_id",
        "filament_density",
    )

    def norm(value, key):
        if isinstance(value, list):
            items = [str(x).strip().strip('"') for x in value]
        elif key == "printable_area" or key == "nozzle_diameter":
            items = str(value).split(",")
        elif key.startswith("filament_"):
            items = [v.strip().strip('"') for v in str(value).split(";")]
        else:
            items = [str(value).strip().strip('"')]

        def numeric(s):
            try:
                return str(float(s))
            except ValueError:
                return s.strip()

        return [numeric(s) for s in items]

    actual = {}
    for key in keys:
        m = re.search(r"^; " + re.escape(key) + r"\s*=\s*(.*)$", text, re.M)
        if m:
            actual[key] = m[1].strip()
        if key not in cfg:
            continue
        if key not in actual or norm(cfg[key], key) != norm(actual[key], key):
            add(
                report,
                "SLICE.PROFILE",
                "error",
                "Sliced output did not preserve embedded " + key,
                {"expected": cfg[key], "actual": actual.get(key)},
                "Reject this output and resolve the effective slicer settings; no generic fallback allowed.",
            )
    return actual
