#!/usr/bin/env python3.12
"""Tests for scripts/discover.py (Stage 3: repo discovery)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import discover


class TestClassifyFromCargo(unittest.TestCase):
    def test_plugin_detected(self):
        cargo = '[package]\nname = "nu_plugin_foo"\n\n[dependencies]\nnu-plugin = { version = "0.114.0" }\n'
        info = discover._classify_from_cargo(cargo)
        self.assertTrue(info["is_plugin"])
        self.assertEqual(info["crate_name"], "nu_plugin_foo")
        self.assertEqual(info["nu_dep_version"], "0.114.0")

    def test_non_plugin(self):
        cargo = '[package]\nname = "some-crate"\n\n[dependencies]\nserde = "1.0"\n'
        info = discover._classify_from_cargo(cargo)
        self.assertFalse(info["is_plugin"])
        self.assertEqual(info["crate_name"], "some-crate")
        self.assertIsNone(info["nu_dep_version"])

    def test_nu_protocol_only(self):
        cargo = '[package]\nname = "nu_thing"\n\n[dependencies]\nnu-protocol = "0.113.0"\n'
        info = discover._classify_from_cargo(cargo)
        self.assertTrue(info["is_plugin"])


class TestNuConstraint(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(discover._nu_constraint_from_dep("0.114.0"), ">=0.114.0 <0.115.0")

    def test_caret_prefix(self):
        self.assertEqual(discover._nu_constraint_from_dep("^0.113.1"), ">=0.113.1 <0.114.0")

    def test_none(self):
        self.assertIsNone(discover._nu_constraint_from_dep(None))


class TestArchiveSuffix(unittest.TestCase):
    def test_zip(self):
        self.assertEqual(discover._archive_suffix("foo-windows.zip"), ".zip")

    def test_tar_gz(self):
        self.assertEqual(discover._archive_suffix("foo-linux.tar.gz"), ".tar.gz")

    def test_unsupported(self):
        self.assertIsNone(discover._archive_suffix("foo.exe"))
        self.assertIsNone(discover._archive_suffix("README.md"))


class TestDiscoverLocal(unittest.TestCase):
    def test_plugin_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "Cargo.toml").write_text(
                '[package]\nname = "nu_plugin_test"\n\n[dependencies]\nnu-plugin = { version = "0.114.0" }\n'
            )
            report = discover.discover_local(p)
            self.assertEqual(report["facts"]["package_type"], "plugin")
            self.assertTrue(report["facts"]["has_cargo_toml"])
            self.assertEqual(report["guesses"]["confidence"], "high")
            self.assertEqual(report["facts"]["nu_constraint_hint"], ">=0.114.0 <0.115.0")

    def test_module_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "mod.nu").write_text("export def hello [] { 'hi' }\n")
            report = discover.discover_local(p)
            self.assertEqual(report["facts"]["package_type"], "module")
            self.assertEqual(report["guesses"]["reason"], "mod.nu found")

    def test_unknown_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "README.md").write_text("# Something\n")
            report = discover.discover_local(p)
            self.assertIsNone(report["facts"]["package_type"])
            self.assertEqual(report["guesses"]["confidence"], "low")

    def test_license_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "mod.nu").write_text("")
            (p / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026\n")
            report = discover.discover_local(p)
            self.assertEqual(report["facts"]["license"], "MIT")


class TestDiscoverGithub(unittest.TestCase):
    @patch("discover.gh_json")
    def test_plugin_github(self, mock_gh):
        def side_effect(args):
            endpoint = args[1] if len(args) > 1 else ""
            if endpoint == "repos/fdncred/nu_plugin_emoji":
                return {
                    "description": "Emoji plugin",
                    "license": {"spdx_id": "MIT"},
                    "topics": ["nushell", "plugin"],
                }
            if "releases" in endpoint:
                return [
                    {
                        "tag_name": "v0.23.0",
                        "assets": [
                            {"name": "nu_plugin_emoji-x86_64-pc-windows-msvc.zip", "browser_download_url": "https://x/win.zip", "size": 100},
                            {"name": "nu_plugin_emoji-x86_64-unknown-linux-gnu.tar.gz", "browser_download_url": "https://x/linux.tar.gz", "size": 200},
                        ],
                    }
                ]
            if "contents/Cargo.toml" in endpoint:
                import base64
                content = '[package]\nname = "nu_plugin_emoji"\n\n[dependencies]\nnu-plugin = { version = "0.114.0" }\n'
                return {"content": base64.b64encode(content.encode()).decode()}
            return None

        mock_gh.side_effect = side_effect
        report = discover.discover_github("fdncred/nu_plugin_emoji", ref="v0.23.0")
        self.assertEqual(report["facts"]["package_type"], "plugin")
        self.assertEqual(report["facts"]["owner"], "fdncred")
        self.assertEqual(report["facts"]["license"], "MIT")
        self.assertTrue(report["platform_hints"]["windows"])
        self.assertTrue(report["platform_hints"]["linux"])
        self.assertEqual(len(report["facts"]["releases"]), 1)
        self.assertEqual(len(report["facts"]["releases"][0]["assets"]), 2)

    @patch("discover.gh_json")
    def test_repo_not_found(self, mock_gh):
        mock_gh.return_value = None
        with self.assertRaises(SystemExit):
            discover.discover_github("nobody/nonexistent")


if __name__ == "__main__":
    unittest.main()
