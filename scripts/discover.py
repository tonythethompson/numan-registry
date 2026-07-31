#!/usr/bin/env python3.12
"""Stage 3: Read-only repo discovery for registry intake.

Inspects a GitHub repository (via `gh` CLI) or a local checkout and produces
a structured JSON report separating facts from guesses. Does not mutate
anything — pure read + report.

Usage:
  python scripts/discover.py --repo fdncred/nu_plugin_emoji [--ref v0.23.0]
  python scripts/discover.py --path /local/checkout [--out report.json]

Output schema (discovery-v1):
  {schema_version, source, facts, guesses, needs_decision, platform_hints}
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

from archive_formats import SUPPORTED_ARCHIVE_SUFFIXES

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# GitHub helpers (same pattern as sync-intake-candidates.py)
# ---------------------------------------------------------------------------


def gh_json(args: list[str]) -> object | None:
    """Run a gh CLI command and parse JSON output."""
    try:
        out = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def gh_text(args: list[str]) -> str | None:
    """Run a gh CLI command and return stripped text output."""
    try:
        out = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

_NU_PLUGIN_DEP_RE = re.compile(r'nu-plugin\s*=\s*["\{]')
_NU_PROTOCOL_DEP_RE = re.compile(r'nu-protocol\s*=\s*["\{]')
_NU_VERSION_RE = re.compile(r'nu-plugin\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"')
_CRATE_NAME_RE = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)


def _archive_suffix(filename: str) -> str | None:
    """Return the supported archive suffix for a filename, or None."""
    for suffix in SUPPORTED_ARCHIVE_SUFFIXES:
        if filename.endswith(suffix):
            return suffix
    return None


def _classify_from_cargo(cargo_content: str) -> dict:
    """Extract plugin classification hints from Cargo.toml content."""
    is_plugin = bool(_NU_PLUGIN_DEP_RE.search(cargo_content)) or bool(
        _NU_PROTOCOL_DEP_RE.search(cargo_content)
    )
    crate_match = _CRATE_NAME_RE.search(cargo_content)
    crate_name = crate_match.group(1) if crate_match else None
    version_match = _NU_VERSION_RE.search(cargo_content)
    nu_dep_version = version_match.group(1) if version_match else None
    return {
        "is_plugin": is_plugin,
        "crate_name": crate_name,
        "nu_dep_version": nu_dep_version,
    }


def _nu_constraint_from_dep(dep_version: str | None) -> str | None:
    """Convert a Cargo nu-plugin dep version like '0.114.0' to a registry constraint."""
    if not dep_version:
        return None
    # Strip leading ^ or = if present
    dep_version = dep_version.lstrip("^=~ ")
    parts = dep_version.split(".")
    if len(parts) >= 2:
        major, minor = parts[0], parts[1]
        patch = parts[2] if len(parts) >= 3 else "0"
        return f">={major}.{minor}.{patch} <{major}.{int(minor) + 1}.0"
    return None


# ---------------------------------------------------------------------------
# GitHub discovery
# ---------------------------------------------------------------------------


def discover_github(repo: str, ref: str | None = None) -> dict:
    """Discover package metadata from a GitHub repository via gh CLI."""
    owner, name = repo.split("/", 1) if "/" in repo else (None, repo)
    if not owner:
        print(f"error: --repo must be owner/name format, got '{repo}'", file=sys.stderr)
        sys.exit(1)

    url = f"https://github.com/{owner}/{name}"

    # Repo metadata
    repo_info = gh_json(["api", f"repos/{owner}/{name}"])
    if repo_info is None:
        print(f"error: cannot fetch repo metadata for {owner}/{name}", file=sys.stderr)
        print("hint: ensure `gh auth status` succeeds", file=sys.stderr)
        sys.exit(1)

    description = repo_info.get("description") or ""
    license_info = repo_info.get("license") or {}
    license_spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None
    topics = repo_info.get("topics") or []

    # Releases: fetch by tag when --ref is set, otherwise latest 5
    if ref:
        releases_raw = gh_json(["api", f"repos/{owner}/{name}/releases/tags/{ref}"])
        if isinstance(releases_raw, dict):
            releases_raw = [releases_raw]
        elif releases_raw is None:
            releases_raw = []
    else:
        releases_raw = gh_json(["api", f"repos/{owner}/{name}/releases?per_page=5"])
    releases = []
    if isinstance(releases_raw, list):
        for rel in releases_raw:
            tag = rel.get("tag_name", "")
            if ref and tag != ref:
                continue
            assets = []
            for asset in rel.get("assets", []):
                asset_name = asset.get("name", "")
                suffix = _archive_suffix(asset_name)
                if suffix:
                    assets.append({
                        "name": asset_name,
                        "url": asset.get("browser_download_url", ""),
                        "size": asset.get("size", 0),
                        "suffix": suffix,
                    })
            if assets or not ref:
                releases.append({"tag": tag, "assets": assets})

    # Cargo.toml (for plugin detection)
    cargo_content = None
    cargo_b64 = gh_json(["api", f"repos/{owner}/{name}/contents/Cargo.toml"])
    if isinstance(cargo_b64, dict) and cargo_b64.get("content"):
        try:
            cargo_content = base64.b64decode(cargo_b64["content"]).decode("utf-8")
        except Exception:
            pass

    has_cargo = cargo_content is not None
    cargo_info = _classify_from_cargo(cargo_content) if cargo_content else {}
    has_nupm = False  # Would need another API call; skip for now unless ref given

    # Classification
    if cargo_info.get("is_plugin"):
        package_type = "plugin"
        confidence = "high"
        reason = "Cargo.toml depends on nu-plugin"
    elif name.startswith("nu_plugin_") or name.startswith("nu-plugin-"):
        package_type = "plugin"
        confidence = "medium"
        reason = "repository name matches plugin convention"
    elif "module" in topics or "nushell-module" in topics:
        package_type = "module"
        confidence = "medium"
        reason = "GitHub topics indicate module"
    elif "completion" in topics or "completions" in name:
        package_type = "completion"
        confidence = "medium"
        reason = "name/topics indicate completions"
    else:
        package_type = None
        confidence = "low"
        reason = "no strong signal; needs manual classification"

    nu_constraint = _nu_constraint_from_dep(cargo_info.get("nu_dep_version"))

    # Platform hints from release assets
    platform_hints = {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False}
    for rel in releases:
        for asset in rel.get("assets", []):
            aname = asset["name"].lower()
            if "windows" in aname or "win" in aname or "msvc" in aname:
                platform_hints["windows"] = True
            if "linux" in aname or "gnu" in aname:
                platform_hints["linux"] = True
            if "aarch64" in aname and ("apple" in aname or "darwin" in aname or "macos" in aname):
                platform_hints["macos_arm"] = True
            if "x86_64" in aname and ("apple" in aname or "darwin" in aname or "macos" in aname):
                platform_hints["macos_x64"] = True

    needs_decision = []
    if not nu_constraint:
        needs_decision.append("nu_version constraint not declared")
    needs_decision.append("verified_with")
    if package_type == "plugin" and not any(platform_hints.values()):
        needs_decision.append("exclude_targets")

    return {
        "schema_version": 1,
        "source": {"kind": "github", "url": url, "ref": ref},
        "facts": {
            "name": name,
            "owner": owner,
            "package_type": package_type,
            "license": license_spdx,
            "description": description,
            "has_cargo_toml": has_cargo,
            "has_nupm_metadata": has_nupm,
            "nu_constraint_hint": nu_constraint,
            "releases": releases,
        },
        "guesses": {
            "registry_type": package_type,
            "confidence": confidence,
            "reason": reason,
        },
        "needs_decision": needs_decision,
        "platform_hints": platform_hints,
    }


# ---------------------------------------------------------------------------
# Local discovery
# ---------------------------------------------------------------------------


def discover_local(path: Path) -> dict:
    """Discover package metadata from a local checkout."""
    if not path.is_dir():
        print(f"error: path '{path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    name = path.name
    owner = None  # Not inferable from local path alone

    # Cargo.toml
    cargo_toml = path / "Cargo.toml"
    has_cargo = cargo_toml.is_file()
    cargo_info = {}
    if has_cargo:
        cargo_info = _classify_from_cargo(cargo_toml.read_text(encoding="utf-8"))

    # nupm.nuon
    nupm_nuon = path / "nupm.nuon"
    has_nupm = nupm_nuon.is_file()

    # mod.nu
    has_mod_nu = (path / "mod.nu").is_file()
    if not has_mod_nu:
        # Check one level deep (e.g., pkgs/name/mod.nu)
        for child in path.iterdir():
            if child.is_dir() and (child / "mod.nu").is_file():
                has_mod_nu = True
                break

    # License
    license_spdx = None
    for lic_name in ("LICENSE", "LICENSE-MIT", "LICENSE.md", "LICENCE"):
        if (path / lic_name).is_file():
            content = (path / lic_name).read_text(encoding="utf-8", errors="replace")[:500]
            if "MIT" in content:
                license_spdx = "MIT"
            elif "Apache" in content:
                license_spdx = "Apache-2.0"
            else:
                license_spdx = "UNKNOWN"
            break

    # Classification
    if cargo_info.get("is_plugin"):
        package_type = "plugin"
        confidence = "high"
        reason = "Cargo.toml depends on nu-plugin"
    elif has_mod_nu:
        package_type = "module"
        confidence = "high"
        reason = "mod.nu found"
    elif has_nupm:
        package_type = "module"
        confidence = "medium"
        reason = "nupm.nuon present (assumed module)"
    elif "completion" in name:
        package_type = "completion"
        confidence = "medium"
        reason = "name suggests completions"
    else:
        package_type = None
        confidence = "low"
        reason = "no strong signal"

    nu_constraint = _nu_constraint_from_dep(cargo_info.get("nu_dep_version"))

    needs_decision = ["registry_owner"]
    if not nu_constraint:
        needs_decision.append("nu_version constraint not declared")
    needs_decision.append("verified_with")

    return {
        "schema_version": 1,
        "source": {"kind": "local", "url": str(path.resolve()), "ref": None},
        "facts": {
            "name": name,
            "owner": owner,
            "package_type": package_type,
            "license": license_spdx,
            "description": "",
            "has_cargo_toml": has_cargo,
            "has_nupm_metadata": has_nupm,
            "nu_constraint_hint": nu_constraint,
            "releases": [],
        },
        "guesses": {
            "registry_type": package_type,
            "confidence": confidence,
            "reason": reason,
        },
        "needs_decision": needs_decision,
        "platform_hints": {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: read-only repo discovery")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="GitHub repo as owner/name")
    group.add_argument("--path", help="Local directory path")
    parser.add_argument("--ref", help="Git ref (tag/branch) to focus on")
    parser.add_argument("--out", help="Write report to file instead of stdout")
    args = parser.parse_args()

    if args.repo:
        report = discover_github(args.repo, ref=args.ref)
    else:
        report = discover_local(Path(args.path))

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Discovery report written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
