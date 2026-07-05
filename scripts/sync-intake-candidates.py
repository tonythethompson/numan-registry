#!/usr/bin/env python3
"""Regenerate docs/intake-candidates.md from intake-state.json + live signals.

Reads registry/index.json (what is pinned), optional gh CLI (open PRs, outreach
issues), and writes an updated markdown doc plus the outreach tracker table in
docs/upstream-release-outreach.md.

Usage:
  python scripts/sync-intake-candidates.py
  python scripts/sync-intake-candidates.py --hook stop   # Cursor hook entry
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "docs" / "intake-state.json"
OUT_PATH = REPO_ROOT / "docs" / "intake-candidates.md"
INDEX_PATH = REPO_ROOT / "registry" / "index.json"
OUTREACH_DOC = REPO_ROOT / "docs" / "upstream-release-outreach.md"
REGISTRY_REPO = "tonythethompson/numan-registry"


def gh_json(args: list[str]) -> Any | None:
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
    return json.loads(out.stdout)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def registry_packages(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    live: dict[str, dict[str, Any]] = {}
    for pkg in index.get("packages", []):
        pid = pkg["id"]
        key = f"{pid['owner']}/{pid['name']}"
        versions = pkg.get("versions", [])
        latest = versions[-1] if versions else {}
        artifact = latest.get("artifact", {})
        url = artifact.get("url") or ""
        if artifact.get("kind") == "binary":
            targets = artifact.get("targets", {})
            url = next(iter(targets.values()), {}).get("url", "")
        mirror = "numan-registry/releases/download/mirror-" in url
        live[key] = {
            "version": latest.get("version", "?"),
            "mirror": mirror,
            "upstream_asset": not mirror and url.startswith("http"),
        }
    return live


def pr_state(number: int | None) -> str | None:
    if not number:
        return None
    data = gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            REGISTRY_REPO,
            "--json",
            "state,mergedAt,url",
        ]
    )
    if not data:
        return None
    state = data.get("state", "").upper()
    if state == "MERGED":
        return "merged"
    if state == "OPEN":
        return "open"
    if state == "CLOSED":
        return "closed"
    return state.lower() if state else None


def outreach_status(outreach: dict[str, Any]) -> dict[str, str]:
    """Return outreach fields: issue, opened, response, upstream_shipped."""
    result = {
        "issue": "",
        "opened": "",
        "response": "",
        "upstream_shipped": "",
        "summary": "not started",
    }
    repo = outreach.get("upstream_repo")
    if not repo:
        return result

    issue_url = outreach.get("issue_url")
    issue_number: int | None = None
    if issue_url:
        m = re.search(r"/issues/(\d+)", issue_url)
        if m:
            issue_number = int(m.group(1))

    if issue_number is None:
        search = " ".join(outreach.get("search_terms", ["numan", "release zip"]))
        found = gh_json(
            [
                "issue",
                "list",
                "--repo",
                repo,
                "--author",
                "@me",
                "--state",
                "all",
                "--search",
                search,
                "--limit",
                "3",
                "--json",
                "number,title,state,url,comments,updatedAt",
            ]
        )
        if found:
            issue_number = found[0]["number"]
            issue_url = found[0]["url"]
            outreach["issue_url"] = issue_url  # persist discovery

    if issue_number is None:
        result["summary"] = "outreach pending"
        return result

    detail = gh_json(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "number,title,state,url,comments,createdAt,updatedAt",
        ]
    )
    if not detail:
        result["issue"] = issue_url or f"{repo}#{issue_number}"
        result["summary"] = "issue filed (status unknown)"
        return result

    result["issue"] = f"[#{detail['number']}]({detail['url']})"
    created = detail.get("createdAt", "")[:10]
    result["opened"] = created

    comments = gh_json(
        [
            "api",
            f"repos/{repo}/issues/{issue_number}/comments",
            "--jq",
            "[.[] | {user: .user.login, created_at: .created_at}]",
        ]
    )
    me = gh_json(["api", "user", "--jq", ".login"])
    if comments and me:
        others = [c for c in comments if c.get("user") != me]
        if others:
            result["response"] = f"yes ({others[-1]['created_at'][:10]})"
            result["summary"] = f"responded — see {repo}#{issue_number}"
        else:
            result["response"] = "awaiting"
            result["summary"] = f"issue open, awaiting response ({repo}#{issue_number})"
    else:
        result["response"] = "awaiting"
        result["summary"] = f"issue open ({repo}#{issue_number})"

    if detail.get("state") == "CLOSED":
        result["summary"] = f"issue closed ({repo}#{issue_number})"

    return result


def package_status(
    entry: dict[str, Any],
    live: dict[str, dict[str, Any]],
    pr_map: dict[int, str | None],
) -> str:
    pid = entry["id"]
    version = entry.get("version", "")
    note = entry.get("note")
    pr_num = entry.get("pr")
    parts: list[str] = []

    if pid in live:
        info = live[pid]
        if info.get("mirror"):
            parts.append("live (registry mirror)")
        elif info.get("upstream_asset"):
            parts.append("live (upstream asset)")
        else:
            parts.append("live")
        if version and info.get("version") != version:
            parts.append(f"index@{info['version']}")
    elif pr_num:
        ps = pr_map.get(pr_num)
        if ps == "merged":
            parts.append(f"merged in [#{pr_num}](https://github.com/{REGISTRY_REPO}/pull/{pr_num}) — publish pending?")
        elif ps == "open":
            parts.append(f"PR [#{pr_num}](https://github.com/{REGISTRY_REPO}/pull/{pr_num}) open")
        elif ps == "closed":
            parts.append(f"PR #{pr_num} closed (not merged)")
        else:
            parts.append(f"pending [#{pr_num}](https://github.com/{REGISTRY_REPO}/pull/{pr_num})")
    else:
        spec = entry.get("spec")
        if spec and (REPO_ROOT / spec).exists():
            parts.append("spec written, not in index")
        else:
            parts.append("candidate")

    outreach = entry.get("outreach")
    if outreach:
        o = outreach_status(outreach)
        parts.append(f"outreach: {o['summary']}")

    if note:
        parts.append(note)

    return " — ".join(parts)


def render_intake_doc(
    state: dict[str, Any], live: dict[str, dict[str, Any]], index: dict[str, Any]
) -> str:
    pr_nums = {
        e.get("pr")
        for section in ("ready", "mirror")
        for e in state.get(section, [])
        if e.get("pr")
    }
    pr_map = {n: pr_state(n) for n in pr_nums if n}

    registry_summary = []
    for key in sorted(live):
        info = live[key]
        kind = "mirror" if info.get("mirror") else "upstream"
        registry_summary.append(f"`{key}@{info['version']}` ({kind})")
    # Include multi-version packages explicitly (e.g. nutest).
    for pkg in index.get("packages", []):
        pid = pkg["id"]
        key = f"{pid['owner']}/{pid['name']}"
        versions = [v.get("version") for v in pkg.get("versions", []) if v.get("version")]
        if len(versions) > 1:
            registry_summary = [s for s in registry_summary if not s.startswith(f"`{key}@")]
            registry_summary.append(f"`{key}` ({', '.join(versions)})")
    registry_line = ", ".join(registry_summary) if registry_summary else "(none)"

    lines = [
        "# Registry intake candidates",
        "",
        "Running list of packages evaluated for the official Numan registry.",
        f"_Auto-synced {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from `docs/intake-state.json`, `registry/index.json`, and GitHub (via `gh`). Edit `intake-state.json` to add candidates; run `python scripts/sync-intake-candidates.py` to refresh._",
        "",
        "**Intake rules:** artifact must be `.zip`, `.tar.gz`, `.tgz`, or `.tar` (not `.tar.xz`); prefer upstream uploaded release assets over GitHub auto-generated `/archive/` zipballs; never hand-type `sha256` (use `scripts/add-package.py`); mirror packages via `scripts/build-mirror-zip.py` + registry release upload. See [upstream-release-outreach.md](upstream-release-outreach.md) for contacting maintainers to ship upstream assets.",
        "",
        f"**Currently in registry:** {registry_line}.",
        "",
        "---",
        "",
        "## Ready to add now",
        "",
        "Upstream ships byte-stable release assets in Numan-supported formats.",
        "",
        "| Package | Type | Version | Platforms | Status |",
        "|---------|------|---------|-----------|--------|",
    ]

    for entry in state.get("ready", []):
        link = f"[`{entry['id']}`]({entry['repo']})"
        status = package_status(entry, live, pr_map)
        lines.append(
            f"| {link} | {entry['type']} | v{entry['version']} | {entry['platforms']} | {status} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Worth adding via registry mirror",
            "",
            "No compliant upstream release asset; pack a tag/commit snapshot as a registry-hosted zip (see `scripts/build-mirror-zip.py`).",
            "",
            "| Package | Type | Source | Status |",
            "|---------|------|--------|--------|",
        ]
    )

    for entry in state.get("mirror", []):
        link = f"[`{entry['id']}`]({entry['repo']})"
        status = package_status(entry, live, pr_map)
        lines.append(
            f"| {link} | {entry['type']} | {entry['source']} | {status} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Blocked for now",
            "",
            "| Package | Blocker |",
            "|---------|---------|",
        ]
    )
    for entry in state.get("blocked", []):
        pkg = entry["id"]
        if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", pkg):
            link = f"[`{pkg}`](https://github.com/{pkg})"
        else:
            link = pkg
        lines.append(f"| {link} | {entry['blocker']} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Changelog",
            "",
            "| Date | Change |",
            "|------|--------|",
        ]
    )
    for row in state.get("changelog", []):
        lines.append(f"| {row['date']} | {row['change']} |")

    lines.append("")
    return "\n".join(lines)


def update_outreach_tracker(state: dict[str, Any], live: dict[str, dict[str, Any]]) -> bool:
    if not OUTREACH_DOC.exists():
        return False

    text = OUTREACH_DOC.read_text(encoding="utf-8")
    start = text.find("## Outreach tracker")
    if start == -1:
        return False
    end = text.find("\n---\n", start + 1)
    if end == -1:
        return False

    rows = [
        "| Upstream | Issue/PR | Opened | Response | Upstream asset shipped | Registry switched |",
        "|----------|----------|--------|----------|------------------------|-------------------|",
    ]

    for entry in state.get("mirror", []):
        outreach = entry.get("outreach") or {}
        if entry["owner"] == "nushell" and entry["name"] != "nu_scripts":
            upstream = f"nushell/nu_scripts ({entry['name']})"
        else:
            upstream = entry["id"]
        o = outreach_status(outreach) if outreach else {}
        pid = entry["id"]
        switched = ""
        if pid in live and not live[pid].get("mirror"):
            switched = "yes"
        elif pid in live:
            switched = "mirror only"
        rows.append(
            "| "
            + " | ".join(
                [
                    upstream,
                    o.get("issue", ""),
                    o.get("opened", ""),
                    o.get("response", ""),
                    o.get("upstream_shipped", ""),
                    switched,
                ]
            )
            + " |"
        )

    new_section = "## Outreach tracker\n\n" + "\n".join(rows) + "\n\n"
    updated = text[:start] + new_section + text[end + 1 :]
    if updated == text:
        return False
    OUTREACH_DOC.write_text(updated, encoding="utf-8", newline="\n")
    return True


def sync() -> bool:
    if not STATE_PATH.exists():
        print(f"FAIL: missing {STATE_PATH}", file=sys.stderr)
        return False

    state = load_json(STATE_PATH)
    state_dirty = False

    index = load_json(INDEX_PATH) if INDEX_PATH.exists() else {"packages": []}
    live = registry_packages(index)

    # Persist auto-discovered issue URLs back into state.
    for section in ("mirror",):
        for entry in state.get(section, []):
            outreach = entry.get("outreach")
            if outreach:
                before = outreach.get("issue_url")
                outreach_status(outreach)
                if outreach.get("issue_url") != before:
                    state_dirty = True

    doc = render_intake_doc(state, live, index)
    existing = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
    changed = False
    if existing != doc:
        OUT_PATH.write_text(doc, encoding="utf-8", newline="\n")
        changed = True

    if update_outreach_tracker(state, live):
        changed = True

    if state_dirty:
        STATE_PATH.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        changed = True

    return changed


def hook_main(hook_name: str) -> int:
    payload_raw = sys.stdin.read()
    payload: dict[str, Any] = {}
    if payload_raw.strip():
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}

    if hook_name == "afterShellExecution":
        cmd = payload.get("command", "")
        triggers = ("gh ", "add-package.py", "build-mirror-zip.py", "sync-intake-candidates.py")
        if not any(t in cmd for t in triggers):
            print("{}")
            return 0

    if hook_name == "afterFileEdit":
        path = (payload.get("file_path") or payload.get("path") or "").replace("\\", "/")
        triggers = ("registry/index.json", "specs/", "intake-state.json")
        if path and not any(t in path for t in triggers):
            print("{}")
            return 0

    changed = sync()
    if hook_name == "stop" and changed:
        print(
            json.dumps(
                {
                    "followup_message": (
                        "Synced docs/intake-candidates.md (and outreach tracker) from "
                        "registry index + GitHub outreach state."
                    )
                }
            )
        )
    else:
        print("{}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hook",
        choices=("stop", "afterShellExecution", "afterFileEdit"),
        help="Cursor hook entry point (reads JSON from stdin)",
    )
    args = parser.parse_args()

    if args.hook:
        return hook_main(args.hook)

    changed = sync()
    print("OK: updated intake docs" if changed else "OK: intake docs already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
