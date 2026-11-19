"""Compare explicit job requirements with configured and emitted settings."""

import json
import math
import re
from collections import defaultdict

from .report import add

FIELDS = ("bottom_shell_layers", "top_surface_speed")
CONFIG = "Metadata/project_settings.config"


def read_expectations(path):
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Expected profile JSON exceeds 64 KiB")
    expected = json.loads(path.read_text())
    if not isinstance(expected, dict) or not expected or expected.keys() - set(FIELDS):
        raise ValueError("Expected profile accepts bottom_shell_layers and top_surface_speed")
    if "bottom_shell_layers" in expected:
        count = expected["bottom_shell_layers"]
        if type(count) is not int or count < 0:
            raise ValueError("bottom_shell_layers must be a non-negative integer")
    if "top_surface_speed" in expected:
        speeds = expected["top_surface_speed"]
        if (
            not isinstance(speeds, list)
            or not 1 <= len(speeds) <= 16
            or any(
                type(speed) not in (int, float) or not math.isfinite(speed) or speed <= 0
                for speed in speeds
            )
        ):
            raise ValueError("top_surface_speed must be an ordered list of positive speeds in mm/s")
    return expected


def read_config(archive):
    members = [info for info in archive.infolist() if info.filename == CONFIG]
    if len(members) != 1 or members[0].file_size > 8 * 1024 * 1024:
        raise ValueError("Expected one bounded vendor project settings resource")
    config = json.loads(archive.read(members[0]))
    if not isinstance(config, dict):
        raise ValueError("Vendor project settings must be a JSON object")
    return config


def gcode_settings(text):
    # A Bambu G-code file can repeat the resolved profile at its end. Preserve
    # conflicting evidence instead of silently taking whichever value came first.
    fields = defaultdict(set)
    for key, value in re.findall(
        r"^; (bottom_shell_layers|top_surface_speed)[ \t]*=[ \t]*([^\r\n]+)", text, re.M
    ):
        fields[key].add(value.strip())
    ambiguous = {key for key, values in fields.items() if len(values) > 1}
    return {
        key: sorted(values) if key in ambiguous else next(iter(values))
        for key, values in fields.items()
    }, ambiguous


def compare_expectations(report, expected, actual, stage, *, plate=None, ambiguous=()):
    checks = report.setdefault("profile_expectations", [])
    for key in FIELDS:
        if key not in expected:
            continue
        wanted, observed = expected[key], actual.get(key)
        status = "MISMATCH"
        if key in ambiguous:
            status = "AMBIGUOUS"
        elif observed is None:
            status = "MISSING"
        else:
            try:
                if key == "top_surface_speed":
                    values = observed if isinstance(observed, list) else str(observed).split(",")
                    matches = [float(v) for v in values[: len(wanted)]] == wanted
                else:
                    matches = float(observed) == wanted
                if matches:
                    status = "PASS"
            except (TypeError, ValueError, OverflowError):
                pass
        result = dict(
            stage=stage, plate=plate, field=key, expected=wanted, actual=observed, status=status
        )
        checks.append(result)
        if status != "PASS":
            add(
                report,
                "PROFILE.EXPECTATION",
                "error",
                f"{stage}: {key} is {status.lower()}",
                result,
                "Correct the configured project or resolve the emitted difference, then revalidate.",
                plate=plate,
            )
