#!/usr/bin/env python3
"""Audit awesome-nu inventory against numan-registry and numan-plugins."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

AWESOME_NU_DEFAULT_URL = (
    "https://raw.githubusercontent.com/nushell/awesome-nu/main/README.md"
)


def normalize_name(raw_name: str) -> str:
    """Normalize a package or tool name for fuzzy comparison."""
    clean = re.sub(r"\s+by\s+.*$", "", raw_name, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s*\(.*\)$", "", clean).strip()
    clean = clean.lower().replace("-", "_")
    if clean.endswith(".nu"):
        clean = clean[:-3]
    return clean


def parse_awesome_nu_markdown(content: str) -> dict[str, list[dict[str, str]]]:
    """Parse sections and items from awesome-nu markdown content."""
    item_re = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\):\s*(.*)$")
    sections: dict[str, list[dict[str, str]]] = {}
    curr_sec: str | None = None

    for line in content.splitlines():
        heading_match = re.match(r"^##\s+(.*)", line)
        if heading_match:
            curr_sec = heading_match.group(1).strip()
            sections[curr_sec] = []
        elif curr_sec and line.strip().startswith("- ["):
            item_match = item_re.match(line.strip())
            if item_match:
                name, url, desc = item_match.groups()
                sections[curr_sec].append(
                    {
                        "name": name.strip(),
                        "url": url.strip(),
                        "desc": desc.strip(),
                    }
                )

    return sections


def build_registry_indices(
    registry_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    """Build name-based and repo-based lookup indices for registry packages."""
    by_name: dict[str, Any] = {}
    by_repo: dict[str, list[Any]] = {}

    for pkg in registry_data.get("packages", []):
        name = pkg["id"]["name"].lower()
        owner = pkg["id"]["owner"].lower()
        repo = pkg.get("repo", "").lower().rstrip("/")

        by_name[name] = pkg
        by_name[f"{owner}/{name}"] = pkg

        if repo:
            by_repo.setdefault(repo, []).append(pkg)

    return by_name, by_repo


def build_manifest_indices(
    manifest_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build name-based and repo-based lookup indices for manifest plugins."""
    by_name: dict[str, Any] = {}
    by_repo: dict[str, Any] = {}

    for entry in manifest_data.get("active", []):
        c_name = entry.get("name", "").lower().replace("-", "_")
        repo = entry.get("repo", "").lower().rstrip("/")
        if c_name:
            by_name[c_name] = entry
        if repo:
            by_repo[repo] = entry

    return by_name, by_repo


