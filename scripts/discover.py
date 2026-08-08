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
import sys
from pathlib import Path

from archive_formats import SUPPORTED_ARCHIVE_SUFFIXES
from gh_helpers import gh_json, gh_text

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

_NU_PLUGIN_DEP_RE = re.compile(r'nu-plugin\s*=\s*["\{]')
_NU_PROTOCOL_DEP_RE = re.compile(r'nu-protocol\s*=\s*["\{]')
_NU_VERSION_RE = re.compile(r'nu-plugin\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"')
_CRATE_NAME_RE = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)

# Platform tokens matched (lowercased) against release asset filenames.
_WINDOWS_TOKENS = ("windows", "win64", "win32", "win-x64", "win-arm64", "msvc")
_LINUX_TOKENS = ("linux", "gnu")
_MACOS_TOKENS = ("apple", "darwin", "macos")
_ARM_TOKENS = ("aarch64",)
_X64_TOKENS = ("x86_64",)


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
        try:
            next_minor = int(minor) + 1
        except ValueError:
            return None
        return f">={major}.{minor}.{patch} <{major}.{next_minor}.0"
    return None


# ---------------------------------------------------------------------------
# GitHub discovery
# ---------------------------------------------------------------------------


def _fetch_repo_info(owner: str, name: str) -> dict:
    """Fetch GitHub repo metadata, exiting if it cannot be retrieved."""
    repo_info = gh_json(["api", f"repos/{owner}/{name}"])
    if not isinstance(repo_info, dict):
        print(f"error: cannot fetch repo metadata for {owner}/{name}", file=sys.stderr)
        print("hint: ensure `gh auth status` succeeds", file=sys.stderr)
        sys.exit(1)
    return repo_info


def _release_assets(rel: dict) -> list[dict]:
    """Map supported archive assets of a release to the report shape."""
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
    return assets


def _fetch_releases(owner: str, name: str, ref: str | None) -> list[dict]:
    """Fetch releases, filtered to the requested tag (or latest 5)."""
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
            assets = _release_assets(rel)
            if assets or not ref:
                releases.append({"tag": tag, "assets": assets})
    return releases


