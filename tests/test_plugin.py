import importlib.util
import sys
import types

from printlint.policy import ROOT


def load(monkeypatch):
    fake = types.SimpleNamespace(
        script=types.SimpleNamespace(ScriptPluginCapabilityBase=object),
        slicing=types.SimpleNamespace(SlicingPipelineCapabilityBase=object),
        base=object,
        plugin=lambda c: c,
    )
    monkeypatch.setitem(sys.modules, "orca", fake)
    s = importlib.util.spec_from_file_location(
        "native_printlint", ROOT / "plugins/printlint_native.py"
    )
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_native_policy_blocks(monkeypatch):
    m = load(monkeypatch)
    snap = [
        {
            "object": "cube",
            "triangles": 12,
            "manifold": True,
            "dimensions_mm": [10, 10, 10],
            "mesh_errors": 0,
        }
    ]
    assert m.evaluate(snap, {"max_triangles": 8})[0]["severity"] == "error"
    assert not m.evaluate(snap, {"max_triangles": 100})


def test_native_nonmanifold(monkeypatch):
    m = load(monkeypatch)
    d = m.evaluate(
        [
            {
                "object": "bad",
                "triangles": 4,
                "manifold": False,
                "dimensions_mm": [10, 10, 10],
                "mesh_errors": 2,
            }
        ],
        {},
    )
    assert {"ORCA.NONMANIFOLD", "ORCA.REPAIRED"} == {v["rule_id"] for v in d}
