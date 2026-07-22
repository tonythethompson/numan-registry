#!/usr/bin/env python3
"""Scaffold a registry/index.json package entry from a spec file.

Takes a small JSON "spec" describing a package version WITHOUT any sha256
values, downloads each referenced artifact, computes its sha256, and either
prints the resulting package/version JSON block (default) or merges it
into registry/index.json (--write). Never commits, pushes, or signs
anything — that stays a separate, reviewed step.

This exists so a maintainer never hand-types a sha256: a typo there
silently ships a broken or unverifiable install. See the mechanical
equivalent on the client side: scripts/update-official-trust-root.sh in
tonythethompson/numan does the same "script computes, human reviews" shape
for the trust root.

Spec format (binary artifact, e.g. a plugin):

    {
      "owner": "someone", "name": "cool-plugin",
      "description": "...", "repo": "https://github.com/someone/cool-plugin",
      "type": "plugin", "tags": ["plugin", "utility"],
      "version": "1.0.0", "nu_version": "0.111.x", "verified_with": ["0.111.0"],
      "artifact": {
        "kind": "binary",
        "targets": {
          "x86_64-pc-windows-msvc": {"url": "https://.../windows.zip", "executable_path": "nu_plugin_cool.exe"},
          "x86_64-unknown-linux-gnu": {"url": "https://.../linux.tar.gz", "executable_path": "nu_plugin_cool"},
          "x86_64-apple-darwin": {"url": "https://.../macos.tar.gz", "executable_path": "nu_plugin_cool"}
        }
      }
    }

Spec format (archive artifact, e.g. a module):

    {
      "owner": "someone", "name": "cool-module",
      "description": "...", "repo": "https://github.com/someone/cool-module",
      "type": "module", "tags": ["module"],
      "version": "1.0.0", "nu_version": "*",
      "artifact": {"kind": "archive", "url": "https://.../module.zip", "entry": "mod.nu"},
      "activation": {"kind": "nu-module", "import": "all"}
    }

Note: a "mod.nu" entry must use "import": "all". Numan's activation
imports the entry file directly (`use "<entry>"`), not the containing
directory, so Nu's directory-name-becomes-module-name convention for
mod.nu doesn't apply here -- "import": "module" would activate under
a module literally named "mod", not the package name. Use "import":
"module" only when the entry file is NOT named mod.nu (its own
filename becomes the module name in that case, which is what you
want).

`artifact.kind: "source"` is not supported yet — source builds are a
deferred Phase 5 item on the client per CLAUDE.md; an entry this script
can't verify by hash is exactly the kind of unverifiable entry it exists
to prevent.

Usage:
  ./scripts/add-package.py --spec spec.json
      Downloads artifacts, computes sha256, prints the resulting JSON
      block. Does not touch registry/index.json.

  ./scripts/add-package.py --spec spec.json --write [--index registry/index.json] [--force]
      Same, then merges into the index (new package, or a new version
      under an existing package) and writes it back. Refuses to replace
      an existing version's artifact without --force.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "index-v1.json"

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
REQUIRED_TOP_FIELDS = (
    "owner",
    "name",
    "description",
    "repo",
    "type",
    "tags",
    "version",
    "nu_version",
    "artifact",
)
VALID_TYPES = ("plugin", "module", "script", "completion")

# Must match ArchiveFormat::from_url in tonythethompson/numan's
# src/install/extract.rs. A target URL with any other extension will fail
# to install with "Cannot determine archive format" -- checked here because
# a real seed entry shipped with .tar.xz targets and nobody caught it until
# a reviewer actually traced it through the client's install path.
SUPPORTED_ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".tar")


def check_archive_format_supported(url, label):
    lower = url.lower()
    if not any(lower.endswith(suffix) for suffix in SUPPORTED_ARCHIVE_SUFFIXES):
        print(
            f"FAIL: {label} url '{url}' does not end in a format Numan's "
            f"installer supports ({', '.join(SUPPORTED_ARCHIVE_SUFFIXES)}). "
            "It would fail to install with 'Cannot determine archive format'. "
            "Either the upstream release needs a differently-packaged asset, "
            "or this target should be dropped from the entry."
        )
        sys.exit(1)


def download_and_hash(url):
    print(f"  downloading {url} ...", file=sys.stderr)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    print(f"  OK: sha256={digest} ({len(data)} bytes)", file=sys.stderr)
    return digest


def build_artifact(spec_artifact):
    kind = spec_artifact.get("kind")
    if kind == "source":
        print(
            "FAIL: artifact.kind 'source' is not supported by this script - "
            "source builds are a deferred client feature (see CLAUDE.md Phase "
            "status). An entry this script can't verify by hash is exactly "
            "what it exists to prevent."
        )
        sys.exit(1)

    if kind == "binary":
        targets = spec_artifact.get("targets") or {}
        if not targets:
            print("FAIL: artifact.kind 'binary' requires at least one entry in 'targets'")
            sys.exit(1)
        built_targets = {}
        for triple, target in targets.items():
            url = target.get("url")
            executable_path = target.get("executable_path")
            if not url or not executable_path:
                print(f"FAIL: target '{triple}' requires 'url' and 'executable_path'")
                sys.exit(1)
            check_archive_format_supported(url, f"target '{triple}'")
            sha256 = download_and_hash(url)
            built_targets[triple] = {
                "url": url,
                "sha256": sha256,
                "executable_path": executable_path,
            }
        return {"kind": "binary", "targets": built_targets}

    if kind == "archive":
        url = spec_artifact.get("url")
        if not url:
            print("FAIL: artifact.kind 'archive' requires 'url'")
            sys.exit(1)
        check_archive_format_supported(url, "artifact")
        sha256 = download_and_hash(url)
        artifact = {"kind": "archive", "url": url, "sha256": sha256}
        for optional in ("entry", "archive_root", "include"):
            if optional in spec_artifact:
                artifact[optional] = spec_artifact[optional]
        return artifact

    print(f"FAIL: unsupported artifact.kind '{kind}' (expected 'binary' or 'archive')")
    sys.exit(1)


def check_module_import_mode(spec_artifact, activation):
    if not activation or activation.get("kind") != "nu-module":
        return
    entry = spec_artifact.get("entry")
    import_mode = activation.get("import", "module")
    if entry and Path(entry).name == "mod.nu" and import_mode == "module":
        print(
            "FAIL: entry is a 'mod.nu' file with activation.import 'module'. "
            "Numan's activation renders this as `use \"<entry file>\"` (a "
            "file-form import), not `use \"<containing dir>\"`. Nu's "
            "directory-name-becomes-module-name convention for mod.nu only "
            "applies to the directory form, so this would activate as a "
            "module named 'mod', not the package name -- e.g. `mod run-tests` "
            "instead of the upstream-documented `nutest run-tests`. "
            "Verified empirically on real Nu; this is not a hypothetical. "
            "Set activation.import to 'all' instead (commands import "
            "unprefixed), or use a differently-named entry file if the "
            "package doesn't need mod.nu's directory-scoping behavior."
        )
        sys.exit(1)


SOURCE_REQUIRED_KEYS = ("git", "rev", "cargo_name")


def copy_source_field(spec, version_entry):
    """Copy optional `source` provenance onto a version entry.

    Schema (index-v1): required git/rev/cargo_name; optional cargo_lock_sha256.
    Extracted so unit tests can assert passthrough without downloading artifacts.
    """
    if "source" not in spec:
        return
    source = spec["source"]
    if not isinstance(source, dict):
        print("FAIL: 'source' must be an object with git, rev, and cargo_name")
        sys.exit(1)
    missing = [k for k in SOURCE_REQUIRED_KEYS if not source.get(k)]
    if missing:
        print(
            "FAIL: 'source' is missing required field(s): "
            + ", ".join(missing)
            + " (need git, rev, cargo_name)"
        )
        sys.exit(1)
    out = {k: source[k] for k in SOURCE_REQUIRED_KEYS}
    if "cargo_lock_sha256" in source:
        out["cargo_lock_sha256"] = source["cargo_lock_sha256"]
    version_entry["source"] = out


def build_version_entry(spec):
    version_entry = {
        "version": spec["version"],
        "nu_version": spec["nu_version"],
    }
    if "verified_with" in spec:
        version_entry["verified_with"] = spec["verified_with"]
    copy_source_field(spec, version_entry)
    if "activation" in spec:
        check_module_import_mode(spec["artifact"], spec["activation"])
    version_entry["artifact"] = build_artifact(spec["artifact"])
    if "activation" in spec:
        version_entry["activation"] = spec["activation"]
    if "dependencies" in spec:
        version_entry["dependencies"] = spec["dependencies"]
    return version_entry


def build_package_entry(spec, version_entry):
    return {
        "id": {"owner": spec["owner"], "name": spec["name"]},
        "description": spec["description"],
        "repo": spec["repo"],
        "type": spec["type"],
        "tags": spec.get("tags", []),
        "versions": [version_entry],
    }


def validate_spec(spec):
    missing = [f for f in REQUIRED_TOP_FIELDS if f not in spec]
    if missing:
        print(f"FAIL: spec is missing required field(s): {', '.join(missing)}")
        sys.exit(1)
    if spec["type"] not in VALID_TYPES:
        print(f"FAIL: type must be one of {VALID_TYPES}, got '{spec['type']}'")
        sys.exit(1)


def validate_against_schema(index):
    try:
        import jsonschema
    except ImportError:
        print(
            "WARN: 'jsonschema' not installed, skipping schema validation. "
            "Install with: pip install jsonschema",
            file=sys.stderr,
        )
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(index, schema)
    print("OK: resulting index validates against schemas/index-v1.json")


def merge_into_index(index_path, package_entry, force):
    index = json.loads(index_path.read_text(encoding="utf-8"))
    owner = package_entry["id"]["owner"]
    name = package_entry["id"]["name"]
    new_version = package_entry["versions"][0]["version"]

    existing = None
    for pkg in index.get("packages", []):
        if pkg["id"]["owner"] == owner and pkg["id"]["name"] == name:
            existing = pkg
            break

    if existing is None:
        index.setdefault("packages", []).append(package_entry)
        print(f"OK: added new package {owner}/{name}@{new_version}")
    else:
        existing_versions = {v["version"]: i for i, v in enumerate(existing["versions"])}
        if new_version in existing_versions and not force:
            print(
                f"FAIL: {owner}/{name}@{new_version} already exists. "
                "Re-run with --force to replace it (e.g. a re-published artifact)."
            )
            sys.exit(1)
        if new_version in existing_versions:
            existing["versions"][existing_versions[new_version]] = package_entry["versions"][0]
            print(f"OK: replaced existing version {owner}/{name}@{new_version}")
        else:
            existing["versions"].append(package_entry["versions"][0])
            print(f"OK: added new version {owner}/{name}@{new_version}")
        # Keep description/repo/tags in sync with the latest spec for this package.
        existing["description"] = package_entry["description"]
        existing["repo"] = package_entry["repo"]
        existing["tags"] = package_entry["tags"]

    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return index


def main():
    parser = argparse.ArgumentParser(description="Scaffold a registry package entry from a spec file")
    parser.add_argument("--spec", required=True, help="Path to the package spec JSON file")
    parser.add_argument("--write", action="store_true", help="Merge into --index instead of just printing")
    parser.add_argument("--index", default=str(REPO_ROOT / "registry" / "index.json"))
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing version")
    args = parser.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    validate_spec(spec)

    print(f"Building {spec['owner']}/{spec['name']}@{spec['version']} ...", file=sys.stderr)
    version_entry = build_version_entry(spec)
    package_entry = build_package_entry(spec, version_entry)

    if not args.write:
        print("\n--- package entry (not written; re-run with --write to merge) ---")
        print(json.dumps(package_entry, indent=2))
        return 0

    index_path = Path(args.index)
    index = merge_into_index(index_path, package_entry, args.force)
    validate_against_schema(index)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")

    resolved = index_path.resolve()
    try:
        diff_target = resolved.relative_to(REPO_ROOT)
    except ValueError:
        # index_path lives outside REPO_ROOT (e.g. --index pointed elsewhere);
        # fall back to the absolute path rather than a bogus relative one.
        diff_target = resolved

    print(f"\nWrote {index_path}. Review the diff before committing:")
    print(f"  git -C \"{REPO_ROOT}\" --no-pager diff -- \"{diff_target}\"")
    print(
        "\nNote: this does not sign the index. Signing happens via the "
        "staging/production workflow, same as any other index change."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
