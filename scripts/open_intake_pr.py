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
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from gh_helpers import gh_json, gh_run

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


def _write_json_atomic(path: Path, data: dict) -> None:
    """Write JSON atomically, keeping a .bak copy of the previous file.

    Uses a sibling temporary file and os.replace so readers never see a
    partially-written file. A .bak copy of the previous contents is kept for
    recovery. This is a maintainer-run tool, so advisory file locking is not
    implemented; the atomic replace plus backup gives the required safety.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if path.is_file():
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _current_branch() -> str:
    """Return the name of the currently checked-out branch."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _is_worktree_dirty() -> bool:
    """Return True if the git worktree has uncommitted changes.

    Fail-closed: if ``git status`` itself fails (non-zero exit), treat the
    worktree as dirty so we do not risk mutating an unknown state.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return True
    return result.stdout.strip() != ""


def _cleanup_intake_branch(branch: str, original_branch: str,
                           mutated_paths: list[Path]) -> None:
    """Best-effort cleanup of a partially created intake branch.

    Restores tracked files to their original-branch state, removes any
    untracked files created during the failed intake, switches back to the
    original branch, and deletes the intake branch.
    """
    try:
        tracked = [str(p) for p in mutated_paths if p.is_file()]
        if tracked:
            subprocess.run(
                ["git", "checkout", "--", *tracked],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
        for path in mutated_paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                print(f"warning: could not remove {path}: {exc}", file=sys.stderr)
        subprocess.run(
            ["git", "checkout", original_branch],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  cleaned up intake branch {branch}", file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print(
            f"warning: could not clean up intake branch {branch}: {exc}",
            file=sys.stderr,
        )
        remaining = [str(p) for p in mutated_paths if p.exists()]
        if remaining:
            print(
                f"warning: these paths may still be modified: {', '.join(remaining)}",
                file=sys.stderr,
            )


def _update_intake_state(owner: str, name: str, version: str, pkg_type: str,
                         spec_path: str, repo: str, *, dry_run: bool) -> None:
    """Append or refresh an entry in docs/intake-state.json ready[]."""
    if dry_run:
        print(f"  [dry-run] would update {INTAKE_STATE_PATH}", file=sys.stderr)
        return

    if not INTAKE_STATE_PATH.is_file():
        print(f"warning: {INTAKE_STATE_PATH} not found; creating fresh", file=sys.stderr)
        state: dict = {"schema_version": 1, "ready": []}
    else:
        state = json.loads(INTAKE_STATE_PATH.read_text(encoding="utf-8"))

    core_fields = {
        "id": f"{owner}/{name}",
        "name": name,
        "owner": owner,
        "type": pkg_type,
        "version": version,
        "repo": repo,
        "spec": spec_path,
    }
    # Keep one entry per package, but refresh it when a new version is intaken.
    # Preserve optional metadata (pr, note, outreach, platforms, etc.) across
    # refreshes. Platforms is preserved because maintainers often hand-edit it
    # to a descriptive value after the initial intake.
    ready = state.setdefault("ready", [])
    for index, existing in enumerate(ready):
        if existing.get("id") == core_fields["id"]:
            preserved = {k: v for k, v in existing.items() if k not in core_fields}
            ready[index] = {**core_fields, **preserved}
            break
    else:
        ready.append({**core_fields, "platforms": "see spec targets"})
    _write_json_atomic(INTAKE_STATE_PATH, state)


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


def _load_inputs(spec_path: Path, evidence_path: Path) -> tuple[dict, dict, dict]:
    """Load and unwrap the spec (dropping the {spec, _meta} wrapper) and evidence."""
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    if "spec" in spec_data and "_meta" in spec_data:
        spec = spec_data["spec"]
    else:
        spec = spec_data
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    return spec_data, spec, evidence


def _guard_evidence(evidence: dict) -> None:
    """Refuse to proceed when validation evidence did not pass."""
    if evidence.get("overall") not in ("pass", "partial"):
        print(f"error: evidence overall is '{evidence.get('overall')}'; "
              "refusing to open PR for a failing candidate", file=sys.stderr)
        sys.exit(1)


def _print_intake_header(owner: str, name: str, version: str, branch: str,
                         spec_filename: str, *, dry_run: bool) -> None:
    """Print the intake summary banner."""
    print(f"Intake: {owner}/{name} v{version}", file=sys.stderr)
    print(f"  Branch: {branch}", file=sys.stderr)
    print(f"  Spec:   specs/{spec_filename}", file=sys.stderr)
    if dry_run:
        print("  Mode:   DRY RUN (no mutations)", file=sys.stderr)
    print("", file=sys.stderr)


def _prepare_push_branch() -> str:
    """Return the current branch for cleanup, refusing dirty/detached worktrees."""
    if _is_worktree_dirty():
        print(
            "error: refusing to create intake branch with a dirty worktree; "
            "commit or stash changes first",
            file=sys.stderr,
        )
        sys.exit(1)
    branch = _current_branch()
    if not branch:
        print(
            "error: refusing to create intake branch from a detached HEAD; "
            "check out a branch first",
            file=sys.stderr,
        )
        sys.exit(1)
    return branch


def _stage_create_branch(branch: str, *, dry_run: bool) -> None:
    """Create the intake branch before any tracked files are mutated."""
    if dry_run:
        print(f"  [dry-run] would: git checkout -b {branch}", file=sys.stderr)
    else:
        _run(["git", "checkout", "-b", branch])


def _stage_copy_spec(dest_spec: Path, spec_data: dict, spec_filename: str, *, dry_run: bool) -> None:
    """Copy the spec (with _meta provenance) to specs/."""
    if dry_run:
        print(f"  [dry-run] would copy spec → specs/{spec_filename}", file=sys.stderr)
    else:
        dest_spec.write_text(
            json.dumps(spec_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def _stage_merge_into_index(spec_path: Path, spec: dict, spec_filename: str,
                             deferral_reason: str = "",
                             *, dry_run: bool) -> None:
    """Run add-package.py --write with an unwrapped spec copy.

    A nonblank deferral_reason means Stage 5 evidence deferred lifecycle-prove;
    the index entry must retain that reason and go in as provisional. An empty
    deferral_reason means evidence passed fully (verified_with present) — the
    entry is proven and add-package.py must run without --provisional, since
    it rejects --provisional together with verified_with.

    add-package.py expects bare spec fields (owner, name, …) at the top level,
    not the {spec, _meta} wrapper — write an unwrapped copy outside the repo
    and remove it even if add-package.py fails.
    """
    if dry_run:
        effective_spec_for_add = spec_path
        bare_tmp_dir: Path | None = None
    else:
        bare_tmp_dir = Path(tempfile.mkdtemp(prefix="intake-bare-"))
        effective_spec_for_add = bare_tmp_dir / spec_filename
        effective_spec_for_add.write_text(
            json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    command = [sys.executable, str(SCRIPTS / "add-package.py"),
               "--spec", str(effective_spec_for_add),
               "--write", "--index", str(INDEX_PATH)]
    if deferral_reason.strip():
        command += ["--provisional", "--deferral-reason", deferral_reason]
    try:
        _run(command, dry_run=dry_run)
    finally:
        if bare_tmp_dir is not None:
            shutil.rmtree(bare_tmp_dir, ignore_errors=True)


def _stage_lint_and_validate(*, dry_run: bool) -> None:
    """Run the Stage 2 lint + schema validation gates."""
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


def _stage_refresh_docs(*, dry_run: bool) -> None:
    """Refresh docs/intake-candidates.md (best-effort)."""
    _run(
        [sys.executable, str(SCRIPTS / "sync-intake-candidates.py")],
        dry_run=dry_run,
        check=False,
    )


def _stage_commit_and_push(owner: str, name: str, version: str, branch: str,
                           dest_spec: Path, *, dry_run: bool) -> None:
    """Commit the intake and push the branch (or print what would happen)."""
    add_paths = [
        str(dest_spec),
        str(INDEX_PATH),
        str(INTAKE_STATE_PATH),
        str(REPO_ROOT / "docs" / "intake-candidates.md"),
    ]
    if dry_run:
        print(f"  [dry-run] would: git add {' '.join(add_paths)}", file=sys.stderr)
        print(f"  [dry-run] would: git commit -m 'Intake {owner}/{name} v{version}'", file=sys.stderr)
        print(f"  [dry-run] would: git push origin {branch}", file=sys.stderr)
    else:
        _run(["git", "add", *add_paths])
        _run(["git", "commit", "-m", f"Intake {owner}/{name} v{version}"])
        _run(["git", "push", "origin", branch])


def _reconcile_failed_pr_create(owner: str, name: str, version: str) -> None:
    """Reconcile the pushed intake branch after a failed ``gh pr create``.

    _stage_commit_and_push pushed ``intake/...`` before this runs, so a failed
    gh pr create would otherwise leave an orphaned remote branch. Look the
    branch up in the PR list: if a PR exists (created before a timeout, or a
    re-run of the same intake), keep the branch and report the URL; if we can
    prove no PR exists, delete the remote ref. When the existence check itself
    fails, keep the branch and tell the operator — never delete on an unknown
    state, because a just-created PR would lose its head branch.
    """
    branch = _branch_name(owner, name, version)
    existing = gh_json([
        "pr", "list", "--head", branch, "--state", "all", "--json", "number,url",
    ])
    if isinstance(existing, list) and existing:
        entry = existing[0]
        url = entry.get("url") if isinstance(entry, dict) else None
        if url:
            print(f"warning: PR for '{branch}' may already exist: {url}; "
                  f"remote branch kept", file=sys.stderr)
        else:
            print(f"warning: PR for '{branch}' may already exist (URL unavailable); "
                  f"remote branch kept — check the PR list manually", file=sys.stderr)
        return
    if not isinstance(existing, list):
        print(f"warning: could not confirm whether a PR exists for '{branch}'; "
              f"remote branch kept — check manually", file=sys.stderr)
        return
    print(f"warning: no PR exists for pushed branch '{branch}'; deleting remote ref", file=sys.stderr)
    delete_result = _run(["git", "push", "origin", "--delete", branch], check=False)
    if delete_result is not None and delete_result.returncode != 0:
        print(f"warning: could not delete remote branch '{branch}': "
              f"{delete_result.stderr.strip()}", file=sys.stderr)


def _stage_open_pr(owner: str, name: str, version: str, spec: dict,
                   evidence: dict, *, dry_run: bool, auto_merge: bool = False) -> None:
    """Open the intake PR with a generated body (or print a preview)."""
    pr_body = _generate_pr_body(spec, evidence)
    branch = _branch_name(owner, name, version)
    if dry_run:
        print(f"  [dry-run] would: gh pr create --title 'Intake: {owner}/{name} v{version}'", file=sys.stderr)
        if auto_merge:
            print(f"  [dry-run] would: gh pr merge {branch} --auto --squash", file=sys.stderr)
        print("\n--- PR body preview ---", file=sys.stderr)
        print(pr_body, file=sys.stderr)
    else:
        # gh pr create is mutating, so unlike the fail-soft gh_json/gh_text
        # paths it must fail closed: any non-zero exit aborts the intake.
        result = gh_run([
            "pr", "create",
            "--title", f"Intake: {owner}/{name} v{version}",
            "--body", pr_body,
            "--base", "main",
        ])
        if result is None or result.returncode != 0:
            _reconcile_failed_pr_create(owner, name, version)
            print("error: gh pr create failed", file=sys.stderr)
            if result is not None and result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)

        if auto_merge:
            pr_target = result.stdout.strip() if (result is not None and result.stdout.strip()) else branch
            merge_result = gh_run(["pr", "merge", pr_target, "--auto", "--squash"])
            if merge_result is not None and merge_result.returncode != 0:
                print("warning: failed to enable auto-merge on PR", file=sys.stderr)


def open_intake_pr(spec_path: Path, evidence_path: Path, *, push: bool = False, auto_merge: bool = False) -> None:
    """Main orchestration: assemble and optionally open the PR."""
    dry_run = not push

    spec_data, spec, evidence = _load_inputs(spec_path, evidence_path)
    _guard_evidence(evidence)
    deferral_reason = evidence.get("lifecycle_deferral", {}).get("reason", "")

    owner = spec.get("owner", "unknown")
    name = spec.get("name", "unknown")
    version = spec.get("version", "0.0.0")
    pkg_type = spec.get("type", "plugin")
    repo = spec.get("repo", "")

    branch = _branch_name(owner, name, version)
    spec_filename = _spec_filename(owner, name, version)
    dest_spec = SPECS_DIR / spec_filename
    mutated_paths = [
        dest_spec,
        INDEX_PATH,
        INTAKE_STATE_PATH,
        REPO_ROOT / "docs" / "intake-candidates.md",
        INTAKE_STATE_PATH.with_suffix(INTAKE_STATE_PATH.suffix + ".bak"),
    ]

    _print_intake_header(owner, name, version, branch, spec_filename, dry_run=dry_run)

    original_branch: str | None = None
    if push:
        original_branch = _prepare_push_branch()

    try:
        _stage_create_branch(branch, dry_run=dry_run)
        _stage_copy_spec(dest_spec, spec_data, spec_filename, dry_run=dry_run)
        _stage_merge_into_index(
            spec_path, spec, spec_filename, deferral_reason, dry_run=dry_run
        )
        _stage_lint_and_validate(dry_run=dry_run)
        _update_intake_state(
            owner, name, version, pkg_type, f"specs/{spec_filename}", repo,
            dry_run=dry_run,
        )
        _stage_refresh_docs(dry_run=dry_run)
        _stage_commit_and_push(owner, name, version, branch, dest_spec, dry_run=dry_run)
        _stage_open_pr(owner, name, version, spec, evidence, dry_run=dry_run, auto_merge=auto_merge)
    except BaseException:
        if push and original_branch is not None:
            _cleanup_intake_branch(branch, original_branch, mutated_paths)
        raise

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
    parser.add_argument("--auto-merge", action="store_true",
                        help="Enable GitHub auto-merge on the created PR")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    evidence_path = Path(args.evidence)

    if not spec_path.is_file():
        print(f"error: spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)
    if not evidence_path.is_file():
        print(f"error: evidence not found: {evidence_path}", file=sys.stderr)
        sys.exit(1)

    open_intake_pr(spec_path, evidence_path, push=args.push, auto_merge=args.auto_merge)


if __name__ == "__main__":
    main()
