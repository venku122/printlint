import importlib.metadata
import json
import platform
import shutil
import subprocess

from .policy import ROOT
from .report import add, finish, new_report
from .slicer import SLICERS


def doctor():
    r = new_report()
    env = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "root": str(ROOT),
        "slicers": {},
    }
    for name in [
        "trimesh",
        "numpy",
        "scipy",
        "rtree",
        "networkx",
        "defusedxml",
        "mmu-remapper",
    ]:
        try:
            env[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            add(
                r,
                "DOCTOR.DEPENDENCY",
                "error",
                "Missing " + name,
                action="Run tools/setup.sh.",
            )
    for name, path in SLICERS.items():
        env["slicers"][name] = {"path": str(path), "available": path.is_file()}
        if not path.is_file():
            add(
                r,
                "DOCTOR.SLICER",
                "error",
                "Missing slicer " + name,
                action="Install the app or update SLICERS paths.",
            )
    env["node"] = shutil.which("node")
    env["uv"] = shutil.which("uv")
    if not env["node"]:
        add(r, "DOCTOR.NODE", "error", "Node is missing", action="Install Node >=22.")
    env["official_mcp_built"] = (ROOT / "vendor/3mf-mcp/dist/cli.js").is_file()
    if not env["official_mcp_built"]:
        add(
            r,
            "DOCTOR.MCP",
            "error",
            "Official MCP is not built",
            action="Run npm ci, npm test and npm run build in vendor/3mf-mcp.",
        )
    if env["node"]:
        p = subprocess.run([env["node"], "--version"], capture_output=True, text=True, check=False)
        env["node_version"] = p.stdout.strip()
        if p.returncode or int(p.stdout.strip().lstrip("v").split(".")[0]) < 22:
            add(r, "DOCTOR.NODE", "error", "Node >=22 is required", p.stdout.strip())
    evidence = ROOT / "docs/validation-status.json"
    env["acceptance"] = (
        json.loads(evidence.read_text())
        if evidence.exists()
        else {"native_plugin": "not yet verified"}
    )
    if env["acceptance"].get("native_plugin") != "verified":
        add(
            r,
            "DOCTOR.PLUGIN",
            "warning",
            "Native Orca plugin UI execution remains unverified",
            action="Unlock the Mac and complete manual action and deliberate blocking-hook checks.",
        )
    r["environment"] = env
    return finish(r)
