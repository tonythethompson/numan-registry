#!/usr/bin/env python3.12
"""Stage 4: Generate a draft registry spec from a discovery report.

Transforms the Stage 3 discovery JSON into a spec file in the exact shape
that add-package.py expects. Includes a _meta provenance block so reviewers
can see what was discovered vs. guessed vs. unresolved.

Usage:
  python scripts/gen_candidate.py --report report.json [--out spec.json]
  python scripts/gen_candidate.py --report report.json --owner override --nu-version ">=0.114.0 <0.115.0"

Output (stdout or --out):
  {"spec": {...add-package.py compatible...}, "_meta": {...provenance...}}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archive_formats import SUPPORTED_ARCHIVE_SUFFIXES
from lint_packages import KNOWN_TRIPLES

# ---------------------------------------------------------------------------
# Target-mapping heuristics
# ---------------------------------------------------------------------------

# Ordered patterns: first match wins for each asset filename.
_TARGET_PATTERNS: list[tuple[str, list[str]]] = [
    ("x86_64-pc-windows-msvc", ["x86_64-pc-windows-msvc", "x86_64-windows", "windows-x86_64", "win-x64", "windows.zip"]),
    ("aarch64-pc-windows-msvc", ["aarch64-pc-windows-msvc", "aarch64-windows", "windows-aarch64", "win-arm64"]),
    ("x86_64-unknown-linux-gnu", ["x86_64-unknown-linux-gnu", "x86_64-linux", "linux-x86_64", "linux-gnu", "linux.tar"]),
    ("aarch64-unknown-linux-gnu", ["aarch64-unknown-linux-gnu", "aarch64-linux", "linux-aarch64", "linux-arm64"]),
    ("x86_64-apple-darwin", ["x86_64-apple-darwin", "x86_64-macos", "macos-x86_64", "darwin-x86_64", "apple-x86_64"]),
    ("aarch64-apple-darwin", ["aarch64-apple-darwin", "aarch64-macos", "macos-aarch64", "darwin-aarch64", "apple-aarch64"]),
]


def _match_target(filename: str) -> str | None:
    """Match an asset filename to a known target triple."""
    lower = filename.lower()
    for triple, patterns in _TARGET_PATTERNS:
        for pattern in patterns:
            if pattern in lower:
                return triple
    return None


def _executable_path(name: str, target: str) -> str:
    """Infer the executable path inside an archive for a plugin."""
    exe_name = name if name.startswith("nu_plugin_") or name.startswith("nu-plugin-") else f"nu_plugin_{name}"
    if "windows" in target:
        return f"{exe_name}.exe"
    return exe_name


# ---------------------------------------------------------------------------
# Spec generation
# ---------------------------------------------------------------------------


def generate_spec(report: dict, *, owner_override: str | None = None,
                  nu_version_override: str | None = None) -> dict:
    """Generate a candidate spec + provenance metadata from a discovery report."""
    facts = report.get("facts", {})
    guesses = report.get("guesses", {})

    owner = owner_override or facts.get("owner")
    name = facts.get("name", "")
    description = facts.get("description", "")
    package_type = facts.get("package_type") or guesses.get("registry_type")
    nu_version = nu_version_override or facts.get("nu_constraint_hint") or "*"
    releases = facts.get("releases", [])

    field_provenance: dict[str, str] = {}
    unresolved: list[str] = []
    warnings: list[str] = []

    if owner_override:
        field_provenance["owner"] = f"CLI override: {owner_override}"
    elif facts.get("owner"):
        field_provenance["owner"] = "github repo owner"
    else:
        unresolved.append("owner not determined; use --owner")

    if nu_version_override:
        field_provenance["nu_version"] = f"CLI override: {nu_version_override}"
    elif facts.get("nu_constraint_hint"):
        field_provenance["nu_version"] = "Cargo.toml nu-plugin dependency version"
    else:
        field_provenance["nu_version"] = "defaulted to * (not declared)"
        warnings.append("nu_version constraint not declared; defaulted to *")

    # Pick the best release (first with assets, or first overall)
    best_release = None
    for rel in releases:
        if rel.get("assets"):
            best_release = rel
            break
    if not best_release and releases:
        best_release = releases[0]

    version = ""
    if best_release:
        tag = best_release.get("tag", "")
        version = tag.lstrip("v")
        field_provenance["version"] = f"release tag {tag}"
    else:
        unresolved.append("version not determined; no releases found")

    # Build artifact block
    repo_url = report.get("source", {}).get("url", "")
    if not repo_url and owner and name:
        repo_url = f"https://github.com/{owner}/{name}"

    if not package_type:
        unresolved.append("package_type not determined; defaulting to plugin — verify manually")
        package_type = "plugin"

    spec: dict = {
        "owner": owner or "TODO",
        "name": name,
        "description": description,
        "repo": repo_url,
        "type": package_type,
        "tags": [package_type, "ci-built"],
        "version": version or "0.0.0",
        "nu_version": nu_version,
    }

    if package_type == "plugin":
        # Binary artifact with targets
        targets: dict[str, dict] = {}
        skipped: list[str] = []
        if best_release:
            for asset in best_release.get("assets", []):
                target = _match_target(asset["name"])
                if target and target in KNOWN_TRIPLES:
                    targets[target] = {
                        "url": asset["url"],
                        "executable_path": _executable_path(name, target),
                    }
                else:
                    skipped.append(asset["name"])
        if skipped:
            warnings.append(f"unmapped assets skipped: {', '.join(skipped)}")
        if not targets:
            unresolved.append("no release assets matched known target triples")
        spec["artifact"] = {"kind": "binary", "targets": targets}

    elif package_type in ("module", "script", "completion"):
        # Archive artifact
        url = ""
        if best_release and best_release.get("assets"):
            url = best_release["assets"][0].get("url", "")
            field_provenance["artifact_url"] = f"first asset from release {best_release.get('tag', '')}"
        if not url:
            unresolved.append("no archive URL found; may need registry-hosted mirror")

        entry = "mod.nu"
        import_mode = "all"  # mod.nu → "all" per add-package.py convention
        spec["artifact"] = {"kind": "archive", "url": url, "entry": entry}
        if package_type == "module":
            spec["activation"] = {"kind": "nu-module", "import": import_mode}

    else:
        unresolved.append(f"unsupported package_type '{package_type}'; cannot generate artifact block")

    unresolved.append("verified_with not populated — run lifecycle-prove")

    return {
        "spec": spec,
        "_meta": {
            "generated_from": "discovery-v1",
            "field_provenance": field_provenance,
            "unresolved": unresolved,
            "warnings": warnings,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: generate draft spec from discovery report")
    parser.add_argument("--report", required=True, help="Path to discovery report JSON (Stage 3 output)")
    parser.add_argument("--out", help="Write candidate to file instead of stdout")
    parser.add_argument("--owner", help="Override the registry owner field")
    parser.add_argument("--nu-version", help="Override the nu_version constraint")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"error: report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != 1:
        print(f"warning: unexpected discovery schema_version {report.get('schema_version')}", file=sys.stderr)

    candidate = generate_spec(report, owner_override=args.owner, nu_version_override=args.nu_version)

    output = json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Candidate spec written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)

    # Print warnings to stderr for visibility
    for w in candidate["_meta"]["warnings"]:
        print(f"  warning: {w}", file=sys.stderr)
    for u in candidate["_meta"]["unresolved"]:
        print(f"  unresolved: {u}", file=sys.stderr)


if __name__ == "__main__":
    main()
