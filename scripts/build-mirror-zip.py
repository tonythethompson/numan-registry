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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_at_ref(repo: str, ref: str, workdir: Path) -> Path:
    clone_dir = workdir / "src"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(clone_dir)])
    return clone_dir


def clone_at_commit(repo: str, commit: str, workdir: Path) -> Path:
    clone_dir = workdir / "src"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    run(["git", "clone", repo, str(clone_dir)])
    run(["git", "checkout", commit], cwd=clone_dir)
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
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def make_zip(source_dir: Path, output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    root_name = source_dir.name
    shutil.make_archive(
        str(output.with_suffix("")),
        "zip",
        root_dir=str(source_dir.parent),
        base_dir=root_name,
    )
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
    copy_paths(src_root, args.paths, staging)

    make_zip(staging, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
