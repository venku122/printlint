"""Geometry checks never repair the source or discard invalid faces silently."""

import numpy as np
import trimesh

from .report import add


def inspect_mesh(mesh, policy, report, obj, plate, check_position=True, tool=0):
    kw = dict(object=obj, plate=plate)

    def diag(
        rule,
        level,
        msg,
        val=None,
        action="Repair in CAD and re-export; inspect the slicer preview.",
    ):
        add(report, rule, level, msg, val, action, **kw)

    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        diag("GEO.EMPTY", "error", "Empty mesh")
        return
    if not np.isfinite(mesh.vertices).all():
        diag("GEO.INVALID", "error", "Non-finite vertex coordinates")
        return
    if mesh.faces.min() < 0 or mesh.faces.max() >= len(mesh.vertices):
        diag("GEO.INVALID", "error", "Triangle vertex index out of range")
        return
    # STL duplicates vertices at every face; merge coincident vertices only on the analysis copy.
    mesh = mesh.copy()
    mesh.merge_vertices()
    degenerate = int((mesh.area_faces < 1e-10).sum())
    topology = mesh.copy()
    if degenerate:
        topology.update_faces(topology.area_faces >= 1e-10)
    counts = np.bincount(topology.edges_unique_inverse)
    boundary = int((counts == 1).sum())
    nonmanifold = int((counts > 2).sum())
    degenerate = int((mesh.area_faces < 1e-10).sum())
    if nonmanifold:
        diag(
            "GEO.NONMANIFOLD",
            "error",
            "Edges shared by more than two faces",
            nonmanifold,
        )
    if boundary:
        diag(
            "GEO.OPEN",
            policy.get("surface_policy", "warning"),
            "Open boundary edges; may be intentional surface geometry",
            boundary,
            "Confirm intentional surface/vase use, or close the holes in CAD.",
        )
    if not mesh.is_winding_consistent:
        diag("GEO.WINDING", "warning", "Inconsistent triangle winding")
    if degenerate:
        diag("GEO.DEGENERATE", "warning", "Zero-area or collapsed triangles", degenerate)
    parts = topology.split(only_watertight=False)
    if len(parts) > 1:
        diag(
            "GEO.COMPONENTS",
            "information",
            "Separate connected components; may be intentional",
            len(parts),
            "Confirm all components are intended and attached or printable independently.",
        )
    b = mesh.bounds
    dims = mesh.extents
    env = np.array(policy["envelope_mm"])
    if (dims > env + 1e-3).any() or (
        check_position and ((b[0] < -0.01).any() or (b[1] > env + 0.01).any())
    ):
        diag(
            "GEO.ENVELOPE",
            "error",
            "Geometry outside the configured X2D build envelope",
            {"bounds_mm": b.tolist(), "envelope_mm": env.tolist()},
            "Reposition, split or scale in the slicer; verify the actual nozzle printable area.",
        )
    if check_position and b[0, 2] > policy["layer_height_mm"]:
        diag(
            "GEO.FLOATING",
            "warning",
            "Object has no contact with Z=0",
            float(b[0, 2]),
            "Place on the plate or verify intended support by another part.",
        )
    if (
        check_position
        and 0 <= tool < len(policy.get("tool_x_min_mm", []))
        and b[0, 0] < policy["tool_x_min_mm"][tool] - 0.01
    ):
        diag(
            "GEO.TOOL_AREA",
            "error",
            "Object lies outside this toolhead printable area",
            {"tool": tool, "x_min_mm": float(b[0, 0])},
            "Reposition the object within the selected nozzle printable area.",
        )
    thickness = {}
    if mesh.is_watertight and not degenerate and len(mesh.faces) < 500000:
        # Fixed seed gives repeatable surface samples. Ray estimate is advisory, not a minimum-wall proof.
        points, fi = trimesh.sample.sample_surface(
            mesh, int(policy.get("thickness_samples", 512)), seed=0
        )
        normals = mesh.face_normals[fi]
        try:
            hits, ri, _ = mesh.ray.intersects_location(
                points - normals * 1e-5, -normals, multiple_hits=False
            )
            d = np.linalg.norm(hits - points[ri], axis=1)
            d = d[d > 1e-4]
            if len(d):
                thickness = {
                    "sampled_min_mm": round(float(d.min()), 6),
                    "sampled_p10_mm": round(float(np.percentile(d, 10)), 6),
                    "samples": len(d),
                }
                if d.min() < policy["min_wall_mm"]:
                    diag(
                        "GEO.THIN",
                        "warning",
                        "Sampled wall/feature thinner than policy; ray estimate is advisory",
                        thickness,
                        "Inspect thin features in the sliced preview; thicken where function requires it.",
                    )
        except (ValueError, RuntimeError, ImportError) as e:
            diag(
                "GEO.THICKNESS_UNKNOWN",
                "information",
                "Ray thickness unavailable",
                type(e).__name__,
                "Use the slicer preview and measure walls in CAD.",
            )
    down = mesh.face_normals[:, 2] < -np.cos(np.radians(policy["overhang_degrees"]))
    down &= mesh.triangles[:, :, 2].max(axis=1) > b[0, 2] + policy["layer_height_mm"]
    area = float(mesh.area_faces[down].sum())
    if area > 0.01:
        diag(
            "GEO.OVERHANG",
            "warning",
            "Downward-facing area above the base; bridges/support are not resolved by this heuristic",
            round(area, 4),
            "Inspect bridges, islands and supports in the sliced preview.",
        )
    report["geometry"].append(
        dict(
            object=obj,
            plate=plate,
            bounds_mm=np.round(b, 6).tolist(),
            dimensions_mm=np.round(dims, 6).tolist(),
            watertight=bool(mesh.is_watertight),
            winding_consistent=bool(mesh.is_winding_consistent),
            faces=len(mesh.faces),
            vertices=len(mesh.vertices),
            connected_components=len(parts),
            open_edges=boundary,
            nonmanifold_edges=nonmanifold,
            degenerate_faces=degenerate,
            thickness=thickness,
        )
    )
