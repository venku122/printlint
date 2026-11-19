# DfAM evidence with PrintLint

DfAM is design for additive manufacturing. These checks summarize nominal model and toolpath evidence. The supported rule IDs and evidence limits are listed below.

```sh
printlint check configured.3mf --dfam --json
printlint slice configured.3mf --dfam --slicer bambu --output /tmp/dfam-slice --json
printlint dfam /tmp/dfam-slice/sliced.3mf --dfam-spec witnesses.json --format sarif
```

`check --dfam` includes existing validation plus structured mesh evidence. `slice --dfam` adds it to `preflight.json` and inspects annotated native output after the normal gate and slicer checks. Run the final `dfam` command with witnesses to check critical features. It also accepts standalone annotated native G-code. A name such as `plate_2.gcode` selects plate 2. Use `--plate` when the standalone filename cannot convey the plate. The command uses the G-code members of a sliced 3MF.

## Witness specification

Bind the spec to the exact audit input SHA-256. Use CAD-derived plate-local XY and the matching executable layer Z, all in millimetres. Account for rotation, offsets, scale, layer sampling and per-plate placement. Include source revision/section and the selection rationale in `source`. A revision or reslice needs reviewed witnesses and a new hash.

```json
{
  "input_sha256": "REPLACE_WITH_EXACT_ARCHIVE_OR_GCODE_SHA256",
  "source": "CAD revision B, section at Z=10.1 mm; corresponding native layer Z=10.2 mm",
  "features": [
    {
      "name": "Hinge lip",
      "plate": "1",
      "critical": true,
      "points_mm": [[120, 30, 10.2], [120, 36, 10.2]]
    }
  ]
}
```

- The default `rule_id` is `DFAM-14` and the default `expect` is `solid`. Each specified witness must intersect nominal model extrusion.
- For `DFAM-02`, use solid witnesses along the wall and optionally supply measured `wall_thickness_mm`. The result includes effective configured outer width where resolvable and local equivalent path widths.
- For `DFAM-03`, use `solid` for material witnesses or `clear` for a required gap. For `DFAM-12`, use `support_clear` to check for nominal support at sampled removal-corridor points. Review the full removal path and contact surfaces manually.
- A critical mismatch or unverified witness is an error. A noncritical mismatch or unverified witness is a warning. `--strict` blocks warnings. If a known risk has an explicit decision for the exact slice, add `"accepted_risk": {"reason": "...", "evidence": "..."}`. The report retains the original status and evidence. Syntax, hash or read failure returns exit 2.
- JSON and SARIF include rule, severity, status, affected geometry, rationale, evidence and corrective action. A scoped PASS covers the listed witness points. Plate-level UNVERIFIED entries cover outstanding review.

## Coverage and limitations

| Rules | Implemented evidence |
| --- | --- |
| DFAM-02, 03 | Sampled solid thickness and configured width or selected policy heuristics. Automated nominal solid/clear witness checks. Review perimeter continuity, holes, text and thin or fragile paths. |
| DFAM-04 | Candidate downward mesh area and annotated bridge/overhang runs, with location and longest segment. Review anchors, backing and unsupported span in preview. |
| DFAM-12 | Locates annotated supports and checks supplied support-clear witnesses. Removal access and surface finish require review. |
| DFAM-14 | Automated nominal material/clearance checks for named witnesses on the exact artifact. Review continuity and critical features beyond the sampled points. |
| DFAM-15 | Reports available estimated time, mass and changes. Comparative judgment remains manual. |
| DFAM-01, 05–11, 13, 16 | Engineering and physical review when applicable. |

The parser uses annotated, planar G0/G1 moves in recognized Bambu Studio and Orca executable blocks and estimates a bead width from positive filament extrusion, equal configured filament diameters and annotated layer height. Retraction repayment, support, purge/tower, skirt/brim and travel are excluded from model witness evidence. Unsupported positive arcs, nonplanar moves and incomplete annotations can leave affected layers unverified. Conditional vendor scripts and role labels limit coverage. A bridge run is cumulative labeled extrusion and may include infill-backed paths. A clean witness check establishes neither continuous geometry nor deposited dimensions, mechanical fit, legibility or strength. Review the actual native preview and retain physical evidence separately.
