import json
import shutil
import subprocess

from .policy import ROOT
from .report import add


def compliance(path, report):
    try:
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node >=22 is missing from PATH")
        p = subprocess.run(
            [
                node,
                str(ROOT / "tools/mcp-inspect.mjs"),
                str(path.resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if p.returncode:
            raise RuntimeError(p.stderr[:1000])
        c = json.loads(p.stdout)["compliance"]
        report["compliance"] = c
        if not c.get("parseable") or not c.get("validation", {}).get("nonStrict", {}).get("valid"):
            add(
                report,
                "3MF.COMPLIANCE",
                "error",
                "Official lib3mf cannot read this package",
                c.get("validation"),
                "Repair package structure and validate again with lib3mf.",
            )
        elif not c["validation"]["compliant"]:
            add(
                report,
                "3MF.STRICT",
                "warning",
                "Readable vendor project is not strictly 3MF-compliant",
                c["validation"]["strict"],
                "Review official diagnostics; vendor paint extensions may cause strict warnings.",
            )
        for f in c.get("validation", {}).get("findings", []):
            add(
                report,
                "3MF." + f["code"],
                f["severity"],
                f["message"],
                object=f.get("resourceId"),
            )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
        report["execution_failure"] = True
        add(
            report,
            "EXEC.LIB3MF",
            "error",
            str(e),
            action="Run the setup script and verify Node and the built official 3MF server.",
        )
