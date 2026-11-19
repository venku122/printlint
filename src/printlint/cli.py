import argparse
import json
from pathlib import Path

from .core import check, colors
from .profile_intent import read_expectations
from .report import add, finish, new_report, render


def main(argv=None):
    a = argparse.ArgumentParser(prog="printlint")
    subs = a.add_subparsers(dest="command", required=True)
    for name in ("check", "colors", "slice", "doctor", "dfam", "inspect-final"):
        s = subs.add_parser(name)
        if name != "doctor":
            s.add_argument("input", type=Path)
        s.add_argument("--json", action="store_true")
        s.add_argument("--format", choices=["text", "json", "sarif"], default="text")
        s.add_argument("--strict", action="store_true")
        if name != "dfam":
            s.add_argument("--policy", type=Path)
            s.add_argument("--manifest", type=Path)
        if name == "dfam":
            s.add_argument("--dfam-spec", type=Path)
            s.add_argument("--plate", type=int, choices=range(1, 65), metavar="1-64")
        if name in ("check", "slice", "inspect-final"):
            s.add_argument("--expect-profile", type=Path)
        if name == "inspect-final":
            s.add_argument("--report", type=Path)
            s.add_argument("--validation-3mf", type=Path)
            s.add_argument("--dfam-spec", type=Path)
            s.add_argument("--plate", type=int, choices=range(1, 65), metavar="1-64")
        if name in ("check", "slice"):
            s.add_argument("--dfam", action="store_true")
        if name == "check":
            s.add_argument("--advisory", action="store_true")
        if name == "slice":
            s.add_argument("--slicer", choices=["bambu", "orca", "orca-stable"], required=True)
            s.add_argument("--output", type=Path)
    args = a.parse_args(argv)
    if args.command == "dfam":
        from .dfam import audit

        r = audit(args.input, args.dfam_spec, args.strict, str(args.plate) if args.plate else None)
        print(render(r, "json" if args.json else args.format))
        return r["exit_code"]
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
    expected = None
    if getattr(args, "expect_profile", None):
        try:
            expected = read_expectations(args.expect_profile)
        except (OSError, ValueError, OverflowError) as e:
            r = new_report()
            r["execution_failure"] = True
            add(
                r,
                "EXEC.PROFILE_EXPECTATIONS",
                "error",
                str(e),
                action="Supply a valid profile expectations JSON object.",
            )
            finish(r)
            print(render(r, "json" if args.json else args.format))
            return r["exit_code"]
    if args.command == "inspect-final":
        from .final_inspection import compact_receipt, inspect_final

        r = inspect_final(
            args.input,
            expected=expected,
            policy=args.policy,
            manifest=manifest,
            strict=args.strict,
            spec=args.dfam_spec,
            plate=args.plate,
            details=args.report,
            validation=args.validation_3mf,
        )
        if args.json or args.format == "json":
            print(json.dumps(compact_receipt(r), indent=2, allow_nan=False))
        else:
            print(render(r, args.format))
        return r["exit_code"]
    if args.command == "doctor":
        from .doctor import doctor

        r = doctor()
    elif args.command == "slice":
        from .slicer import slice_project

        r = slice_project(
            args.input,
            args.slicer,
            args.output,
            args.policy,
            args.strict,
            manifest=manifest,
            dfam=args.dfam,
            expected=expected,
        )
    else:
        r = (check if args.command == "check" else colors)(
            args.input,
            policy=args.policy,
            manifest=manifest,
            strict=args.strict,
            **({"dfam": args.dfam} if args.command == "check" else {}),
        )
    if args.command == "check" and expected and r["exit_code"] != 2:
        import zipfile

        from .profile_intent import compare_expectations, read_config

        try:
            with zipfile.ZipFile(args.input) as archive:
                compare_expectations(r, expected, read_config(archive), "configured_input")
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            r["execution_failure"] = True
            add(r, "EXEC.PROFILE_EXPECTATIONS", "error", str(e))
        finish(r, args.strict)
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