def _fetch_cargo(owner: str, name: str) -> str | None:
    """Fetch and decode Cargo.toml content (or None when absent/undecodable)."""
    cargo_b64 = gh_json(["api", f"repos/{owner}/{name}/contents/Cargo.toml"])
    if not (isinstance(cargo_b64, dict) and cargo_b64.get("content")):
        return None
    try:
        return base64.b64decode(cargo_b64["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"warning: cannot decode Cargo.toml content: {exc}", file=sys.stderr)
        return None


def _classify_github(name: str, cargo_info: dict, topics: list) -> tuple[str | None, str, str]:
    """Classify a GitHub repo into (package_type, confidence, reason)."""
    if cargo_info.get("is_plugin"):
        return "plugin", "high", "Cargo.toml depends on nu-plugin"
    if name.startswith(("nu_plugin_", "nu-plugin-")):
        return "plugin", "medium", "repository name matches plugin convention"
    if "module" in topics or "nushell-module" in topics:
        return "module", "medium", "GitHub topics indicate module"
    if "completion" in topics or "completions" in name:
        return "completion", "medium", "name/topics indicate completions"
    return None, "low", "no strong signal; needs manual classification"


def _platform_hints(releases: list[dict]) -> dict:
    """Derive platform hints from release asset filenames."""
    hints = {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False}
    for rel in releases:
        for asset in rel.get("assets", []):
            aname = asset["name"].lower()
            if any(token in aname for token in _WINDOWS_TOKENS):
                hints["windows"] = True
            if any(token in aname for token in _LINUX_TOKENS):
                hints["linux"] = True
            if any(token in aname for token in _ARM_TOKENS) and any(token in aname for token in _MACOS_TOKENS):
                hints["macos_arm"] = True
            if any(token in aname for token in _X64_TOKENS) and any(token in aname for token in _MACOS_TOKENS):
                hints["macos_x64"] = True
    return hints


def _needs_decision(nu_constraint: str | None, package_type: str | None,
                    platform_hints: dict) -> list[str]:
    """Build the needs_decision list for a GitHub discovery."""
    needs = []
    if not nu_constraint:
        needs.append("nu_version constraint not declared")
    needs.append("verified_with")
    if package_type == "plugin" and not any(platform_hints.values()):
        needs.append("exclude_targets")
    return needs


def discover_github(repo: str, ref: str | None = None) -> dict:
    """Discover package metadata from a GitHub repository via gh CLI."""
    owner, name = repo.split("/", 1) if "/" in repo else (None, repo)
    if not owner or not name:
        print(f"error: --repo must be owner/name format, got '{repo}'", file=sys.stderr)
        sys.exit(1)

    url = f"https://github.com/{owner}/{name}"
    repo_info = _fetch_repo_info(owner, name)

    description = repo_info.get("description") or ""
    license_info = repo_info.get("license") or {}
    license_spdx = license_info.get("spdx_id") if isinstance(license_info, dict) else None
    topics = repo_info.get("topics") or []

    releases = _fetch_releases(owner, name, ref)

    cargo_content = _fetch_cargo(owner, name)
    has_cargo = cargo_content is not None
    cargo_info = _classify_from_cargo(cargo_content) if cargo_content else {}
    has_nupm = False  # Would need another API call; skip for now unless ref given

    package_type, confidence, reason = _classify_github(name, cargo_info, topics)
    nu_constraint = _nu_constraint_from_dep(cargo_info.get("nu_dep_version"))
    platform_hints = _platform_hints(releases)

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
        "needs_decision": _needs_decision(nu_constraint, package_type, platform_hints),
        "platform_hints": platform_hints,
    }


# ---------------------------------------------------------------------------
# Local discovery
# ---------------------------------------------------------------------------

_LICENSE_FILE_NAMES = ("LICENSE", "LICENSE-MIT", "LICENSE.md", "LICENCE")


def _probe_cargo(path: Path) -> tuple[bool, dict]:
    """Probe a checkout for Cargo.toml, returning (present, classified content)."""
    cargo_toml = path / "Cargo.toml"
    if not cargo_toml.is_file():
        return False, {}
    try:
        content = cargo_toml.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"warning: cannot read Cargo.toml: {exc}", file=sys.stderr)
        return False, {}
    return True, _classify_from_cargo(content)


def _probe_nupm(path: Path) -> bool:
    """Return whether the checkout declares nupm metadata."""
    return (path / "nupm.nuon").is_file()


def _probe_mod_nu(path: Path) -> bool:
    """Return whether the checkout has mod.nu at root or one level deep."""
    if (path / "mod.nu").is_file():
        return True
    for child in path.iterdir():
        if child.is_dir() and (child / "mod.nu").is_file():
            return True
    return False


def _detect_license(path: Path) -> str | None:
    """Detect the SPDX id from common license files (MIT / Apache-2.0 / UNKNOWN)."""
    for lic_name in _LICENSE_FILE_NAMES:
        lic_path = path / lic_name
        if not lic_path.is_file():
            continue
        content = lic_path.read_text(encoding="utf-8", errors="replace")[:500]
        if "MIT" in content:
            return "MIT"
        if "Apache" in content:
            return "Apache-2.0"
        return "UNKNOWN"
    return None


def _classify_local(name: str, cargo_info: dict, has_mod_nu: bool,
                    has_nupm: bool) -> tuple[str | None, str, str]:
    """Classify a local checkout into (package_type, confidence, reason)."""
    if cargo_info.get("is_plugin"):
        return "plugin", "high", "Cargo.toml depends on nu-plugin"
    if has_mod_nu:
        return "module", "high", "mod.nu found"
    if has_nupm:
        return "module", "medium", "nupm.nuon present (assumed module)"
    if "completion" in name:
        return "completion", "medium", "name suggests completions"
    return None, "low", "no strong signal"


def discover_local(path: Path) -> dict:
    """Discover package metadata from a local checkout."""
    if not path.is_dir():
        print(f"error: path '{path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    name = path.name
    owner = None  # Not inferable from local path alone

    has_cargo, cargo_info = _probe_cargo(path)
    has_nupm = _probe_nupm(path)
    has_mod_nu = _probe_mod_nu(path)
    license_spdx = _detect_license(path)

    package_type, confidence, reason = _classify_local(name, cargo_info, has_mod_nu, has_nupm)
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
