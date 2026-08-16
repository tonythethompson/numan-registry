#!/usr/bin/env python3
"""Unit tests for audit_awesome_nu.py."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "audit_awesome_nu.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_awesome_nu", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = load_module()


class NormalizeNameTests(unittest.TestCase):
    def test_strip_author_and_decorations(self):
        self.assertEqual(audit.normalize_name("nu_plugin_plist by ainvaltin"), "nu_plugin_plist")
        self.assertEqual(audit.normalize_name("nu_plugin_template (cargo-generate template)"), "nu_plugin_template")
        self.assertEqual(audit.normalize_name("ai.nu"), "ai")
        self.assertEqual(audit.normalize_name("nu-git-manager"), "nu_git_manager")


class ParseAwesomeNuMarkdownTests(unittest.TestCase):
    def test_parse_sections_and_items(self):
        content = """# Awesome Nu

## Plugins

- [nu_plugin_audio](https://github.com/SuaveIV/nu_plugin_audio): Audio plugin for Nu.
- [nu_plugin_bio](https://github.com/Euphrasiologist/nu_plugin_bio): Bioinformatics plugin.

## Scripts

- [ai.nu](https://github.com/fj0r/ai.nu): AI client.
"""
        sections = audit.parse_awesome_nu_markdown(content)
        self.assertIn("Plugins", sections)
        self.assertIn("Scripts", sections)
        self.assertEqual(len(sections["Plugins"]), 2)
        self.assertEqual(sections["Plugins"][0]["name"], "nu_plugin_audio")
        self.assertEqual(sections["Plugins"][0]["url"], "https://github.com/SuaveIV/nu_plugin_audio")
        self.assertEqual(sections["Scripts"][0]["name"], "ai.nu")


class RegistryIndicesAndMatchingTests(unittest.TestCase):
    def setUp(self):
        self.reg_data = {
            "packages": [
                {
                    "id": {"owner": "SuaveIV", "name": "nu_plugin_audio"},
                    "repo": "https://github.com/SuaveIV/nu_plugin_audio",
                    "type": "plugin",
                    "versions": [{"version": "0.2.10", "nu_version": "0.114.1"}],
                },
                {
                    "id": {"owner": "nushell", "name": "git-completions"},
                    "repo": "https://github.com/nushell/nu_scripts/tree/main/custom-completions/git",
                    "type": "completion",
                    "versions": [{"version": "0.1.0", "nu_version": "*"}],
                },
                {
                    "id": {"owner": "nushell", "name": "cargo-completions"},
                    "repo": "https://github.com/nushell/nu_scripts/tree/main/custom-completions/cargo",
                    "type": "completion",
                    "versions": [{"version": "0.1.0", "nu_version": "*"}],
                },
            ]
        }
        self.by_name, self.by_repo = audit.build_registry_indices(self.reg_data)

    def test_direct_name_match(self):
        pkg = audit.match_registry_package("nu_plugin_audio", "https://github.com/SuaveIV/nu_plugin_audio", self.by_name, self.by_repo)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg["id"]["name"], "nu_plugin_audio")

    def test_multi_package_repo_disambiguation(self):
        pkg_git = audit.match_registry_package("git_completions", "https://github.com/nushell/nu_scripts", self.by_name, self.by_repo)
        self.assertIsNotNone(pkg_git)
        self.assertEqual(pkg_git["id"]["name"], "git-completions")

        pkg_cargo = audit.match_registry_package("cargo_completions", "https://github.com/nushell/nu_scripts", self.by_name, self.by_repo)
        self.assertIsNotNone(pkg_cargo)
        self.assertEqual(pkg_cargo["id"]["name"], "cargo-completions")

    def test_exact_name_preferred_over_substring(self):
        reg_data = {
            "packages": [
                {"id": {"owner": "a", "name": "nu-git-manager"}, "repo": "https://github.com/a/tools"},
                {"id": {"owner": "a", "name": "nu-git-manager-sugar"}, "repo": "https://github.com/a/tools"},
            ]
        }
        by_name, by_repo = audit.build_registry_indices(reg_data)
        pkg = audit.match_registry_package(
            "nu_git_manager_sugar",
            "https://github.com/a/tools",
            by_name,
            by_repo,
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg["id"]["name"], "nu-git-manager-sugar")


class AuditPluginsTests(unittest.TestCase):
    def test_audit_plugins_categorization(self):
        items = [
            {"name": "nu_plugin_audio", "url": "https://github.com/SuaveIV/nu_plugin_audio", "desc": "Audio plugin"},
            {"name": "nu_plugin_plot", "url": "https://github.com/Euphrasiologist/nu_plugin_plot", "desc": "Plotting"},
            {"name": "nu_plugin_unknown", "url": "https://github.com/someone/nu_plugin_unknown", "desc": "Unknown"},
        ]
        reg_by_name = {"nu_plugin_audio": {"id": {"owner": "SuaveIV", "name": "nu_plugin_audio"}, "versions": []}}
        reg_by_repo = {}
        man_by_name = {}
        man_by_repo = {}
        backlog_by_name = {"nu_plugin_plot": {"name": "nu_plugin_plot", "status": "NO_RELEASE"}}
        backlog_by_repo = {}

        results = audit.audit_plugins(
            items, reg_by_name, reg_by_repo, man_by_name, man_by_repo, backlog_by_name, backlog_by_repo
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "IN_REGISTRY")
        self.assertEqual(results[1]["status"], "IN_BACKLOG")
        self.assertEqual(results[2]["status"], "UNTRACKED")

    def test_manifest_and_backlog_repo_slug_matching(self):
        man_data = {
            "active": [
                {
                    "name": "nu_plugin_custom",
                    "repo": "https://github.com/org/custom-plugin-repo",
                }
            ]
        }
        man_by_name, man_by_repo = audit.build_manifest_indices(man_data)
        self.assertIn("org/custom-plugin-repo", man_by_repo)

        bl_data = {
            "plugins": [
                {
                    "name": "nu_plugin_future",
                    "repo": "https://github.com/org/future-plugin-repo",
                }
            ]
        }
        bl_by_name, bl_by_repo = audit.build_backlog_indices(bl_data)
        self.assertIn("org/future-plugin-repo", bl_by_repo)

        items = [
            {"name": "different_display_name", "url": "https://github.com/org/custom-plugin-repo", "desc": "Custom"},
            {"name": "another_display_name", "url": "https://github.com/org/future-plugin-repo", "desc": "Future"},
        ]
        results = audit.audit_plugins(
            items, {}, {}, man_by_name, man_by_repo, bl_by_name, bl_by_repo
        )
        self.assertEqual(results[0]["status"], "IN_MANIFEST")
        self.assertEqual(results[1]["status"], "IN_BACKLOG")


class FetchReadmeAndMainTests(unittest.TestCase):
    def test_fetch_readme_local(self):
        with mock.patch.object(Path, "exists", return_value=True):
            with mock.patch.object(Path, "read_text", return_value="## Plugins\n- [a](b): c"):
                content = audit.fetch_readme(Path("dummy.md"))
                self.assertIn("## Plugins", content)

    def test_load_json_file_remote_fallback(self):
        with mock.patch.object(Path, "exists", return_value=False):
            with mock.patch.object(audit, "fetch_readme", return_value='{"active": ["mock"]}'):
                data = audit.load_json_file(
                    Path("missing.json"),
                    fallback_url="https://example.com/manifest.json",
                )
                self.assertEqual(data, {"active": ["mock"]})

    def test_load_json_file_fallback_failure_raises(self):
        with mock.patch.object(Path, "exists", return_value=False):
            with mock.patch.object(audit, "fetch_readme", side_effect=RuntimeError("connection error")):
                with self.assertRaises(RuntimeError):
                    audit.load_json_file(
                        Path("missing.json"),
                        fallback_url="https://example.com/manifest.json",
                        dataset_name="test manifest",
                    )

    def test_main_cli(self):
        with mock.patch.object(audit, "fetch_readme", return_value="## Plugins\n- [nu_plugin_audio](https://github.com/SuaveIV/nu_plugin_audio): Audio"):
            with mock.patch.object(audit, "load_json_file", return_value={"packages": []}):
                exit_code = audit.main(["--readme", "fake.md"])
                self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
