#!/usr/bin/env python3.12
"""Shared `gh` CLI wrappers for registry tooling.

sync-intake-candidates.py, discover.py, open_intake_pr.py, and
validate_candidate.py shell out to the GitHub CLI; the wrappers live here so
the scripts do not duplicate the same invocation plumbing (binary name, repo
cwd, timeout) or output parsing (CodeFactor issue #40).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def gh_run(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a `gh` command and return its full result.

    ``None`` covers gh missing from PATH or a hung invocation exceeding the
    timeout. The command runs with ``check=False``: a non-zero exit is
    reported in the returned ``returncode`` so fail-closed callers (e.g.
    mutating commands like ``gh pr create``) can inspect stderr, while
    fail-soft callers (``gh_json``/``gh_text``) treat it as failure.
    """
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def gh_json(args: list[str]) -> object | None:
    """Run a gh CLI command and parse JSON output.

    Returns ``None`` when gh is unavailable, the command fails, or stdout is
    not parseable JSON.
    """
    out = gh_run(args)
    if out is None or out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def gh_text(args: list[str]) -> str | None:
    """Run a gh CLI command and return stripped text output.

    Returns ``None`` when gh is unavailable or the command fails.
    """
    out = gh_run(args)
    if out is None or out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None
