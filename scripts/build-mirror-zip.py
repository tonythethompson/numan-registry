#!/usr/bin/env python3
"""Build a byte-stable mirror zip from a git repository for registry intake.

Clones (or reuses) a repo at a fixed ref, copies selected paths into a
top-level archive_root directory, and writes a zip suitable for upload as a
numan-registry release asset. Does not commit, push, or upload anything.

Usage:
  python scripts/build-mirror-zip.py \\
    --repo https://github.com/owner/repo \\
    --ref 1.2.3 \\
    --paths pkgs/nu-git-manager \\
    --archive-root nu-git-manager-1.2.3 \\
    --output /tmp/nu-git-manager-1.2.3.zip
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Zip epoch used for all entries so rebuilds of the same source ref produce
# identical bytes (required for hash-pinned registry mirrors).
FIXED_ZIP_DT = (1980, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = 0o644
# Unix (3) in every zip central directory — Windows defaults to 0 and changes sha256.
FIXED_ZIP_CREATE_SYSTEM = 3
VCS_DIR_NAMES = frozenset({".git", ".hg", ".svn"})


def ignore_vcs_metadata(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in VCS_DIR_NAMES}


def assert_mirror_paths_safe(src_root: Path, rel_paths: list[str]) -> None:
    """Reject symlinks and paths that resolve outside the clone."""
    root = src_root.resolve()
    for rel in rel_paths:
        src_path = src_root / rel
        if src_path.is_symlink():
            print(f"FAIL: symlink not allowed in mirror source: {rel}")
            sys.exit(1)
        src = src_path.resolve()
        try:
            src.relative_to(root)
        except ValueError:
            print(f"FAIL: path '{rel}' resolves outside clone ({src})")
            sys.exit(1)
        if src.is_dir():
            for child in src.rglob("*"):
                if child.is_symlink():
                    child_rel = child.relative_to(root)
                    print(f"FAIL: symlink not allowed in mirror source: {child_rel}")
                    sys.exit(1)
                try:
                    child.resolve().relative_to(root)
                except ValueError:
                    child_rel = child.relative_to(root)
                    print(f"FAIL: path resolves outside clone: {child_rel}")
                    sys.exit(1)
        elif not src.is_file():
            print(f"FAIL: path '{rel}' is not a regular file or directory")
            sys.exit(1)


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_at_ref(repo: str, ref: str, workdir: Path) -> Path:
    clone_dir = workdir / "src"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    run(["git", "clone", "--depth", "1", "--branch", ref, "--", repo, str(clone_dir)])
    return clone_dir


def clone_at_commit(repo: str, commit: str, workdir: Path) -> Path:
    clone_dir = workdir / "src"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    clone_dir.mkdir(parents=True)
    run(["git", "init", "-q"], cwd=clone_dir)
    run(["git", "remote", "add", "origin", repo], cwd=clone_dir)
    run(["git", "fetch", "--depth", "1", "origin", commit], cwd=clone_dir)
    run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=clone_dir)
    return clone_dir


def copy_paths(src_root: Path, rel_paths: list[str], dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for rel in rel_paths:
        src = src_root / rel
        if not src.exists():
            print(f"FAIL: path '{rel}' not found under {src_root}")
            sys.exit(1)
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=ignore_vcs_metadata, symlinks=False)
        else:
            shutil.copy(src, dest)


def make_zip(source_dir: Path, output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    root_name = source_dir.name
    entries: list[tuple[Path, str]] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        if VCS_DIR_NAMES.intersection(path.parts):
            continue
        rel = path.relative_to(source_dir).as_posix()
        entries.append((path, f"{root_name}/{rel}"))

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in entries:
            info = zipfile.ZipInfo(arcname)
            info.date_time = FIXED_ZIP_DT
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = FIXED_ZIP_CREATE_SYSTEM
            info.external_attr = (FIXED_FILE_MODE & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"OK: wrote {output} ({output.stat().st_size} bytes)", file=sys.stderr)
    print(f"OK: sha256={digest}", file=sys.stderr)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a registry mirror zip from git")
    parser.add_argument("--repo", required=True, help="Git repository URL")
    parser.add_argument("--ref", help="Branch or tag name (mutually exclusive with --commit)")
    parser.add_argument("--commit", help="Full commit SHA")
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Repo-relative paths to include under archive-root",
    )
    parser.add_argument("--archive-root", required=True, help="Top-level directory name inside the zip")
    parser.add_argument("--output", required=True, type=Path, help="Output .zip path")
    parser.add_argument("--workdir", type=Path, help="Reuse this working directory")
    args = parser.parse_args()

    if bool(args.ref) == bool(args.commit):
        print("FAIL: specify exactly one of --ref or --commit")
        return 1

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="numan-mirror-"))
    workdir.mkdir(parents=True, exist_ok=True)

    if args.commit:
        src_root = clone_at_commit(args.repo, args.commit, workdir)
    else:
        src_root = clone_at_ref(args.repo, args.ref, workdir)

    staging = workdir / "staging" / args.archive_root
    if staging.exists():
        shutil.rmtree(staging.parent)
    assert_mirror_paths_safe(src_root, args.paths)
    copy_paths(src_root, args.paths, staging)

    make_zip(staging, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
