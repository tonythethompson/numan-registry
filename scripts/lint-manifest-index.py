#!/usr/bin/env python3
"""Compare numan-plugins manifest Nu constraints to registry index entries.

Stage 2 intake gate (next-steps C3 / strategy audit §5): when a plugin appears
in both `numan-plugins/manifest.json` `active[]` and `registry/index.json` at
the same owner/name/version, their `nu_version` strings must match exactly.

Does not fail when a manifest plugin is not yet in the index (promotion lag).
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
    req = urllib.request.Request(url, headers={"User-Agent": "numan-registry-lint"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def package_key(owner: str, name: str) -> str:
    return f"{owner}/{name}"


def index_version_map(index: dict) -> dict[tuple[str, str, str], str]:
    """Map (owner, name, version) -> nu_version from the registry index."""
    out: dict[tuple[str, str, str], str] = {}
    for pkg in index.get("packages", []):
        ident = pkg.get("id") or {}
        owner = ident.get("owner")
        name = ident.get("name")
        if not owner or not name:
            continue
        for ver in pkg.get("versions", []):
            version = ver.get("version")
            nu_version = ver.get("nu_version")
            if version is None or nu_version is None:
                continue
            out[(owner, name, version)] = nu_version
    return out


def manifest_active_entries(manifest: dict) -> list[dict]:
    active = manifest.get("active")
    if not isinstance(active, list):
        raise ValueError("manifest.json missing active[] array")
    return active


def compare(
    manifest: dict,
    index: dict,
) -> tuple[list[str], list[str], list[str]]:
    """Return (errors, missing_from_index, checked)."""
    versions = index_version_map(index)
    errors: list[str] = []
    missing: list[str] = []
    checked: list[str] = []

    for entry in manifest_active_entries(manifest):
        owner = entry.get("owner")
        name = entry.get("name")
        version = entry.get("version")
        nu_version = entry.get("nu_version")
        if not all(isinstance(x, str) and x for x in (owner, name, version, nu_version)):
            errors.append(
                f"manifest active entry incomplete (need owner/name/version/nu_version): {entry!r}"
            )
            continue

        key = (owner, name, version)
        label = f"{package_key(owner, name)}@{version}"
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

    return errors, missing, checked


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

    if not isinstance(data, dict):
        raise ValueError("manifest root must be a JSON object")
    return data


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
        index = load_json_path(args.index)
        if not isinstance(index, dict):
            raise ValueError("index root must be a JSON object")
        manifest = resolve_manifest(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors, missing, checked = compare(manifest, index)

    print(f"Checked {len(checked)} overlapping plugin version(s).")
    for label in checked:
        print(f"  ok  {label}")
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
