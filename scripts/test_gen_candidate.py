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


class TestPickBestRelease(unittest.TestCase):
    def test_prefers_release_with_assets(self):
        releases = [{"tag": "v1", "assets": []}, {"tag": "v2", "assets": [{"name": "a"}]}]
        self.assertEqual(gen_candidate._pick_best_release(releases)["tag"], "v2")

    def test_falls_back_to_first_release(self):
        releases = [{"tag": "v1", "assets": []}]
        self.assertEqual(gen_candidate._pick_best_release(releases)["tag"], "v1")

    def test_empty(self):
        self.assertIsNone(gen_candidate._pick_best_release([]))


class TestReleaseVersion(unittest.TestCase):
    def test_strips_v(self):
        prov, unresolved = {}, []
        self.assertEqual(gen_candidate._release_version({"tag": "v1.2.3"}, prov, unresolved), "1.2.3")
        self.assertEqual(prov["version"], "release tag v1.2.3")
        self.assertEqual(unresolved, [])

    def test_no_release(self):
        prov, unresolved = {}, []
        self.assertEqual(gen_candidate._release_version(None, prov, unresolved), "")
        self.assertTrue(any("no releases" in u for u in unresolved))


class TestProvenanceHelpers(unittest.TestCase):
    def test_owner_override(self):
        prov, unresolved = {}, []
        gen_candidate._owner_provenance({"owner": "real"}, "cli-owner", prov, unresolved)
        self.assertIn("CLI override", prov["owner"])
        self.assertEqual(unresolved, [])

    def test_owner_from_facts(self):
        prov, unresolved = {}, []
        gen_candidate._owner_provenance({"owner": "real"}, None, prov, unresolved)
        self.assertEqual(prov["owner"], "github repo owner")
        self.assertEqual(unresolved, [])

    def test_owner_unresolved(self):
        prov, unresolved = {}, []
        gen_candidate._owner_provenance({}, None, prov, unresolved)
        self.assertTrue(any("owner" in u for u in unresolved))

    def test_nu_version_override(self):
        prov, warnings = {}, []
        gen_candidate._nu_version_provenance({"nu_constraint_hint": ">=0.1"}, ">=0.2", prov, warnings)
        self.assertIn("CLI override", prov["nu_version"])
        self.assertEqual(warnings, [])

    def test_nu_version_from_facts(self):
        prov, warnings = {}, []
        gen_candidate._nu_version_provenance({"nu_constraint_hint": ">=0.1"}, None, prov, warnings)
        self.assertEqual(prov["nu_version"], "Cargo.toml nu-plugin dependency version")
        self.assertEqual(warnings, [])

    def test_nu_version_defaulted(self):
        prov, warnings = {}, []
        gen_candidate._nu_version_provenance({}, None, prov, warnings)
        self.assertIn("defaulted", prov["nu_version"])
        self.assertTrue(any("defaulted" in w for w in warnings))


class TestArtifactHelpers(unittest.TestCase):
    def test_binary_maps_targets(self):
        release = {"tag": "v1", "assets": [{"name": "nu_plugin_emoji-x86_64-unknown-linux-gnu.tar.gz", "url": "u"}]}
        art = gen_candidate._binary_artifact("nu_plugin_emoji", release, [], [])
        self.assertEqual(art["kind"], "binary")
        self.assertIn("x86_64-unknown-linux-gnu", art["targets"])
        self.assertEqual(art["targets"]["x86_64-unknown-linux-gnu"]["executable_path"], "nu_plugin_emoji")

    def test_binary_skips_unmapped(self):
        release = {"tag": "v1", "assets": [{"name": "foo-source.tar.gz", "url": "u"}]}
        warnings, unresolved = [], []
        art = gen_candidate._binary_artifact("p", release, warnings, unresolved)
        self.assertEqual(art["targets"], {})
        self.assertTrue(any("unmapped assets" in w for w in warnings))
        self.assertTrue(any("no release assets matched" in u for u in unresolved))

    def test_archive_takes_first_asset(self):
        release = {"tag": "v1", "assets": [{"name": "a.zip", "url": "https://x/a.zip"}]}
        prov, unresolved = {}, []
        art = gen_candidate._archive_artifact(release, prov, unresolved)
        self.assertEqual(art["kind"], "archive")
        self.assertEqual(art["url"], "https://x/a.zip")
        self.assertEqual(art["entry"], "mod.nu")
        self.assertIn("artifact_url", prov)
        self.assertEqual(unresolved, [])

    def test_archive_no_asset(self):
        prov, unresolved = {}, []
        art = gen_candidate._archive_artifact(None, prov, unresolved)
        self.assertEqual(art["url"], "")
        self.assertTrue(any("no archive URL" in u for u in unresolved))


class TestDefaultSpecBase(unittest.TestCase):
    def test_fields(self):
        base = gen_candidate._default_spec_base("o", "n", "d", "https://r", "plugin", "1.0.0", ">=0.114")
        self.assertEqual(base["owner"], "o")
        self.assertEqual(base["name"], "n")
        self.assertEqual(base["version"], "1.0.0")
        self.assertEqual(base["tags"], ["plugin", "ci-built"])

    def test_owner_todo_and_version_default(self):
        base = gen_candidate._default_spec_base(None, "n", "d", "", "plugin", "", "*")
        self.assertEqual(base["owner"], "TODO")
        self.assertEqual(base["version"], "0.0.0")


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

    def test_unsupported_package_type(self):
        report = _plugin_report()
        report["facts"]["package_type"] = "binary"
        report["guesses"]["registry_type"] = None
        result = gen_candidate.generate_spec(report)
        self.assertTrue(any("unsupported package_type" in u for u in result["_meta"]["unresolved"]))

    def test_repo_url_fallback(self):
        report = _plugin_report()
        report["source"]["url"] = ""
        result = gen_candidate.generate_spec(report)
        self.assertEqual(result["spec"]["repo"], "https://github.com/fdncred/nu_plugin_emoji")


if __name__ == "__main__":
    unittest.main()
