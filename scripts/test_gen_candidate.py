#!/usr/bin/env python3.12
"""Tests for scripts/gen_candidate.py (Stage 4: candidate generation)."""

from __future__ import annotations

import unittest

import gen_candidate


def _plugin_report() -> dict:
    """Fixture: discovery report for a binary plugin with full target matrix."""
    return {
        "schema_version": 1,
        "source": {"kind": "github", "url": "https://github.com/fdncred/nu_plugin_emoji", "ref": "v0.23.0"},
        "facts": {
            "name": "nu_plugin_emoji",
            "owner": "fdncred",
            "package_type": "plugin",
            "license": "MIT",
            "description": "Search and insert emoji characters.",
            "has_cargo_toml": True,
            "has_nupm_metadata": False,
            "nu_constraint_hint": ">=0.114.0 <0.115.0",
            "releases": [
                {
                    "tag": "v0.23.0",
                    "assets": [
                        {"name": "nu_plugin_emoji-x86_64-pc-windows-msvc.zip", "url": "https://x/win.zip", "size": 100, "suffix": ".zip"},
                        {"name": "nu_plugin_emoji-x86_64-unknown-linux-gnu.tar.gz", "url": "https://x/linux.tar.gz", "size": 200, "suffix": ".tar.gz"},
                        {"name": "nu_plugin_emoji-aarch64-apple-darwin.tar.gz", "url": "https://x/mac-arm.tar.gz", "size": 150, "suffix": ".tar.gz"},
                    ],
                }
            ],
        },
        "guesses": {"registry_type": "plugin", "confidence": "high", "reason": "Cargo.toml depends on nu-plugin"},
        "needs_decision": ["verified_with"],
        "platform_hints": {"windows": True, "linux": True, "macos_arm": True, "macos_x64": False},
    }


def _module_report() -> dict:
    """Fixture: discovery report for a module with a single archive."""
    return {
        "schema_version": 1,
        "source": {"kind": "github", "url": "https://github.com/someone/cool-module", "ref": "v1.0.0"},
        "facts": {
            "name": "cool-module",
            "owner": "someone",
            "package_type": "module",
            "license": "MIT",
            "description": "A cool module.",
            "has_cargo_toml": False,
            "has_nupm_metadata": True,
            "nu_constraint_hint": None,
            "releases": [
                {
                    "tag": "v1.0.0",
                    "assets": [
                        {"name": "cool-module-1.0.0.zip", "url": "https://x/mod.zip", "size": 50, "suffix": ".zip"},
                    ],
                }
            ],
        },
        "guesses": {"registry_type": "module", "confidence": "high", "reason": "mod.nu found"},
        "needs_decision": ["verified_with"],
        "platform_hints": {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False},
    }


class TestMatchTarget(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(gen_candidate._match_target("nu_plugin_emoji-x86_64-pc-windows-msvc.zip"), "x86_64-pc-windows-msvc")

    def test_linux(self):
        self.assertEqual(gen_candidate._match_target("foo-x86_64-unknown-linux-gnu.tar.gz"), "x86_64-unknown-linux-gnu")

    def test_macos_arm(self):
        self.assertEqual(gen_candidate._match_target("foo-aarch64-apple-darwin.tar.gz"), "aarch64-apple-darwin")

    def test_unknown(self):
        self.assertIsNone(gen_candidate._match_target("foo-source.tar.gz"))


class TestExecutablePath(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(gen_candidate._executable_path("nu_plugin_emoji", "x86_64-pc-windows-msvc"), "nu_plugin_emoji.exe")

    def test_linux(self):
        self.assertEqual(gen_candidate._executable_path("nu_plugin_emoji", "x86_64-unknown-linux-gnu"), "nu_plugin_emoji")


class TestGenerateSpecPlugin(unittest.TestCase):
    def test_basic_plugin(self):
        result = gen_candidate.generate_spec(_plugin_report())
        spec = result["spec"]
        self.assertEqual(spec["owner"], "fdncred")
        self.assertEqual(spec["name"], "nu_plugin_emoji")
        self.assertEqual(spec["type"], "plugin")
        self.assertEqual(spec["version"], "0.23.0")
        self.assertEqual(spec["nu_version"], ">=0.114.0 <0.115.0")
        self.assertEqual(spec["artifact"]["kind"], "binary")
        targets = spec["artifact"]["targets"]
        self.assertIn("x86_64-pc-windows-msvc", targets)
        self.assertIn("x86_64-unknown-linux-gnu", targets)
        self.assertIn("aarch64-apple-darwin", targets)
        self.assertEqual(targets["x86_64-pc-windows-msvc"]["executable_path"], "nu_plugin_emoji.exe")

    def test_provenance(self):
        result = gen_candidate.generate_spec(_plugin_report())
        meta = result["_meta"]
        self.assertEqual(meta["generated_from"], "discovery-v1")
        self.assertIn("owner", meta["field_provenance"])
        self.assertIn("version", meta["field_provenance"])

    def test_owner_override(self):
        result = gen_candidate.generate_spec(_plugin_report(), owner_override="custom-owner")
        self.assertEqual(result["spec"]["owner"], "custom-owner")
        self.assertIn("CLI override", result["_meta"]["field_provenance"]["owner"])

    def test_nu_version_override(self):
        result = gen_candidate.generate_spec(_plugin_report(), nu_version_override=">=0.113.0 <0.114.0")
        self.assertEqual(result["spec"]["nu_version"], ">=0.113.0 <0.114.0")


class TestGenerateSpecModule(unittest.TestCase):
    def test_basic_module(self):
        result = gen_candidate.generate_spec(_module_report())
        spec = result["spec"]
        self.assertEqual(spec["type"], "module")
        self.assertEqual(spec["artifact"]["kind"], "archive")
        self.assertEqual(spec["artifact"]["url"], "https://x/mod.zip")
        self.assertEqual(spec["artifact"]["entry"], "mod.nu")
        self.assertEqual(spec["activation"]["kind"], "nu-module")
        self.assertEqual(spec["activation"]["import"], "all")

    def test_nu_version_default(self):
        result = gen_candidate.generate_spec(_module_report())
        self.assertEqual(result["spec"]["nu_version"], "*")
        self.assertTrue(any("defaulted to *" in w for w in result["_meta"]["warnings"]))


class TestGenerateSpecIncomplete(unittest.TestCase):
    def test_no_releases(self):
        report = _plugin_report()
        report["facts"]["releases"] = []
        result = gen_candidate.generate_spec(report)
        self.assertTrue(any("no releases" in u for u in result["_meta"]["unresolved"]))
        self.assertEqual(result["spec"]["version"], "0.0.0")

    def test_no_owner(self):
        report = _plugin_report()
        report["facts"]["owner"] = None
        result = gen_candidate.generate_spec(report)
        self.assertEqual(result["spec"]["owner"], "TODO")
        self.assertTrue(any("owner" in u for u in result["_meta"]["unresolved"]))


if __name__ == "__main__":
    unittest.main()
