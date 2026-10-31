import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_policy(path=None):
    p = json.loads((ROOT / "config/x2d.example.json").read_text())
    if path:
        p.update(json.loads(Path(path).read_text()))
    for k in ("envelope_mm", "nozzles_mm"):
        if not p[k] or any(float(x) <= 0 for x in p[k]):
            raise ValueError(f"Invalid policy: {k}")
    for k in ("extrusion_width_mm", "layer_height_mm", "min_wall_mm"):
        if float(p[k]) <= 0:
            raise ValueError(f"Invalid policy: {k}")
    return p


def validate_manifest(manifest):
    if manifest is None:
        return
    if not isinstance(manifest, dict) or not isinstance(manifest.get("filaments"), list):
        raise ValueError("Manifest must be an object containing a filaments list")
    seen = set()
    for f in manifest["filaments"]:
        if not isinstance(f, dict) or type(f.get("index")) is not int or f["index"] < 1:
            raise ValueError("Each manifest filament requires a positive integer index")
        if f["index"] in seen:
            raise ValueError("Duplicate manifest index")
        seen.add(f["index"])
        for k in ["color", "material", "ams_slot"]:
            if k in f and not isinstance(f[k], str):
                raise ValueError("Manifest " + k + " must be a string")
        if "tool" in f and type(f["tool"]) is not int:
            raise ValueError("Manifest tool must be a zero-based integer")
