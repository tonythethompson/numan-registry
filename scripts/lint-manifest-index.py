#!/usr/bin/env python3
"""Compare numan-plugins manifest Nu constraints to registry index entries.

Stage 2 intake gate (next-steps C3 / strategy audit §5): when a plugin appears
in both `numan-plugins/manifest.json` `active[]` and `registry/index.json` at
the same owner/name/version, their `nu_version` strings must match exactly.

Does not fail when a manifest plugin is not yet in the index (promotion lag).
Does not fail when an active entry lacks `nu_version` (unchecked; skip compare).
Does fail when both are known and the constraints disagree.

Usage:
  python3 scripts/lint-manifest-index.py
  python3 scripts/lint-manifest-index.py \\
      --index registry/index.json \\
      --manifest /path/to/numan-plugins/manifest.json
  python3 scripts/lint-manifest-index.py --manifest-url https://.../manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/tonythethompson/numan-plugins/"
    "master/manifest.json"
)
DEFAULT_INDEX = Path("registry/index.json")


def load_json_path(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json_url(url: str) -> object:
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"manifest URL must be http(s), got {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": "numan-registry-lint"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — scheme checked above
        return json.loads(resp.read().decode("utf-8"))


def package_key(owner: str, name: str) -> str:
    return f"{owner}/{name}"


def require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object, got {type(value).__name__}")
    return value


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array, got {type(value).__name__}")
    return value


def index_version_map(index: dict) -> dict[tuple[str, str, str], str]:
    """Map (owner, name, version) -> nu_version from the registry index."""
    out: dict[tuple[str, str, str], str] = {}
    packages = require_list(index.get("packages", []), "index.packages")
    for i, pkg in enumerate(packages):
        pkg_obj = require_object(pkg, f"index.packages[{i}]")
        ident = pkg_obj.get("id") or {}
        ident_obj = require_object(ident, f"index.packages[{i}].id")
        owner = ident_obj.get("owner")
        name = ident_obj.get("name")
        if not isinstance(owner, str) or not owner or not isinstance(name, str) or not name:
            continue
        versions = require_list(pkg_obj.get("versions", []), f"index.packages[{i}].versions")
        for j, ver in enumerate(versions):
            ver_obj = require_object(ver, f"index.packages[{i}].versions[{j}]")
            version = ver_obj.get("version")
            nu_version = ver_obj.get("nu_version")
            if not isinstance(version, str) or not version:
                continue
            if not isinstance(nu_version, str) or not nu_version:
                continue
            out[(owner, name, version)] = nu_version
    return out


def manifest_active_entries(manifest: dict) -> list:
    return require_list(manifest.get("active"), "manifest.active")


def compare(
    manifest: dict,
    index: dict,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (errors, missing_from_index, checked, unchecked)."""
    versions = index_version_map(index)
    errors: list[str] = []
    missing: list[str] = []
    checked: list[str] = []
    unchecked: list[str] = []

    for i, entry in enumerate(manifest_active_entries(manifest)):
        entry_obj = require_object(entry, f"manifest.active[{i}]")
        owner = entry_obj.get("owner")
        name = entry_obj.get("name")
        version = entry_obj.get("version")
        nu_version = entry_obj.get("nu_version")

        if not all(isinstance(x, str) and x for x in (owner, name, version)):
            errors.append(
                f"manifest active[{i}] incomplete (need owner/name/version): {entry_obj!r}"
            )
            continue

        label = f"{package_key(owner, name)}@{version}"
        if not isinstance(nu_version, str) or not nu_version:
            unchecked.append(f"{label} (manifest nu_version unknown)")
            continue

        key = (owner, name, version)
        index_nu = versions.get(key)
        if index_nu is None:
            missing.append(f"{label} (manifest nu_version={nu_version!r})")
            continue

        checked.append(label)
        if index_nu != nu_version:
            errors.append(
                f"{label}: manifest nu_version={nu_version!r} "
                f"!= index nu_version={index_nu!r}"
            )

    return errors, missing, checked, unchecked


def resolve_manifest(args: argparse.Namespace) -> dict:
    if args.manifest is not None:
        path = Path(args.manifest)
        if not path.is_file():
            raise FileNotFoundError(f"manifest not found: {path}")
        data = load_json_path(path)
    else:
        url = args.manifest_url
        try:
            data = load_json_url(url)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"failed to fetch manifest from {url}: {exc}") from exc

    return require_object(data, "manifest root")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint numan-plugins manifest Nu constraints against registry/index.json"
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help=f"path to registry index (default: {DEFAULT_INDEX})",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="local numan-plugins manifest.json (overrides --manifest-url)",
    )
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="URL for numan-plugins manifest.json when --manifest is omitted",
    )
    args = parser.parse_args(argv)

    if not args.index.is_file():
        print(f"error: index not found: {args.index}", file=sys.stderr)
        return 2

    try:
        index = require_object(load_json_path(args.index), "index root")
        manifest = resolve_manifest(args)
        errors, missing, checked, unchecked = compare(manifest, index)
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Checked {len(checked)} overlapping plugin version(s).")
    for label in checked:
        print(f"  ok  {label}")
    if unchecked:
        print(
            f"Skipped {len(unchecked)} active entry(ies) with unknown nu_version "
            "(not an error):"
        )
        for label in unchecked:
            print(f"  skip  {label}")
    if missing:
        print(f"Skipped {len(missing)} manifest plugin(s) not in index (not an error):")
        for label in missing:
            print(f"  skip  {label}")

    if errors:
        print(f"FAILED: {len(errors)} Nu constraint mismatch(es):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("OK: manifest and index Nu constraints agree where both are known.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
