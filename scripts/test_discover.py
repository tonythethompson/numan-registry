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


class TestLocalProbeHelpers(unittest.TestCase):
    """Unit tests for the helpers extracted from discover_local()."""

    def test_probe_cargo_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "Cargo.toml").write_text('[package]\nname = "nu_plugin_x"\n\n[dependencies]\nnu-plugin = "0.114.0"\n')
            present, info = discover._probe_cargo(p)
            self.assertTrue(present)
            self.assertTrue(info["is_plugin"])
            self.assertEqual(info["crate_name"], "nu_plugin_x")

    def test_probe_cargo_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            present, info = discover._probe_cargo(Path(tmp))
            self.assertFalse(present)
            self.assertEqual(info, {})

    def test_probe_nupm(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "nupm.nuon").write_text("")
            self.assertTrue(discover._probe_nupm(p))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(discover._probe_nupm(Path(tmp)))

    def test_probe_mod_nu_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "mod.nu").write_text("")
            self.assertTrue(discover._probe_mod_nu(p))

    def test_probe_mod_nu_one_level_deep(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            sub = p / "pkgs"
            sub.mkdir()
            (sub / "mod.nu").write_text("")
            self.assertTrue(discover._probe_mod_nu(p))

    def test_probe_mod_nu_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(discover._probe_mod_nu(Path(tmp)))

    def test_probe_mod_nu_not_two_levels_deep(self):
        # Direct children only: a nested pkgs/name/mod.nu must not match.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            sub = p / "pkgs" / "name"
            sub.mkdir(parents=True)
            (sub / "mod.nu").write_text("")
            self.assertFalse(discover._probe_mod_nu(p))

    def test_detect_license_mit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "LICENSE").write_text("MIT License\nCopyright (c) 2026\n")
            self.assertEqual(discover._detect_license(p), "MIT")

    def test_detect_license_apache(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "LICENSE-MIT").write_text("Apache License 2.0\n")
            self.assertEqual(discover._detect_license(p), "Apache-2.0")

    def test_detect_license_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "LICENSE.md").write_text("All rights reserved.\n")
            self.assertEqual(discover._detect_license(p), "UNKNOWN")

    def test_detect_license_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(discover._detect_license(Path(tmp)))

    def test_classify_local_plugin(self):
        self.assertEqual(
            discover._classify_local("x", {"is_plugin": True}, False, False),
            ("plugin", "high", "Cargo.toml depends on nu-plugin"),
        )

    def test_classify_local_mod_nu(self):
        self.assertEqual(
            discover._classify_local("x", {}, True, False),
            ("module", "high", "mod.nu found"),
        )

    def test_classify_local_nupm(self):
        self.assertEqual(
            discover._classify_local("x", {}, False, True),
            ("module", "medium", "nupm.nuon present (assumed module)"),
        )

    def test_classify_local_completion(self):
        self.assertEqual(
            discover._classify_local("bash-completions", {}, False, False),
            ("completion", "medium", "name suggests completions"),
        )

    def test_classify_local_unknown(self):
        self.assertEqual(
            discover._classify_local("random", {}, False, False),
            (None, "low", "no strong signal"),
        )

    def test_local_report_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "LICENSE").write_text("MIT License\n")
            (p / "mod.nu").write_text("")
            report = discover.discover_local(p)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["source"], {"kind": "local", "url": str(p.resolve()), "ref": None})
            self.assertEqual(report["facts"]["name"], Path(tmp).name)
            self.assertIsNone(report["facts"]["owner"])
            self.assertEqual(report["facts"]["package_type"], "module")
            self.assertEqual(report["facts"]["license"], "MIT")
            self.assertEqual(report["facts"]["releases"], [])
            self.assertEqual(
                report["needs_decision"],
                ["registry_owner", "nu_version constraint not declared", "verified_with"],
            )
            self.assertFalse(any(report["platform_hints"].values()))


