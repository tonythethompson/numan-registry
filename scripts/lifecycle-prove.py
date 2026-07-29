#!/usr/bin/env python3.12
"""Run Stage 1 lifecycle-prove for a registry package against a real Nu.

Given a package id (`owner/name`) and paths to `numan` + `nu`, creates a
temporary Numan root and runs:

  init → registry sync → search → info → install → activate → doctor →
  list → deactivate → remove → gc

Fails nonzero on the first failing step and prints which step failed.
Does not commit, push, or sign anything.

Usage:
  python3 scripts/lifecycle-prove.py \\
      --package FMotalleb/nu_plugin_desktop_notifications \\
      --numan /path/to/numan \\
      --nu /path/to/nu

  # PATH lookup for numan/nu when flags omitted:
  python3 scripts/lifecycle-prove.py --package vyadh/nutest
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Step:
    name: str
    args: list[str]


def which(name: str) -> Path | None:
    """Locate an executable by name on the system PATH.
    
    Parameters:
    	name (str): The executable name to locate.
    
    Returns:
    	Path | None: The executable path if found, otherwise `None`.
    """
    found = shutil.which(name)
    return Path(found) if found else None


def is_executable(path: Path, *, platform: str | None = None) -> bool:
    """
    Determine whether a path points to an executable file for the target platform.
    
    Parameters:
        path (Path): File path to check.
        platform (str | None): Platform identifier used for the executable check. Defaults to the current platform.
    
    Returns:
        bool: `True` if the path is an executable file, `False` otherwise.
    """
    platform = platform or sys.platform
    if not path.is_file():
        return False
    if platform == "win32":
        return path.suffix.lower() in {".exe", ".cmd"}
    return os.access(path, os.X_OK)


def resolve_binary(
    explicit: Path | None,
    names: list[str],
    label: str,
    *,
    platform: str | None = None,
) -> Path:
    """
    Resolve an executable from an explicit path or a list of names on `PATH`.
    
    Parameters:
        explicit (Path | None): Optional executable path to validate and resolve.
        names (list[str]): Executable names to search for when no explicit path is provided.
        label (str): Binary label used in error messages and the suggested CLI option.
        platform (str | None): Optional platform identifier used for executable validation.
    
    Returns:
        Path: The resolved executable path.
    
    Raises:
        FileNotFoundError: If the explicit path is not executable or no named executable is found.
    """
    if explicit is not None:
        path = explicit
        if not is_executable(path, platform=platform):
            raise FileNotFoundError(f"{label} is not executable: {path}")
        return path.resolve()
    for name in names:
        found = which(name)
        if found is not None:
            return found.resolve()
    raise FileNotFoundError(
        f"{label} not found on PATH (tried {', '.join(names)}); pass --{label}"
    )


def validate_package_id(package_id: str) -> None:
    """Validate package ID has exactly owner/name format (two non-empty components).

    Raises ValueError if the package_id is malformed.
    """
    if "/" not in package_id:
        raise ValueError(f"package id must be owner/name, got {package_id!r}")
    parts = package_id.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"package id must have exactly two components (owner/name), got {package_id!r}"
        )
    owner, name = parts
    if not owner:
        raise ValueError(f"package id has empty owner: {package_id!r}")
    if not name:
        raise ValueError(f"package id has empty name: {package_id!r}")


def package_search_query(package_id: str) -> str:
    """Prefer the short name so search matches typical user queries."""
    if "/" in package_id:
        return package_id.split("/", 1)[1]
    return package_id


def build_steps(package_id: str) -> list[Step]:
    query = package_search_query(package_id)
    return [
        Step("init", ["init"]),
        Step("registry sync", ["registry", "sync"]),
        Step("search", ["search", query]),
        Step("info", ["info", package_id]),
        Step("install", ["install", package_id]),
        Step("activate", ["activate", "--yes", package_id]),
        Step("doctor", ["doctor"]),
        Step("list", ["list"]),
        # Plugins gate remove while active; deactivate first (modules too).
        Step("deactivate", ["deactivate", "--yes", package_id]),
        Step("remove", ["remove", package_id]),
        Step("gc", ["gc"]),
    ]


def run_step(
    step: Step,
    *,
    numan: Path,
    root: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """
    Run a lifecycle step with the specified Numan executable and root.
    
    Parameters:
    	step (Step): The lifecycle step and its command-line arguments.
    	numan (Path): Path to the Numan executable.
    	root (Path): Numan root directory for the step.
    	env (dict[str, str]): Environment variables used to run the command.
    
    Returns:
    	subprocess.CompletedProcess[str]: The completed process result.
    """
    cmd = [str(numan), "--root", str(root), *step.args]
    print(f"==> {step.name}: {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=False,
        check=False,
    )


def render_nu_shim(nu: Path, *, platform: str | None = None) -> bytes:
    """Render an exact-path Nu launcher for the requested platform."""
    platform = platform or sys.platform
    if platform == "win32":
        return f'@echo off\r\n"{nu}" %*\r\n'.encode("utf-8")
    return f'#!/bin/sh\nexec "{nu}" "$@"\n'.encode("utf-8")


def prepare_nu_search_dir(
    nu: Path,
    shim_dir: Path,
    *,
    platform: str | None = None,
) -> Path:
    """
    Ensure the selected Nu executable is discoverable under the name used by Numan.
    
    Parameters:
        nu (Path): Path to the selected Nu executable.
        shim_dir (Path): Directory used for Nu PATH isolation.
    
    Returns:
        Path: The directory containing the isolated Nu executable.
    
    Raises:
        ValueError: If Windows is used and `nu` does not have an `.exe` suffix.
        OSError: If the isolated Windows copy does not match the selected executable.
    """
    platform = platform or sys.platform
    if platform != "win32":
        return shim_dir
    if nu.suffix.lower() != ".exe":
        raise ValueError(
            "the selected Nu must be an .exe on Windows; .cmd launchers cannot "
            "safely forward Numan's probe arguments"
        )

    alias = shim_dir / "nu.exe"
    try:
        os.link(nu, alias)
    except OSError as link_error:
        shutil.copy2(nu, alias)
        if not filecmp.cmp(nu, alias, shallow=False):
            alias.unlink(missing_ok=True)
            raise OSError(
                "the isolated nu.exe copy does not match the selected Nu"
            ) from link_error
    return shim_dir


def prove(
    package_id: str,
    *,
    numan: Path,
    nu: Path,
    root: Path,
    keep_root: bool,
) -> int:
    # Prefer the requested Nu for `numan init` probing without mutating the
    # caller's shell permanently: create a temporary shim that invokes the
    # exact nu binary, ensuring numan doesn't find a different nu on PATH.
    """
    Run the complete lifecycle verification sequence for a package.
    
    Args:
        package_id: Package identifier in ``owner/name`` format.
        numan: Path to the Numan executable.
        nu: Path to the Nu executable used during initialization.
        root: Numan root directory for the verification.
        keep_root: Whether to preserve the root directory after completion.
    
    Returns:
        ``0`` if every lifecycle step succeeds, ``2`` if Nu isolation fails,
        or the failing step's exit code otherwise.
    
    The temporary Nu shim is removed after execution. The root directory is
    removed unless ``keep_root`` is true.
    """
    env = os.environ.copy()
    env["NUMAN_ROOT"] = str(root)

    # Create a temporary directory for the nu shim
    shim_dir = Path(tempfile.mkdtemp(prefix="numan-lifecycle-prove-shim-"))
    is_windows = sys.platform == "win32"
    shim_path = shim_dir / "nu"

    try:
        if not is_windows:
            shim_path.write_bytes(render_nu_shim(nu))
            shim_path.chmod(0o755)

        # Rust rejects some arguments when Command launches a batch file, so
        # Windows exposes an isolated nu.exe hardlink/copy of the exact binary.
        try:
            nu_search_dir = prepare_nu_search_dir(nu, shim_dir)
        except (OSError, ValueError) as exc:
            print(f"error: could not isolate selected Nu: {exc}", file=sys.stderr)
            return 2

        # Prepend the selected Nu location to PATH.
        path_key = "PATH"
        sep = os.pathsep
        env[path_key] = str(nu_search_dir) + sep + env.get(path_key, "")

        print(f"package: {package_id}")
        print(f"numan:   {numan}")
        print(f"nu:      {nu}")
        print(f"root:    {root}")
        print(flush=True)

        for step in build_steps(package_id):
            result = run_step(step, numan=numan, root=root, env=env)
            if result.returncode != 0:
                print(
                    f"FAILED at step {step.name!r} "
                    f"(exit {result.returncode})",
                    file=sys.stderr,
                )
                return result.returncode if result.returncode != 0 else 1
        print("OK: lifecycle-prove passed.")
        return 0
    finally:
        # Clean up shim directory
        shutil.rmtree(shim_dir, ignore_errors=True)

        if keep_root:
            print(f"kept root at {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 1 lifecycle-prove: search→info→install→activate→doctor→"
            "list→deactivate→remove→gc on a temp Numan root"
        )
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Package id (owner/name), e.g. FMotalleb/nu_plugin_desktop_notifications",
    )
    parser.add_argument(
        "--numan",
        type=Path,
        default=None,
        help="Path to numan binary (default: numan on PATH)",
    )
    parser.add_argument(
        "--nu",
        type=Path,
        default=None,
        help="Path to nu binary (default: nu on PATH); prepended to PATH for init",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Numan root to use (default: fresh temp dir, deleted on success/fail)",
    )
    parser.add_argument(
        "--keep-root",
        action="store_true",
        help="Do not delete the temp root after the run",
    )
    args = parser.parse_args(argv)

    try:
        validate_package_id(args.package.strip())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        numan = resolve_binary(
            args.numan,
            ["numan", "numan.exe"],
            "numan",
        )
        nu = resolve_binary(args.nu, ["nu", "nu.exe"], "nu")
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.root is not None:
        root = args.root.resolve()
        if root.exists():
            if not root.is_dir():
                print(f"error: --root exists but is not a directory: {root}", file=sys.stderr)
                return 2
            # Reject non-empty existing directories
            if any(root.iterdir()):
                print(f"error: --root directory must be empty: {root}", file=sys.stderr)
                return 2
        else:
            # Create the directory if it doesn't exist
            root.mkdir(parents=True, exist_ok=True)
        # Never delete a caller-supplied root.
        keep_root = True
    else:
        root = Path(tempfile.mkdtemp(prefix="numan-lifecycle-prove-"))
        keep_root = bool(args.keep_root)

    return prove(
        args.package.strip(),
        numan=numan,
        nu=nu,
        root=root,
        keep_root=keep_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
