# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.orcaslicer.plugin]
# name = "PrintLint"
# description = "Read-only mesh preflight and blocking slicing policy. No printer access."
# author = "Local PrintLint"
# version = "0.1.0"
# ///
"""Native lightweight checks. Full transformed/paint/thickness checks stay in the external CLI."""

import json

import orca

DEFAULTS = {
    "enabled": True,
    "max_triangles": 10000000,
    "min_feature_mm": 0.42,
    "block_nonmanifold": True,
}


def evaluate(snapshot, policy):
    c = DEFAULTS | policy
    out = []
    if not c["enabled"]:
        return out

    def add(rule, severity, obj, msg, val, action):
        out.append(
            dict(
                rule_id=rule,
                severity=severity,
                object=obj,
                plate=None,
                description=msg,
                measured_value=val,
                corrective_action=action,
            )
        )

    for o in snapshot:
        name = o["object"]
        if o["triangles"] > c["max_triangles"]:
            add(
                "ORCA.COMPLEXITY",
                "error",
                name,
                "Triangle count exceeds configured limit",
                o["triangles"],
                "Simplify the mesh or intentionally raise max_triangles.",
            )
        if not o["manifold"]:
            add(
                "ORCA.NONMANIFOLD",
                "error" if c["block_nonmanifold"] else "warning",
                name,
                "Mesh is not manifold",
                False,
                "Repair the exported source mesh and run external printlint check.",
            )
        if o["mesh_errors"]:
            add(
                "ORCA.REPAIRED",
                "warning",
                name,
                "Slicer reports import-time repairs",
                o["mesh_errors"],
                "Validate the original export externally; slicer repairs may hide source defects.",
            )
        d = min(o["dimensions_mm"])
        if d < c["min_feature_mm"]:
            add(
                "ORCA.SMALL_FEATURE",
                "warning",
                name,
                "Local mesh dimension below feature threshold",
                d,
                "Inspect feature survival in sliced preview; this is not a wall-thickness measurement.",
            )
    return out


def snapshot(objects):
    out = []
    for obj in objects:
        for vol in obj.volumes():
            if not vol.is_model_part():
                continue
            out.append(
                {
                    "object": obj.name + "/" + vol.name,
                    "triangles": vol.facets_count(),
                    "manifold": vol.is_manifold(),
                    "dimensions_mm": list(vol.bounding_box().size),
                    "mesh_errors": vol.mesh_errors_count(),
                }
            )
    return out


def policy(cap):
    raw = cap.get_config()
    return DEFAULTS | (json.loads(raw) if raw else {})


def result(diags):
    text = "PrintLint: " + str(len(diags)) + " finding(s)"
    if diags:
        text += "\n" + "\n".join(
            d["rule_id"] + ": " + d["description"] + " [" + str(d["measured_value"]) + "]"
            for d in diags
        )
    print(text)
    payload = json.dumps(
        {
            "diagnostics": diags,
            "scope": "native local mesh checks; external CLI required for transformed build/paint/thickness",
        }
    )
    if any(d["severity"] == "error" for d in diags):
        return orca.ExecutionResult.failure(orca.PluginResult.FatalError, text, payload)
    return orca.ExecutionResult.success(text, payload)


class Manual(orca.script.ScriptPluginCapabilityBase):
    def get_name(self):
        return "PrintLint manual check"

    def get_default_config(self):
        return DEFAULTS

    def execute(self):
        return result(evaluate(snapshot(orca.host.model().objects()), policy(self)))


class Pipeline(orca.slicing.SlicingPipelineCapabilityBase):
    def get_name(self):
        return "PrintLint slicing check"

    def get_default_config(self):
        return DEFAULTS

    def execute(self, ctx):
        if ctx.step != orca.slicing.Step.posSlice or ctx.object is None:
            return orca.ExecutionResult.success()
        # Read from the worker's snapshot, never the GUI model; never call UI on this thread.
        return result(evaluate(snapshot([ctx.object.model_object()]), policy(self)))


@orca.plugin
class PrintLint(orca.base):
    def register_capabilities(self):
        # Native read-only host access requires no filesystem, network or process permissions.
        orca.register_capability(Manual)
        orca.register_capability(Pipeline)