class TestFetchHelpers(unittest.TestCase):
    """Unit tests for the helpers extracted from discover_github()."""

    def test_fetch_repo_info_returns_metadata(self):
        with patch("discover.gh_json", return_value={"description": "d", "topics": []}):
            self.assertEqual(discover._fetch_repo_info("o", "n"), {"description": "d", "topics": []})

    def test_fetch_repo_info_exits_when_missing(self):
        with (
            patch("discover.gh_json", return_value=None),
            self.assertRaises(SystemExit),
        ):
            discover._fetch_repo_info("o", "n")

    def test_release_assets_maps_supported_suffixes(self):
        rel = {"assets": [
            {"name": "pkg-win.zip", "browser_download_url": "https://x/win.zip", "size": 10},
            {"name": "pkg-linux.tar.gz", "browser_download_url": "https://x/linux.tar.gz", "size": 20},
            {"name": "README.md", "browser_download_url": "https://x/readme", "size": 5},
        ]}
        assets = discover._release_assets(rel)
        self.assertEqual(len(assets), 2)
        self.assertEqual(assets[0]["suffix"], ".zip")
        self.assertEqual(assets[1]["suffix"], ".tar.gz")

    def test_fetch_releases_with_ref_filters_tag(self):
        releases = [
            {"tag_name": "v0.23.0", "assets": [{"name": "a.zip", "browser_download_url": "u", "size": 1}]},
            {"tag_name": "v0.22.0", "assets": [{"name": "b.zip", "browser_download_url": "u", "size": 1}]},
        ]
        with patch("discover.gh_json", return_value=releases):
            got = discover._fetch_releases("o", "n", ref="v0.23.0")
        self.assertEqual([r["tag"] for r in got], ["v0.23.0"])

    def test_fetch_releases_without_ref_keeps_latest(self):
        releases = [
            {"tag_name": "v2", "assets": [{"name": "a.zip", "browser_download_url": "u", "size": 1}]},
            {"tag_name": "v1", "assets": []},
        ]
        with patch("discover.gh_json", return_value=releases):
            got = discover._fetch_releases("o", "n", ref=None)
        # v1 has no supported assets but is kept when no ref is given.
        self.assertEqual([r["tag"] for r in got], ["v2", "v1"])

    def test_fetch_cargo_decodes_content(self):
        import base64

        content = '[package]\nname = "nu_plugin_x"\n'
        with patch("discover.gh_json", return_value={"content": base64.b64encode(content.encode()).decode()}):
            self.assertEqual(discover._fetch_cargo("o", "n"), content)

    def test_fetch_cargo_returns_none_when_absent(self):
        with patch("discover.gh_json", return_value=None):
            self.assertIsNone(discover._fetch_cargo("o", "n"))

    def test_classify_github_plugin_by_cargo(self):
        self.assertEqual(
            discover._classify_github("x", {"is_plugin": True}, []),
            ("plugin", "high", "Cargo.toml depends on nu-plugin"),
        )

    def test_classify_github_plugin_by_name(self):
        self.assertEqual(
            discover._classify_github("nu_plugin_emoji", {}, []),
            ("plugin", "medium", "repository name matches plugin convention"),
        )

    def test_classify_github_module_by_topics(self):
        self.assertEqual(
            discover._classify_github("x", {}, ["nushell-module"]),
            ("module", "medium", "GitHub topics indicate module"),
        )

    def test_classify_github_completion(self):
        self.assertEqual(
            discover._classify_github("bash-completions", {}, ["completions"]),
            ("completion", "medium", "name/topics indicate completions"),
        )

    def test_classify_github_unknown(self):
        self.assertEqual(
            discover._classify_github("random", {}, []),
            (None, "low", "no strong signal; needs manual classification"),
        )

    def test_platform_hints_detects_platforms(self):
        releases = [{"assets": [
            {"name": "pkg-x86_64-pc-windows-msvc.zip"},
            {"name": "pkg-aarch64-apple-darwin.tar.gz"},
            {"name": "pkg-x86_64-apple-darwin.tar.gz"},
            {"name": "pkg-x86_64-unknown-linux-gnu.tar.gz"},
        ]}]
        hints = discover._platform_hints(releases)
        self.assertTrue(hints["windows"])
        self.assertTrue(hints["linux"])
        self.assertTrue(hints["macos_arm"])
        self.assertTrue(hints["macos_x64"])

    def test_platform_hints_empty_releases(self):
        self.assertEqual(
            discover._platform_hints([]),
            {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False},
        )

    def test_needs_decision_for_plugin_without_targets(self):
        needs = discover._needs_decision(None, "plugin", {"windows": False, "linux": False, "macos_arm": False, "macos_x64": False})
        self.assertIn("nu_version constraint not declared", needs)
        self.assertIn("verified_with", needs)
        self.assertIn("exclude_targets", needs)

    def test_needs_decision_for_plugin_with_targets(self):
        needs = discover._needs_decision(">=0.114.0 <0.115.0", "plugin", {"windows": True, "linux": False, "macos_arm": False, "macos_x64": False})
        self.assertNotIn("nu_version constraint not declared", needs)
        self.assertIn("verified_with", needs)
        self.assertNotIn("exclude_targets", needs)


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
