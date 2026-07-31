#!/usr/bin/env python3.12
"""Stage 5: Validation harness for a candidate registry spec.

Orchestrates existing tools (add-package.py, lint_packages.py, validate.py,
lifecycle-prove.py) to download artifacts, compute hashes, lint, and optionally
run the full lifecycle against a real Nu binary.

Usage:
  python scripts/validate_candidate.py --spec spec.json
  python scripts/validate_candidate.py --spec spec.json --prove --numan /path/to/numan --nu /path/to/nu
  python scripts/validate_candidate.py --spec spec.json --out evidence.json

Steps:
  1. add-package.py --spec <spec> --write --index <tmp> --provisional  (download + hash)
  2. lint_packages.py --index <tmp>                                    (structural lint)
  3. validate.py --index <tmp> --skip-signature --skip-artifacts --allow-provisional-lifecycle
  4. lifecycle-prove.py --package owner/name [--numan ...] [--nu ...]  (opt-in via --prove)

Exit 0 if steps 1–3 pass. Step 4 is advisory unless --strict.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _run_script(args: list[str], *, label: str) -> tuple[bool, str]:
    """Run a Python script and capture output. Returns (success, output)."""
    try:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, f"{label}: timed out after 300s"
    except FileNotFoundError as exc:
        return False, f"{label}: {exc}"
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output


def validate_candidate(spec_path: Path, *, prove: bool = False,
                       numan: str | None = None, nu: str | None = None,
                       strict: bool = False) -> dict:
    """Run all validation steps and return an evidence report."""
    checks: list[dict] = []
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))

    # Handle both raw spec and wrapped {spec, _meta} format
    if "spec" in spec_data and "_meta" in spec_data:
        spec_data = spec_data["spec"]

    owner = spec_data.get("owner", "unknown")
    name = spec_data.get("name", "unknown")
    package_id = f"{owner}/{name}"

    with tempfile.TemporaryDirectory(prefix="numan-validate-") as tmp:
        tmp_index = Path(tmp) / "index.json"
        # add-package.py expects top-level spec fields, not the {spec, _meta} wrapper.
        effective_spec = Path(tmp) / "spec.json"
        effective_spec.write_text(
            json.dumps(spec_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Seed a schema-valid index for add-package.py to merge into
        tmp_index.write_text(json.dumps({
            "schema_version": 1,
            "updated_at": "1970-01-01T00:00:00Z",
            "packages": [],
        }), encoding="utf-8")

        # Step 1: Download + hash via add-package.py
        ok, output = _run_script(
            [str(SCRIPTS / "add-package.py"),
             "--spec", str(effective_spec),
             "--write", "--index", str(tmp_index),
             "--provisional"],
            label="add-package",
        )
        targets_count = 0
        if ok:
            # Count targets from the resulting index
            try:
                idx = json.loads(tmp_index.read_text(encoding="utf-8"))
                for pkg in idx.get("packages", []):
                    for ver in pkg.get("versions", []):
                        artifact = ver.get("artifact", {})
                        if artifact.get("kind") == "binary":
                            targets_count += len(artifact.get("targets", {}))
                        else:
                            targets_count += 1
            except (OSError, json.JSONDecodeError) as exc:
                print(f"warning: cannot read temporary index: {exc}", file=sys.stderr)
        checks.append({
            "name": "download_and_hash",
            "status": "pass" if ok else "fail",
            "targets": targets_count,
            "detail": "" if ok else output[-500:],
        })

        # Step 2: Lint
        ok_lint, output_lint = _run_script(
            [str(SCRIPTS / "lint_packages.py"), "--index", str(tmp_index)],
            label="lint",
        )
        lint_errors = []
        if not ok_lint:
            # lint_packages.py reports failures as a FAIL header followed by
            # indented bullet diagnostics; preserve those actionable messages.
            lines = output_lint.splitlines()
            capturing = False
            for line in lines:
                if line.strip().startswith("FAIL:"):
                    capturing = True
                if capturing:
                    lint_errors.append(line)
            if not lint_errors:
                lint_errors = lines
            # Keep the evidence bounded while retaining the end of diagnostics.
            joined = "\n".join(lint_errors)
            lint_errors = joined[-2000:].splitlines()
        checks.append({
            "name": "lint",
            "status": "pass" if ok_lint else "fail",
            "errors": lint_errors,
        })

        # Step 3: Schema validation
        ok_schema, output_schema = _run_script(
            [str(SCRIPTS / "validate.py"),
             "--index", str(tmp_index),
             "--skip-signature", "--skip-artifacts",
             "--allow-provisional-lifecycle"],
            label="validate",
        )
        checks.append({
            "name": "schema",
            "status": "pass" if ok_schema else "fail",
            "detail": "" if ok_schema else output_schema[-500:],
        })

    # Step 4: Lifecycle (opt-in)
    # NOTE: lifecycle-prove runs against the configured production registry,
    # not the candidate index. For new packages not yet staged/published,
    # this step will fail with "package not found" — that is expected.
    # Use --prove only after the package is in the live registry.
    if prove:
        lifecycle_args = [
            str(SCRIPTS / "lifecycle-prove.py"),
            "--package", package_id,
        ]
        if numan:
            lifecycle_args += ["--numan", numan]
        if nu:
            lifecycle_args += ["--nu", nu]
        ok_life, output_life = _run_script(lifecycle_args, label="lifecycle-prove")
        checks.append({
            "name": "lifecycle",
            "status": "pass" if ok_life else "fail",
            "detail": "" if ok_life else (
                "lifecycle-prove runs against the live registry; "
                "new packages must be staged first. " + output_life[-400:]
            ),
        })
    else:
        checks.append({
            "name": "lifecycle",
            "status": "skip",
            "detail": "not requested (use --prove)",
        })

    # Overall status
    core_checks = [c for c in checks if c["name"] != "lifecycle"]
    core_pass = all(c["status"] == "pass" for c in core_checks)
    lifecycle_check = next((c for c in checks if c["name"] == "lifecycle"), None)

    if strict and lifecycle_check and lifecycle_check["status"] == "fail":
        overall = "fail"
    elif core_pass:
        overall = "pass"
    else:
        overall = "fail"

    # Human summary
    parts = []
    dl = next(c for c in checks if c["name"] == "download_and_hash")
    if dl["status"] == "pass":
        parts.append(f"{dl['targets']} artifact(s) downloaded and hashed.")
    else:
        parts.append("Download/hash FAILED.")
    lint_c = next(c for c in checks if c["name"] == "lint")
    parts.append("Lint clean." if lint_c["status"] == "pass" else "Lint FAILED.")
    schema_c = next(c for c in checks if c["name"] == "schema")
    parts.append("Schema valid." if schema_c["status"] == "pass" else "Schema FAILED.")
    if lifecycle_check and lifecycle_check["status"] == "pass":
        parts.append("Lifecycle passed.")
    elif lifecycle_check and lifecycle_check["status"] == "fail":
        parts.append("Lifecycle FAILED.")

    return {
        "schema_version": 1,
        "spec_file": str(spec_path),
        "package_id": package_id,
        "checks": checks,
        "overall": overall,
        "human_summary": " ".join(parts),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 5: validate a candidate spec")
    parser.add_argument("--spec", required=True, help="Path to spec JSON (Stage 4 output or raw spec)")
    parser.add_argument("--prove", action="store_true", help="Run lifecycle-prove (requires numan + nu)")
    parser.add_argument("--numan", help="Path to numan binary (for --prove)")
    parser.add_argument("--nu", help="Path to nu binary (for --prove)")
    parser.add_argument("--strict", action="store_true", help="Fail if lifecycle fails (with --prove)")
    parser.add_argument("--out", help="Write evidence JSON to file instead of stdout")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    evidence = validate_candidate(
        spec_path,
        prove=args.prove,
        numan=args.numan,
        nu=args.nu,
        strict=args.strict,
    )

    output = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Evidence written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)

    print(f"\n  {evidence['human_summary']}", file=sys.stderr)
    sys.exit(0 if evidence["overall"] == "pass" else 1)


if __name__ == "__main__":
    main()
