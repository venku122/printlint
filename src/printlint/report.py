"""Stable diagnostic schema and serializers."""

import json


def new_report():
    return {
        "schema_version": "1.0",
        "diagnostics": [],
        "geometry": [],
        "plates": [],
        "exit_code": 0,
    }


def add(
    r,
    rule,
    severity,
    description,
    value=None,
    action="Inspect and repair the source model, then export again.",
    object=None,
    plate=None,
):
    r["diagnostics"].append(
        dict(
            rule_id=rule,
            severity=severity,
            object=object,
            plate=plate,
            description=description,
            measured_value=value,
            corrective_action=action,
        )
    )


def finish(r, strict=False):
    r["diagnostics"].sort(
        key=lambda d: (
            d["rule_id"],
            str(d["plate"]),
            str(d["object"]),
            d["description"],
        )
    )
    r["exit_code"] = (
        2
        if r.get("execution_failure")
        else int(
            any(
                d["severity"] == "error" or (strict and d["severity"] == "warning")
                for d in r["diagnostics"]
            )
        )
    )
    return r


def render(r, fmt="text"):
    if fmt == "json":
        return json.dumps(r, indent=2, sort_keys=True, allow_nan=False)
    if fmt == "sarif":
        return json.dumps(
            {
                "version": "2.1.0",
                "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
                "runs": [
                    {
                        "tool": {"driver": {"name": "printlint", "version": "0.1.0"}},
                        "results": [
                            {
                                "ruleId": d["rule_id"],
                                "level": {
                                    "error": "error",
                                    "warning": "warning",
                                    "information": "note",
                                }[d["severity"]],
                                "message": {
                                    "text": d["description"] + " " + d["corrective_action"]
                                },
                                "properties": d,
                            }
                            for d in r["diagnostics"]
                        ],
                    }
                ],
            },
            indent=2,
        )
    lines = [
        f"PrintLint: {'execution failure' if r['exit_code'] == 2 else 'validation errors' if r['exit_code'] else 'passed'}"
    ]
    for d in r["diagnostics"]:
        lines.append(
            f"{d['severity'].upper()} {d['rule_id']} [plate={d['plate']}, object={d['object']}]: {d['description']} ({d['measured_value']})\n  → {d['corrective_action']}"
        )
    if r.get("statistics"):
        lines.append(json.dumps(r["statistics"], indent=2))
    return "\n".join(lines)