def build_backlog_indices(
    backlog_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build name-based and repo-based lookup indices for backlog plugins."""
    by_name: dict[str, Any] = {}
    by_repo: dict[str, Any] = {}

    for entry in backlog_data.get("plugins", []):
        if "name" in entry:
            by_name[normalize_name(entry["name"])] = entry
        if "repo" in entry:
            by_repo[entry["repo"].lower().rstrip("/")] = entry

    return by_name, by_repo


def extract_repo_slug(url: str) -> str | None:
    """Extract repository slug from GitHub, Codeberg, or GitLab URL."""
    low = url.lower().rstrip("/")
    if "github.com/" in low:
        return low.split("github.com/")[-1].split("/tree/")[0]
    if "codeberg.org/" in low:
        return low.split("codeberg.org/")[-1].split("/src/")[0]
    if "gitlab.com/" in low:
        return low.split("gitlab.com/")[-1]
    return None


def match_registry_package(
    clean_name: str,
    url: str,
    by_name: dict[str, Any],
    by_repo: dict[str, list[Any]],
) -> Any | None:
    """Match an awesome-nu item to a registry package, disambiguating multi-package repos."""
    if clean_name in by_name:
        return by_name[clean_name]

    url_clean = url.lower().rstrip("/")
    candidates: list[Any] = []

    if url_clean in by_repo:
        candidates.extend(by_repo[url_clean])

    repo_slug = extract_repo_slug(url)
    for r_url, pkgs in by_repo.items():
        if (repo_slug and repo_slug in r_url) or (r_url and r_url in url_clean):
            for p in pkgs:
                if p not in candidates:
                    candidates.append(p)

    for p in candidates:
        p_norm = normalize_name(p["id"]["name"])
        if clean_name == p_norm or clean_name in p_norm or p_norm in clean_name:
            return p

    if len(candidates) == 1:
        return candidates[0]

    return None


def audit_plugins(
    items: list[dict[str, str]],
    reg_by_name: dict[str, Any],
    reg_by_repo: dict[str, list[Any]],
    man_by_name: dict[str, Any],
    man_by_repo: dict[str, Any],
    backlog_by_name: dict[str, Any],
    backlog_by_repo: dict[str, Any],
) -> list[dict[str, Any]]:
    """Audit plugins from awesome-nu against catalog and backlog."""
    results: list[dict[str, Any]] = []

    for item in items:
        raw_name = item["name"]
        c_name = normalize_name(raw_name)
        url = item["url"]
        repo_slug = extract_repo_slug(url)

        match_reg = match_registry_package(c_name, url, reg_by_name, reg_by_repo)
        if match_reg:
            results.append({"item": item, "status": "IN_REGISTRY", "match": match_reg})
            continue

        match_man = man_by_name.get(c_name)
        if not match_man and repo_slug:
            match_man = man_by_repo.get(repo_slug)
        if match_man:
            results.append({"item": item, "status": "IN_MANIFEST", "match": match_man})
            continue

        match_bl = backlog_by_name.get(c_name)
        if not match_bl and repo_slug:
            match_bl = backlog_by_repo.get(repo_slug)
        if match_bl:
            results.append({"item": item, "status": "IN_BACKLOG", "match": match_bl})
            continue

        results.append({"item": item, "status": "UNTRACKED", "match": None})

    return results


def format_plugin_audit(audit_results: list[dict[str, Any]]) -> str:
    """Format plugin audit results into report string."""
    in_reg = [r for r in audit_results if r["status"] == "IN_REGISTRY"]
    in_man = [r for r in audit_results if r["status"] == "IN_MANIFEST"]
    in_bl = [r for r in audit_results if r["status"] == "IN_BACKLOG"]
    untracked = [r for r in audit_results if r["status"] == "UNTRACKED"]

    lines = [
        "=================================================================",
        "PLUGINS AUDIT",
        "=================================================================",
        f"Awesome-Nu Plugins Total: {len(audit_results)}",
        f"  [+] In Numan Registry: {len(in_reg)}",
        f"  [~] In numan-plugins CI Manifest: {len(in_man)}",
        f"  [.] In numan-plugins Backlog: {len(in_bl)}",
        f"  [-] Untracked / Missing: {len(untracked)}",
        "",
        "[+] IN REGISTRY:",
    ]

    for r in sorted(in_reg, key=lambda x: x["match"]["id"]["name"]):
        pkg = r["match"]
        versions = [f"{v['version']} (Nu: {v.get('nu_version', '*')})" for v in pkg.get("versions", [])]
        lines.append(f"  * {pkg['id']['owner']}/{pkg['id']['name']} (awesome-nu: '{r['item']['name']}')")
        lines.append(f"      Versions: {', '.join(versions)}")

    lines.extend(["", "[-] UNTRACKED CANDIDATES:"])
    for r in untracked:
        lines.append(f"  * {r['item']['name']} ({r['item']['url']}) - {r['item']['desc']}")

    return "\n".join(lines)


def fetch_readme(path: Path | None, url: str = AWESOME_NU_DEFAULT_URL) -> str:
    """Read awesome-nu README from local path or fetch via HTTP."""
    if path and path.exists():
        return path.read_text(encoding="utf-8")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "numan-catalog-audit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def load_json_file(path: Path | None, fallback: dict[str, Any]) -> dict[str, Any]:
    """Safely load JSON file or return fallback dict."""
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return fallback


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for audit_awesome_nu."""
    parser = argparse.ArgumentParser(description="Audit awesome-nu catalog coverage")
    parser.add_argument("--readme", type=Path, default=None, help="Path to awesome-nu README.md")
    parser.add_argument("--index", type=Path, default=Path(__file__).resolve().parent.parent / "registry" / "index.json")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent.parent.parent / "numan-plugins" / "manifest.json")
    parser.add_argument("--backlog", type=Path, default=Path(__file__).resolve().parent.parent.parent / "numan-plugins" / "docs" / "backlog.json")
    args = parser.parse_args(argv)

    readme_content = fetch_readme(args.readme)
    sections = parse_awesome_nu_markdown(readme_content)

    reg_data = load_json_file(args.index, {"packages": []})
    man_data = load_json_file(args.manifest, {"active": []})
    bl_data = load_json_file(args.backlog, {"plugins": []})

    reg_by_name, reg_by_repo = build_registry_indices(reg_data)
    man_by_name, man_by_repo = build_manifest_indices(man_data)
    bl_by_name, bl_by_repo = build_backlog_indices(bl_data)

    plugin_results = audit_plugins(
        sections.get("Plugins", []),
        reg_by_name,
        reg_by_repo,
        man_by_name,
        man_by_repo,
        bl_by_name,
        bl_by_repo,
    )

    report = format_plugin_audit(plugin_results)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
