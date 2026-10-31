"""Slicer-specific extraction; absent fields remain unknown, never fabricated zeroes."""

import re

from .report import add


def seconds(value):
    terms = re.findall(r"([\d.]+)\s*([dhms])", value)
    return (
        round(sum(float(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u] for n, u in terms))
        if terms
        else None
    )


def parse_gcode(text, slicer):
    result = {
        "slicer": slicer,
        "estimated_time_seconds": None,
        "filament_g": None,
        "filament_mm": None,
        "filament_changes": None,
        "purge_volume_mm3": None,
        "model_volume_mm3": None,
        "prime_tower_g": None,
    }
    # Verified header conventions shared today, kept behind an explicit slicer discriminator.
    if slicer not in ("bambu", "orca", "orca-stable"):
        raise ValueError("Unsupported slicer dialect")
    for line in text.splitlines():
        m = re.search(r"total estimated time:\s*(.*)", line)
        if m:
            result["estimated_time_seconds"] = seconds(m[1])
        for key, label in [
            ("filament_g", "weight [g]"),
            ("filament_mm", "length [mm]"),
        ]:
            if line.startswith("; total filament " + label + " :"):
                result[key] = [
                    float(v) for v in re.findall(r"\d+(?:\.\d+)?", line.split(":", 1)[1])
                ]
        if line.startswith("; estimated printing time (normal mode) ="):
            result["estimated_time_seconds"] = seconds(line.split("=", 1)[1])
        for key, pattern in [
            ("filament_g", r"; filament used \[g\]\s*=\s*(.*)"),
            ("filament_mm", r"; filament used \[mm\]\s*=\s*(.*)"),
        ]:
            m = re.match(pattern, line)
            if m:
                result[key] = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", m[1])]
        m = re.match(r"; (?:total filament change|filament change count)\s*=\s*(\d+)", line)
        if m:
            result["filament_changes"] = int(m[1])
    return result


def inspect_statistics(stats, policy, report):
    changes = stats.get("filament_changes")
    if changes is not None and changes > policy["max_filament_changes"]:
        add(
            report,
            "SLICE.CHANGES",
            "warning",
            "Filament-change count exceeds policy",
            changes,
            "Review color layout and layer painting to reduce changes.",
        )
    purge = stats.get("purge_volume_mm3")
    model = stats.get("model_volume_mm3")
    if (
        purge is not None
        and model is not None
        and model > 0
        and purge / model > policy["max_purge_ratio"]
    ):
        add(
            report,
            "SLICE.PURGE",
            "warning",
            "Purge-to-model material ratio exceeds policy",
            round(purge / model, 4),
            "Review color changes, purge settings and batching; do not reduce purge without quality validation.",
        )
