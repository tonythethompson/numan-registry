#!/usr/bin/env python3
"""Fail CI if the repository contains probable private-key material.

This scans git-tracked files only (via `git ls-files`) for:

  1. PEM markers (e.g. "-----BEGIN PRIVATE KEY-----") anywhere.
  2. Filenames matching known private-key output patterns (*.key, *.pem,
     *-private*, *_private_key*) — these should never be tracked; they are
     also .gitignore'd, so a hit here means something was force-added.
  3. A literal-looking base64 value assigned to a private-key-shaped
     identifier (e.g. `priv_b64 = "<44 chars>"`), as opposed to a variable
     reference or a GitHub Actions expression.
  4. `NUMAN_REGISTRY_PRIVATE_KEY` assigned a literal-looking value instead
     of a `${{ secrets.* }}` / `${{ env.* }}` expression or an environment
     variable reference.

This script deliberately does NOT flag the committed public key in
keys/official.pub or any `public_key_b64` field — those are meant to be
public and committed.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_PATH = Path(__file__).resolve()

PEM_MARKER_RE = re.compile(r"-{5}BEGIN [A-Z0-9 ]*PRIVATE KEY-{5}")

PRIVATE_KEY_FILENAME_GLOBS = (
    "*.key",
    "*.pem",
    "*-private",
    "*-private.*",
    "*_private_key*",
)

# A literal (not `${{ ... }}`, not a bare identifier) base64 blob assigned to
# something that looks like a private key variable.
LITERAL_PRIVATE_B64_RE = re.compile(
    r"""priv(?:ate)?_?key\w*(?:_b64)?\s*[:=]\s*["']([A-Za-z0-9+/]{40,64}={0,2})["']""",
    re.IGNORECASE,
)

# NUMAN_REGISTRY_PRIVATE_KEY assigned something that isn't a GitHub Actions
# expression or an env/shell variable reference.
HARDCODED_SECRET_RE = re.compile(
    r"""NUMAN_REGISTRY_PRIVATE_KEY\s*[:=]\s*["']?([^\s"'$][^\n"']{8,})["']?"""
)

ALLOWLIST_MARKER = "secretscan:allow"


def git_tracked_files():
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line for line in out.stdout.splitlines() if line]


def matches_private_filename(path):
    name = path.name
    for pattern in PRIVATE_KEY_FILENAME_GLOBS:
        if path.match(pattern) or Path(name).match(pattern):
            return pattern
    return None


def scan_file_contents(path):
    findings = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        if ALLOWLIST_MARKER in line:
            continue

        if PEM_MARKER_RE.search(line):
            findings.append((lineno, "PEM private-key marker", line.strip()))
            continue

        if "public_key_b64" not in line and "${{" not in line:
            m = LITERAL_PRIVATE_B64_RE.search(line)
            if m:
                findings.append(
                    (lineno, "literal base64 assigned to a private-key-shaped variable", line.strip())
                )
                continue

        if "${{" not in line and "os.environ" not in line and "getenv" not in line:
            m = HARDCODED_SECRET_RE.search(line)
            if m:
                findings.append(
                    (lineno, "NUMAN_REGISTRY_PRIVATE_KEY assigned a literal value", line.strip())
                )

    return findings


def main():
    errors = []

    for path in git_tracked_files():
        if path.resolve() == SELF_PATH:
            continue

        glob_hit = matches_private_filename(path)
        if glob_hit:
            errors.append(f"{path.relative_to(REPO_ROOT)}: tracked file matches private-key filename pattern '{glob_hit}'")
            continue

        for lineno, reason, line in scan_file_contents(path):
            rel = path.relative_to(REPO_ROOT)
            errors.append(f"{rel}:{lineno}: {reason}: {line}")

    if errors:
        print(f"FAIL: secret scan found {len(errors)} probable private-key issue(s):\n")
        for err in errors:
            print(f"  - {err}")
        print(
            "\nIf this is a false positive in documentation, rewrite the example to use "
            "an obviously-fake placeholder (e.g. '<paste your key here>') instead of a "
            "realistic-looking base64 string, or add '# secretscan:allow' to the line."
        )
        return 1

    print("OK: no probable private-key material found in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
