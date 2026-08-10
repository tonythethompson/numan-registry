#!/usr/bin/env python3
"""Automate registry intake for non-binary packages (modules, scripts, completions).

The CI plugin lane cross-compiles Rust; modules/scripts/completions need no
compilation at all -- they're just archives of source files. This script
turns "here's a Git repo with Nu files" into a registry-intake-ready spec:

  1. Resolve the given ref (branch, tag, or commit SHA) to its full 40-char
     commit SHA via `git ls-remote` (immutable provenance anchor, matching
     the CI plugin lane's `source_commit` convention).
  2. Shallow-clone the repo and check out exactly that SHA.
  3. Verify the declared entry file exists in the checkout.
  4. Archive the checked-out tree (minus .git) as a deterministic .tar.gz --
     sorted entries, fixed mtime, gzip mtime=0 -- matching numan-plugins'
     scripts/package_plugin.py conventions, so repeat builds are byte-stable.
  5. Upload the archive to a GitHub Release on --release-repo.
  6. Emit a spec JSON compatible with `add-package.py --spec ... --write`.
  7. Record the resolved SHA + original ref in manifest-archives.json for
     repeatable re-intake on version bumps.

The registry index's `source` field is Rust-plugin-shaped (requires
cargo_name) and existing non-binary entries all omit it; provenance for
archive packages lives in manifest-archives.json instead, not in the
registry index.

Usage:
  python scripts/intake-archive.py \\
    --git-url https://github.com/owner/repo --ref v1.0.0 \\
    --entry mod.nu --name cool-module --owner someone --type module \\
    --description "..." --tags '["module"]' --nu-version ">=0.114.0" \\
    --activation-kind nu-module --activation-import all \\
    --release-repo tonythethompson/numan-registry \\
    --out spec-someone-cool-module.json --write
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
COMMAND_TIMEOUT_SECONDS = 120
FIXED_MTIME = 315532800  # 1980-01-01 UTC; matches package_plugin.py
VALID_TYPES = ("module", "script", "completion")


def _load_add_package() -> ModuleType:
    """Dynamically load add-package.py (hyphenated filename, not import-able)."""
    spec = importlib.util.spec_from_file_location(
        "add_package", Path(__file__).resolve().parent / "add-package.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("could not load scripts/add-package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_ref(git_url: str, ref: str) -> str:
    """Resolve a branch, tag, or commit SHA on `git_url` to its full 40-char commit SHA."""
    for candidate in (ref, f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"):
        result = subprocess.run(
            ["git", "ls-remote", git_url, candidate],
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    if SHA_RE.fullmatch(ref):
        return ref
    raise ValueError(f"could not resolve ref {ref!r} on {git_url}")


def shallow_clone_at(git_url: str, sha: str, dest: Path) -> None:
    """Clone `git_url` into `dest` and check out exactly `sha`, shallow (depth=1)."""
    subprocess.run(
        ["git", "init", "--quiet", str(dest)], check=True, timeout=COMMAND_TIMEOUT_SECONDS
    )
    subprocess.run(
        ["git", "-C", str(dest), "remote", "add", "origin", git_url],
        check=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    subprocess.run(
        ["git", "-C", str(dest), "fetch", "--quiet", "--depth", "1", "origin", sha],
        check=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", sha],
        check=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )


def sorted_files(root: Path) -> list[Path]:
    """List regular files under `root` (excluding .git), sorted for deterministic archiving."""
    files = []
    resolved_root = root.resolve()
    for p in root.rglob("*"):
        if p.is_symlink():
            raise ValueError(f"symlink not allowed in archive source: {p.relative_to(root)}")
        if not p.is_file():
            continue
        try:
            p.resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"archive source path resolves outside checkout: {p.relative_to(root)}") from exc
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] == ".git":
            continue
        files.append(rel)
    return sorted(files, key=lambda p: p.as_posix())


def build_archive(src_dir: Path, out: Path) -> None:
    """Build a deterministic .tar.gz of `src_dir`: sorted entries, fixed mtime, gzip mtime=0."""
    raw = io.BytesIO()
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024

    rels = sorted_files(src_dir)
    if len(rels) > MAX_ARCHIVE_FILES:
        raise ValueError(f"{len(rels)} files exceeds client limit of {MAX_ARCHIVE_FILES}")
    total = sum((src_dir / r).stat().st_size for r in rels)
    if total > MAX_ARCHIVE_BYTES:
        raise ValueError(f"{total} bytes exceeds client limit of {MAX_ARCHIVE_BYTES}")

    with out.open("wb") as fh:
        gz = gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0)
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for rel in rels:
                full = src_dir / rel
                info = tarfile.TarInfo(name=rel.as_posix())
                info.size = full.stat().st_size
                info.mtime = FIXED_MTIME
                info.mode = 0o755 if full.stat().st_mode & 0o111 else 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with full.open("rb") as src:
                    tar.addfile(info, src)
        gz.close()
        gz.close()


def upload_to_release(release_repo: str, tag: str, title: str, asset: Path) -> str:
    """Create a new GitHub release on `release_repo` and upload `asset`.

    Refuses to reuse an existing tag (immutable-per-intake, like the CI
    plugin lane's release_transaction.py). Returns the asset's download URL.
    """
    gh_helpers = importlib.import_module("gh_helpers")

    existing = gh_helpers.gh_run(["release", "view", tag, "--repo", release_repo])
    if existing is not None and existing.returncode == 0:
        raise ValueError(f"release tag {tag!r} already exists on {release_repo}; refusing to overwrite")

    result = gh_helpers.gh_run(
        [
            "release",
            "create",
            tag,
            str(asset),
            "--repo",
            release_repo,
            "--title",
            title,
            "--notes",
            f"Non-binary archive intake: {asset.name}",
        ]
    )
    if result is None or result.returncode != 0:
        stderr = result.stderr.strip() if result is not None else "gh CLI unavailable"
        raise ValueError(f"gh release create failed: {stderr}")
    return f"https://github.com/{release_repo}/releases/download/{tag}/{asset.name}"


def derive_version(ref: str, resolved_sha: str) -> str:
    """Derive a version string when the caller doesn't supply one explicitly.

    A tag-shaped ref (optionally 'v'-prefixed semver) uses its own version.
    Otherwise falls back to the 0.1.0-<short-sha> convention already used by
    this registry's existing script/completion entries pinned to a branch.
    """
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+(?:[-+].+)?)", ref)
    if match:
        return match.group(1)
    return f"0.1.0-{resolved_sha[:7]}"


def build_spec(
    *,
    owner: str,
    name: str,
    description: str,
    git_url: str,
    pkg_type: str,
    tags: list[str],
    version: str,
    nu_version: str,
    entry: str,
    url: str,
    activation_kind: str | None = None,
    activation_import: str | None = None,
) -> dict:
    """Build a registry intake spec for a non-binary (archive-kind) package."""
    spec: dict = {
        "owner": owner,
        "name": name,
        "description": description,
        "repo": git_url,
        "type": pkg_type,
        "tags": tags,
        "version": version,
        "nu_version": nu_version,
        "artifact": {
            "kind": "archive",
            "url": url,
            "entry": entry,
        },
    }
    if activation_kind:
        activation = {"kind": activation_kind}
        if activation_import:
            activation["import"] = activation_import
        spec["activation"] = activation
    return spec


def record_archive_manifest(
    path: Path,
    *,
    git_url: str,
    ref: str,
    resolved_sha: str,
    entry: str,
    name: str,
    owner: str,
    pkg_type: str,
) -> None:
    """Upsert this intake's re-intake tracking record into manifest-archives.json."""
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    record = {
        "git": git_url,
        "ref": ref,
        "resolved_sha": resolved_sha,
        "entry": entry,
        "name": name,
        "owner": owner,
        "type": pkg_type,
    }
    entries = [e for e in entries if not (e.get("owner") == owner and e.get("name") == name)]
    entries.append(record)
    entries.sort(key=lambda e: (e.get("owner", ""), e.get("name", "")))
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Resolve, archive, publish, and emit a registry spec for a non-binary package."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--git-url", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--type", required=True, choices=VALID_TYPES, dest="pkg_type")
    ap.add_argument("--description", required=True)
    ap.add_argument("--tags", required=True, help="JSON array of tag strings")
    ap.add_argument("--nu-version", required=True)
    ap.add_argument("--activation-kind", default=None)
    ap.add_argument("--activation-import", default=None, choices=("module", "all"))
    ap.add_argument(
        "--provisional",
        action="store_true",
        help="Allow activation-bearing specs without lifecycle evidence",
    )
    ap.add_argument(
        "--version",
        default=None,
        help="Version string for this intake; derived from --ref if omitted",
    )
    ap.add_argument(
        "--release-repo",
        required=True,
        help="owner/repo to publish the archive as a GitHub release asset on",
    )
    ap.add_argument(
        "--manifest-archives",
        type=Path,
        default=REPO_ROOT / "manifest-archives.json",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="Chain into add-package.py --write")
    args = ap.parse_args(argv)

    if args.activation_kind and not args.provisional:
        print(
            "FAIL: --activation-kind requires --provisional (no lifecycle evidence was provided)",
            file=sys.stderr,
        )
        return 1

    try:
        tags = json.loads(args.tags)
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError("--tags must be a JSON array of strings")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.activation_kind:
        add_package = _load_add_package()
        try:
            add_package.check_module_import_mode(
                {"entry": args.entry},
                {"kind": args.activation_kind, "import": args.activation_import or "module"},
            )
        except SystemExit:
            return 1

    try:
        resolved_sha = resolve_ref(args.git_url, args.ref)
    except (ValueError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Resolved {args.git_url}@{args.ref} -> {resolved_sha}", file=sys.stderr)

    version = args.version or derive_version(args.ref, resolved_sha)

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = Path(tmp) / "src"
        try:
            shallow_clone_at(args.git_url, resolved_sha, src_dir)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print(f"FAIL: could not clone/checkout {resolved_sha}: {exc}", file=sys.stderr)
            return 1

        entry_path = src_dir / args.entry
        try:
            if Path(args.entry).is_absolute():
                raise ValueError
            entry_path.resolve().relative_to(src_dir.resolve())
        except ValueError:
            print(f"FAIL: entry path escapes checkout: {args.entry}", file=sys.stderr)
            return 1
        if not entry_path.is_file():
            print(f"FAIL: entry file not found in checkout: {args.entry}", file=sys.stderr)
            return 1

        archive_path = Path(tmp) / f"{args.owner}-{args.name}-{version}.tar.gz"
        try:
            build_archive(src_dir, archive_path)
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        print(f"Built {archive_path.name} sha256={digest}", file=sys.stderr)

        tag = f"archive-{args.owner}-{args.name}-{version}"
        try:
            url = upload_to_release(
                args.release_repo, tag, f"{args.owner}/{args.name} {version}", archive_path
            )
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

    spec = build_spec(
        owner=args.owner,
        name=args.name,
        description=args.description,
        git_url=args.git_url,
        pkg_type=args.pkg_type,
        tags=tags,
        version=version,
        nu_version=args.nu_version,
        entry=args.entry,
        url=url,
        activation_kind=args.activation_kind,
        activation_import=args.activation_import,
    )

    out_path = args.out or (REPO_ROOT / f"spec-{args.owner}-{args.name}.json")
    out_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)

    record_archive_manifest(
        args.manifest_archives,
        git_url=args.git_url,
        ref=args.ref,
        resolved_sha=resolved_sha,
        entry=args.entry,
        name=args.name,
        owner=args.owner,
        pkg_type=args.pkg_type,
    )
    print(f"recorded re-intake tracking in {args.manifest_archives}", file=sys.stderr)

    if args.write:
        add_package_script = REPO_ROOT / "scripts" / "add-package.py"
        result = subprocess.run(
            [
                sys.executable,
                str(add_package_script),
                "--spec",
                str(out_path),
                "--write",
                *( ["--provisional"] if args.provisional else [] ),
            ],
            cwd=REPO_ROOT,
        )
        return result.returncode

    rerun_cmd = f"python scripts/add-package.py --spec {out_path} --write"
    if args.provisional:
        rerun_cmd += " --provisional"
    print(f"\nRe-run with the emitted spec: {rerun_cmd}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
