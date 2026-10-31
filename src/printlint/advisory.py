import json
import subprocess
import sys

from .policy import ROOT


def community_advisory(path, nozzle):
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "vendor/3d-print-validator/print3d_check.py"),
            str(path),
            "--json",
            "--samples",
            "512",
            "--nozzle",
            str(nozzle),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    # Upstream writes ANSI progress before its JSON. Never pass that through as machine output.
    start = proc.stdout.find("{")
    if start < 0:
        raise RuntimeError("Community validator returned no JSON: " + proc.stderr[:500])
    result = json.loads(proc.stdout[start:])
    return {
        "advisory_only": True,
        "upstream_exit_status": proc.returncode,
        "result": result,
        "limitations": [
            "Only largest connected body gets integrity/thickness checks upstream.",
            "Random surface samples; small thin regions can be missed.",
            "A heuristic score cannot certify printability.",
        ],
    }
