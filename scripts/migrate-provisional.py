#!/usr/bin/env python3
"""One-time migration: backfill evidence_tier/deferral_reason for pre-reform entries.

For any activatable version entry (type == "plugin", or any entry with an
"activation" block) that lacks verified_with and doesn't already declare an
evidence_tier, stamps evidence_tier: "provisional" and deferral_reason:
"pre-reform provisional intake". Entries that already have an evidence_tier
are left untouched, so the script is safe to re-run (idempotent).

Usage:
  python scripts/migrate-provisional.py                 # dry run, reports what would change
  python scripts/migrate-provisional.py --write          # applies changes to --index
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "registry" / "index.json"
DEFERRAL_REASON = "pre-reform provisional intake"


def needs_migration(pkg: dict, version: object) -> bool:
    """Whether a version entry should be backfilled with a provisional evidence tier."""
    if not isinstance(version, dict):
        return False
    if "evidence_tier" in version:
        return False
    if version.get("verified_with"):
        return False
    return pkg.get("type") == "plugin" or "activation" in version


def migrate_index(index: dict) -> list[str]:
    """Backfill evidence_tier/deferral_reason on qualifying entries in place.

    Returns:
        list[str]: Labels (owner/name@version) of the entries touched.
    """
    touched: list[str] = []
    for pkg in index.get("packages", []):
        if not isinstance(pkg, dict):
            continue
        pkg_id = pkg.get("id") or {}
        label_base = f"{pkg_id.get('owner', '?')}/{pkg_id.get('name', '?')}"
        for version in pkg.get("versions", []):
            if not needs_migration(pkg, version):
                continue
            version["evidence_tier"] = "provisional"
            version["deferral_reason"] = DEFERRAL_REASON
            touched.append(f"{label_base}@{version.get('version', '?')}")
    return touched


def main(argv: list[str] | None = None) -> int:
    """Report or apply the provisional-tier backfill against a registry index."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes back to --index instead of just reporting",
    )
    args = parser.parse_args(argv)

    index = json.loads(args.index.read_text(encoding="utf-8"))
    touched = migrate_index(index)

    if not touched:
        print("OK: no entries needed migration")
        return 0

    verb = "Migrated" if args.write else "Would migrate"
    plural = "y" if len(touched) == 1 else "ies"
    print(f"{verb} {len(touched)} version entr{plural}:", file=sys.stderr)
    for label in touched:
        print(f"  - {label}", file=sys.stderr)

    if not args.write:
        print("\nRe-run with --write to apply.", file=sys.stderr)
        return 0

    args.index.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.index}. Review the diff, then run scripts/lint_packages.py before committing.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
