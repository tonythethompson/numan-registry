#!/usr/bin/env python3.12
"""Shared `gh` CLI wrappers for registry tooling.

Both sync-intake-candidates.py and discover.py shell out to the GitHub CLI
and parse its output; the wrappers live here so the two scripts do not
duplicate the same helpers (CodeFactor issue #40).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a `gh` command, returning its result or ``None`` if gh is missing."""
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None


def gh_json(args: list[str]) -> object | None:
    """Run a gh CLI command and parse JSON output.

    Returns ``None`` when gh is unavailable, the command fails, or stdout is
    not parseable JSON.
    """
    out = _run_gh(args)
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
    out = _run_gh(args)
    if out is None or out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None
