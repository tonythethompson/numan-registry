#!/usr/bin/env python3.12
"""Stage 6: Open a registry intake PR from a validated spec + evidence.

Assembles a PR branch with the spec, index update, intake-state entry, and
evidence summary. Never signs, never pushes to main.

Usage:
  python scripts/open_intake_pr.py --spec spec.json --evidence evidence.json --dry-run
  python scripts/open_intake_pr.py --spec spec.json --evidence evidence.json --push

Safety:
  --dry-run (default): prints what would happen, no git/gh mutations.
  --push: creates branch, commits, pushes, and opens a PR via gh.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SPECS_DIR = REPO_ROOT / "specs"
INDEX_PATH = REPO_ROOT / "registry" / "index.json"
INTAKE_STATE_PATH = REPO_ROOT / "docs" / "intake-state.json"


def _run(cmd: list[str], *, check: bool = True, dry_run: bool = False) -> subprocess.CompletedProcess | None:
    """Run a command, optionally in dry-run mode (print only)."""
    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}", file=sys.stderr)
        return None
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"error: command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def _sanitize(value: str) -> str:
    """Sanitize a value for use in filenames and branch names."""
    return re.sub(r"[^a-zA-Z0-9._-]", "-", value).strip("-") or "unknown"


def _spec_filename(owner: str, name: str, version: str) -> str:
    """Generate the canonical spec filename."""
    return f"{_sanitize(owner)}-{_sanitize(name)}-{_sanitize(version)}.json"


def _branch_name(owner: str, name: str, version: str) -> str:
    """Generate the intake branch name."""
    return f"intake/{_sanitize(owner)}-{_sanitize(name)}-{_sanitize(version)}"


def _update_intake_state(owner: str, name: str, version: str, pkg_type: str,
                         spec_path: str, repo: str, dry_run: bool) -> None:
    """Append an entry to docs/intake-state.json ready[]."""
    if dry_run:
        print(f"  [dry-run] would update {INTAKE_STATE_PATH}", file=sys.stderr)
        return

    if not INTAKE_STATE_PATH.is_file():
        print(f"warning: {INTAKE_STATE_PATH} not found; creating fresh", file=sys.stderr)
        state: dict = {"ready": []}
    else:
        state = json.loads(INTAKE_STATE_PATH.read_text(encoding="utf-8"))
    entry = {
        "id": f"{owner}/{name}",
        "name": name,
        "owner": owner,
        "type": pkg_type,
        "version": version,
        "platforms": "see spec targets",
        "repo": repo,
        "spec": spec_path,
    }
    # Keep one entry per package, but refresh it when a new version is intaken.
    ready = state.setdefault("ready", [])
    for index, existing in enumerate(ready):
        if existing.get("id") == entry["id"]:
            ready[index] = entry
            break
    else:
        ready.append(entry)
    INTAKE_STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _generate_pr_body(spec: dict, evidence: dict) -> str:
    """Generate the PR body markdown."""
    owner = spec.get("owner", "?")
    name = spec.get("name", "?")
    version = spec.get("version", "?")
    pkg_type = spec.get("type", "?")
    nu_version = spec.get("nu_version", "?")
    repo = spec.get("repo", "")

    # Count targets
    artifact = spec.get("artifact", {})
    if artifact.get("kind") == "binary":
        target_count = len(artifact.get("targets", {}))
        target_names = ", ".join(artifact.get("targets", {}).keys())
    else:
        target_count = 1
        target_names = "archive"

    # Lifecycle status
    lifecycle_status = "not run"
    for check in evidence.get("checks", []):
        if check.get("name") == "lifecycle":
            lifecycle_status = check.get("status", "unknown")
            break

    overall = evidence.get("overall", "unknown")

    lines = [
        f"## Intake: {owner}/{name} v{version}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Type | {pkg_type} |",
        f"| Nu constraint | {nu_version} |",
        f"| Targets | {target_count} ({target_names}) |",
        f"| Validation | {overall} |",
        f"| Lifecycle | {lifecycle_status} |",
        f"| Repo | {repo} |",
        "",
        "### Evidence",
        "",
        evidence.get("human_summary", "No summary available."),
        "",
        "### Checklist",
        "",
        "- [ ] Human reviewed spec fields",
        "- [ ] License compatible",
        "- [ ] No source-build consent needed",
        "- [ ] Artifact URLs are stable (release assets, not CI ephemeral)",
        "",
        "---",
        f"*Generated by `scripts/open_intake_pr.py` on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
    ]
    return "\n".join(lines)


def open_intake_pr(spec_path: Path, evidence_path: Path, *, push: bool = False) -> None:
    """Main orchestration: assemble and optionally open the PR."""
    dry_run = not push

    # Load inputs
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    if "spec" in spec_data and "_meta" in spec_data:
        spec = spec_data["spec"]
    else:
        spec = spec_data

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    # Gate: refuse to open a PR if validation did not pass
    if evidence.get("overall") not in ("pass", "partial"):
        print(f"error: evidence overall is '{evidence.get('overall')}'; "
              "refusing to open PR for a failing candidate", file=sys.stderr)
        sys.exit(1)

    owner = spec.get("owner", "unknown")
    name = spec.get("name", "unknown")
    version = spec.get("version", "0.0.0")
    pkg_type = spec.get("type", "plugin")
    repo = spec.get("repo", "")

    branch = _branch_name(owner, name, version)
    spec_filename = _spec_filename(owner, name, version)
    dest_spec = SPECS_DIR / spec_filename

    print(f"Intake: {owner}/{name} v{version}", file=sys.stderr)
    print(f"  Branch: {branch}", file=sys.stderr)
    print(f"  Spec:   specs/{spec_filename}", file=sys.stderr)
    if dry_run:
        print("  Mode:   DRY RUN (no mutations)", file=sys.stderr)
    print("", file=sys.stderr)

    # Create the branch before any tracked files are mutated.
    if dry_run:
        print(f"  [dry-run] would: git checkout -b {branch}", file=sys.stderr)
    else:
        _run(["git", "checkout", "-b", branch])

    # Step 1: Copy spec to specs/ (preserve _meta provenance for reviewers)
    if dry_run:
        print(f"  [dry-run] would copy spec → specs/{spec_filename}", file=sys.stderr)
    else:
        dest_spec.write_text(json.dumps(spec_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Step 2: Run add-package.py --write to merge into index.
    # add-package.py expects bare spec fields (owner, name, …) at the top level,
    # not the {spec, _meta} wrapper — write an unwrapped copy for it.
    if dry_run:
        effective_spec_for_add = spec_path
    else:
        effective_spec_for_add = SPECS_DIR / f".bare-{spec_filename}"
        effective_spec_for_add.write_text(
            json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    _run(
        [sys.executable, str(SCRIPTS / "add-package.py"),
         "--spec", str(effective_spec_for_add),
         "--write", "--index", str(INDEX_PATH), "--provisional"],
        dry_run=dry_run,
    )
    # Clean up the temporary bare spec
    if not dry_run and effective_spec_for_add.exists():
        effective_spec_for_add.unlink()

    # Step 3: Lint + validate gates
    _run(
        [sys.executable, str(SCRIPTS / "lint_packages.py"), "--index", str(INDEX_PATH)],
        dry_run=dry_run,
    )
    _run(
        [sys.executable, str(SCRIPTS / "validate.py"),
         "--index", str(INDEX_PATH),
         "--skip-signature", "--skip-artifacts", "--allow-provisional-lifecycle"],
        dry_run=dry_run,
    )

    # Step 4: Update intake-state.json
    _update_intake_state(owner, name, version, pkg_type, f"specs/{spec_filename}", repo, dry_run)

    # Step 5: Refresh intake-candidates doc
    _run(
        [sys.executable, str(SCRIPTS / "sync-intake-candidates.py")],
        dry_run=dry_run,
        check=False,
    )

    # Step 6: Commit and push
    if dry_run:
        print(f"  [dry-run] would: git add specs/{spec_filename} registry/index.json docs/", file=sys.stderr)
        print(f"  [dry-run] would: git commit -m 'Intake {owner}/{name} v{version}'", file=sys.stderr)
        print(f"  [dry-run] would: git push origin {branch}", file=sys.stderr)
    else:
        _run(["git", "add", str(dest_spec), str(INDEX_PATH), str(INTAKE_STATE_PATH),
              str(REPO_ROOT / "docs" / "intake-candidates.md")])
        _run(["git", "commit", "-m", f"Intake {owner}/{name} v{version}"])
        _run(["git", "push", "origin", branch])

    # Step 7: Open PR
    pr_body = _generate_pr_body(spec, evidence)
    if dry_run:
        print(f"  [dry-run] would: gh pr create --title 'Intake: {owner}/{name} v{version}'", file=sys.stderr)
        print("\n--- PR body preview ---", file=sys.stderr)
        print(pr_body, file=sys.stderr)
    else:
        _run([
            "gh", "pr", "create",
            "--title", f"Intake: {owner}/{name} v{version}",
            "--body", pr_body,
            "--base", "main",
        ])

    print("\nDone." if not dry_run else "\nDry run complete. Use --push to execute.", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 6: open a registry intake PR")
    parser.add_argument("--spec", required=True, help="Path to spec JSON")
    parser.add_argument("--evidence", required=True, help="Path to evidence JSON (Stage 5 output)")
    parser.add_argument("--push", action="store_true",
                        help="Actually create branch + PR (default is dry-run)")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    evidence_path = Path(args.evidence)

    if not spec_path.is_file():
        print(f"error: spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)
    if not evidence_path.is_file():
        print(f"error: evidence not found: {evidence_path}", file=sys.stderr)
        sys.exit(1)

    open_intake_pr(spec_path, evidence_path, push=args.push)


if __name__ == "__main__":
    main()
