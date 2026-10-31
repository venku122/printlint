import argparse
import json
from pathlib import Path

from .core import check, colors
from .report import add, finish, new_report, render


def main(argv=None):
    a = argparse.ArgumentParser(prog="printlint")
    subs = a.add_subparsers(dest="command", required=True)
    for name in ("check", "colors", "slice", "doctor"):
        s = subs.add_parser(name)
        if name != "doctor":
            s.add_argument("input", type=Path)
        s.add_argument("--json", action="store_true")
        s.add_argument("--format", choices=["text", "json", "sarif"], default="text")
        s.add_argument("--strict", action="store_true")
        s.add_argument("--policy", type=Path)
        s.add_argument("--manifest", type=Path)
        if name == "check":
            s.add_argument("--advisory", action="store_true")
        if name == "slice":
            s.add_argument("--slicer", choices=["bambu", "orca", "orca-stable"], required=True)
            s.add_argument("--output", type=Path)
    args = a.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text()) if args.manifest else None
    except (OSError, ValueError) as e:
        r = new_report()
        r["execution_failure"] = True
        add(
            r,
            "EXEC.MANIFEST",
            "error",
            str(e),
            action="Supply a readable valid JSON manifest.",
        )
        finish(r)
        print(render(r, "json" if args.json else args.format))
        return 2
    if args.command == "doctor":
        from .doctor import doctor

        r = doctor()
    elif args.command == "slice":
        from .slicer import slice_project

        r = slice_project(
            args.input, args.slicer, args.output, args.policy, args.strict, manifest=manifest
        )
    else:
        r = (check if args.command == "check" else colors)(
            args.input, policy=args.policy, manifest=manifest, strict=args.strict
        )
    if args.command == "check" and args.advisory:
        from .advisory import community_advisory
        from .policy import load_policy

        try:
            r["community_advisory"] = community_advisory(
                args.input, load_policy(args.policy)["nozzles_mm"][0]
            )
        except (OSError, ValueError, RuntimeError) as e:
            add(
                r,
                "ADVISORY.UNAVAILABLE",
                "warning",
                str(e),
                action="Review upstream advisory output; core checks are independent.",
            )
            finish(r, args.strict)
    print(render(r, "json" if args.json else args.format))
    return r["exit_code"]
