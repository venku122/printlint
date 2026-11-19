"""Compact read-only receipt for a final slicer archive."""

import hashlib
import json
import zipfile
from collections import Counter

from .core import check
from .dfam import MAX_GCODE_BYTES, PLATE, audit, file_hash
from .profile_intent import compare_expectations, gcode_settings, read_config
from .report import add, finish, new_report
from .statistics import parse_gcode


def plate_evidence(path, report, expected, selected, *, wrapper=False):
    hashes = {}
    size = 0
    with zipfile.ZipFile(path) as archive:
        if expected:
            compare_expectations(
                report,
                expected,
                read_config(archive),
                "validation_wrapper" if wrapper else "archive",
            )
        for info in archive.infolist():
            match = PLATE.fullmatch(info.filename)
            if not match:
                continue
            number = int(match[1])
            size += info.file_size
            if (
                number in hashes
                or len(hashes) >= 64
                or info.file_size > MAX_GCODE_BYTES
                or size > 4 * MAX_GCODE_BYTES
            ):
                raise ValueError("Duplicate or excessive executable plates")
            raw = archive.read(info)
            hashes[number] = hashlib.sha256(raw).hexdigest()
            if wrapper or selected not in (None, number):
                continue
            text = raw.decode("utf-8")
            if expected:
                values, ambiguous = gcode_settings(text)
                compare_expectations(
                    report, expected, values, "gcode", plate=number, ambiguous=ambiguous
                )
            stats = parse_gcode(text, "orca" if "OrcaSlicer" in text[:2048] else "bambu")
            report["plates"].append(
                {
                    "plate": number,
                    "member": info.filename,
                    "gcode_sha256": hashes[number],
                    "estimated_time_seconds": stats["estimated_time_seconds"],
                    "filament_g": stats["filament_g"],
                }
            )
    return hashes


def inspect_final(
    path,
    *,
    expected,
    policy,
    manifest,
    strict,
    spec=None,
    plate=None,
    details=None,
    validation=None,
):
    report = new_report()
    report["artifact"] = {"path": str(path.resolve())}
    report["strict"] = strict
    report["review"] = dict(
        native_preview="UNVERIFIED",
        camera="UNVERIFIED",
        physical_ams="UNVERIFIED",
        physical_acceptance="UNVERIFIED",
    )
    try:
        if path.suffix.lower() != ".3mf" or (validation and validation.suffix.lower() != ".3mf"):
            raise ValueError("Use the exact final sliced 3MF archive and an optional 3MF wrapper")
        digest = file_hash(path)
        report["artifact"]["sha256"] = digest
        hashes = plate_evidence(path, report, expected, plate)
        report["plates"].sort(key=lambda row: row["plate"])
        if not report["plates"]:
            add(report, "FINAL.MISSING_GCODE", "error", "Requested executable plate is absent")

        check_path, check_digest, matched = path, digest, True
        if validation is not None:
            check_path, check_digest = validation, file_hash(validation)
            matched = bool(hashes) and hashes == plate_evidence(
                validation, report, expected, plate, wrapper=True
            )
            report["validation_artifact"] = {
                "path": str(validation.resolve()),
                "sha256": check_digest,
                "gcode_matches": matched,
                "scope": "wrapper_geometry_and_colors",
            }
            if not matched:
                add(
                    report,
                    "FINAL.VALIDATION_HASH",
                    "error",
                    "Validation wrapper must contain byte-identical G-code for every plate",
                )

        if matched:
            lint = check(check_path, policy=policy, manifest=manifest, strict=strict)
            report["file_check"] = lint
            report["diagnostics"].extend(lint["diagnostics"])
            report["execution_failure"] = lint["exit_code"] == 2
            if spec is not None:
                findings = audit(check_path, spec=spec, strict=strict)
                report["dfam"] = findings
                report["execution_failure"] |= findings["exit_code"] == 2
                report["diagnostics"].extend(findings["diagnostics"])
        if file_hash(path) != digest or (
            validation is not None and file_hash(validation) != check_digest
        ):
            raise ValueError("Final archive or validation wrapper changed during inspection")
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        report["execution_failure"] = True
        add(
            report,
            "EXEC.INSPECT_FINAL",
            "error",
            str(exc),
            action="Check the final artifact, expectations and witness spec.",
        )
    finish(report, strict)
    if details is not None:
        try:
            serialized = json.dumps(report, indent=2, allow_nan=False)
            with details.open("x") as stream:
                stream.write(serialized + "\n")
        except (OSError, ValueError) as exc:
            report["execution_failure"] = True
            add(
                report,
                "EXEC.RECEIPT",
                "error",
                str(exc),
                action="Use a fresh writable report path.",
            )
            finish(report, strict)
        else:
            report["details_path"] = str(details.resolve())
    return report


def compact_receipt(report):
    code = report["exit_code"]
    findings = report["diagnostics"]
    result = {
        key: report[key] for key in ("schema_version", "artifact", "exit_code", "plates", "review")
    }
    if "validation_artifact" in report:
        result["validation_artifact"] = report["validation_artifact"]
    colors = report.get("file_check", {}).get("colors", {})
    result.update(
        stage="inspect-final",
        status=("NEEDS_REVIEW", "BLOCKED", "EXECUTION_FAILURE")[code],
        details_path=report.get("details_path"),
        profile_expectations=report.get("profile_expectations", []),
        diagnostics=dict(Counter(d["rule_id"] for d in findings)),
        blockers=[
            d
            for d in findings
            if d["severity"] == "error" or (report["strict"] and d["severity"] == "warning")
        ][:12],
        color_routing={
            key: colors[key] for key in ("used_filaments", "tools", "physical_ams") if key in colors
        },
        dfam_status_counts=dict(Counter(d["status"] for d in findings if "status" in d)),
        next_action=("REVIEW_FINAL_PREVIEW", "RESOLVE_FINDINGS", "CHECK_EXECUTION")[code],
    )
    return result
