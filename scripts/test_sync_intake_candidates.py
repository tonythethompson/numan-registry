#!/usr/bin/env python3
"""Unit checks for scripts/sync-intake-candidates.py (no network)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "sync-intake-candidates.py"


def load_sync():
    spec = importlib.util.spec_from_file_location("sync_intake_candidates", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class SyncIntakeCandidatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sync = load_sync()

    def test_artifact_provenance_classes(self):
        self.assertEqual(
            self.sync.artifact_provenance(
                "https://github.com/tonythethompson/numan-registry/releases/download/mirror-x/x.zip"
            ),
            "mirror",
        )
        self.assertEqual(
            self.sync.artifact_provenance(
                "https://github.com/tonythethompson/numan-plugins/releases/download/p-1.0.0/p.tar.gz"
            ),
            "ci-built",
        )
        self.assertEqual(
            self.sync.artifact_provenance(
                "https://github.com/acme/nu_plugin_x/releases/download/v1.0.0/x.tar.gz"
            ),
            "upstream",
        )
        self.assertEqual(self.sync.artifact_provenance(""), "other")

    def test_registry_packages_marks_ci_built(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "FMotalleb", "name": "nu_plugin_image"},
                    "versions": [
                        {
                            "version": "0.112.2",
                            "artifact": {
                                "kind": "binary",
                                "targets": {
                                    "x86_64-unknown-linux-gnu": {
                                        "url": (
                                            "https://github.com/tonythethompson/"
                                            "numan-plugins/releases/download/"
                                            "nu_plugin_image-0.112.2/"
                                            "nu_plugin_image-0.112.2-x86_64-unknown-linux-gnu.tar.gz"
                                        ),
                                        "sha256": "abc",
                                    }
                                },
                            },
                        }
                    ],
                }
            ]
        }
        live = self.sync.registry_packages(index)
        info = live["FMotalleb/nu_plugin_image"]
        self.assertTrue(info["ci_built"])
        self.assertFalse(info["upstream_asset"])
        self.assertFalse(info["mirror"])
        self.assertFalse(info["mixed"])

    def test_registry_packages_preserves_mirror_when_mixed(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_partial"},
                    "versions": [
                        {
                            "version": "1.0.0",
                            "artifact": {
                                "kind": "binary",
                                "targets": {
                                    "x86_64-pc-windows-msvc": {
                                        "url": (
                                            "https://github.com/tonythethompson/"
                                            "numan-registry/releases/download/"
                                            "mirror-partial/win.zip"
                                        ),
                                    },
                                    "x86_64-unknown-linux-gnu": {
                                        "url": (
                                            "https://github.com/acme/plugin/"
                                            "releases/download/v1.0.0/linux.zip"
                                        ),
                                    },
                                },
                            },
                        }
                    ],
                }
            ]
        }
        live = self.sync.registry_packages(index)
        info = live["acme/nu_plugin_partial"]
        self.assertTrue(info["mixed"])
        self.assertTrue(info["mirror"])
        self.assertFalse(info["ci_built"])
        self.assertFalse(info["upstream_asset"])

    def test_package_status_uses_ci_built_label(self):
        entry = {
            "id": "FMotalleb/nu_plugin_image",
            "version": "0.112.2",
            "note": "ci-built via numan-plugins; wave1; Nu 0.112",
        }
        live = {
            "FMotalleb/nu_plugin_image": {
                "version": "0.112.2",
                "mirror": False,
                "ci_built": True,
                "upstream_asset": False,
                "mixed": False,
            }
        }
        status = self.sync.package_status(entry, live, {}, {})
        self.assertTrue(status.startswith("live (ci-built asset)"))
        self.assertIn("ci-built via numan-plugins; wave1; Nu 0.112", status)
        self.assertNotIn("upstream asset", status)

    def test_package_status_prefers_mixed_over_mirror(self):
        entry = {"id": "acme/nu_plugin_partial", "version": "1.0.0"}
        live = {
            "acme/nu_plugin_partial": {
                "version": "1.0.0",
                "mirror": True,
                "ci_built": False,
                "upstream_asset": False,
                "mixed": True,
            }
        }
        status = self.sync.package_status(entry, live, {}, {})
        self.assertTrue(status.startswith("live (mixed provenance)"))
        self.assertNotIn("registry mirror", status)

    def test_live_status_none_when_not_in_index(self):
        entry = {"id": "acme/nu_plugin_x", "version": "1.0.0"}
        self.assertIsNone(self.sync._live_status(entry, {}))

    def test_live_status_all_provenance_flavors(self):
        live = {
            "acme/a": {"version": "1.0.0", "mirror": False, "ci_built": False, "upstream_asset": True, "mixed": False},
            "acme/b": {"version": "2.0.0", "mirror": True, "ci_built": False, "upstream_asset": False, "mixed": False},
            "acme/c": {"version": "3.0.0", "mirror": False, "ci_built": True, "upstream_asset": False, "mixed": False},
            "acme/d": {"version": "4.0.0", "mirror": True, "ci_built": False, "upstream_asset": False, "mixed": True},
            "acme/e": {"version": "5.0.0", "mirror": False, "ci_built": False, "upstream_asset": False, "mixed": False},
        }
        expected = {
            "acme/a": "live (upstream asset)",
            "acme/b": "live (registry mirror)",
            "acme/c": "live (ci-built asset)",
            "acme/d": "live (mixed provenance)",
            "acme/e": "live",
        }
        for pid, want in expected.items():
            self.assertEqual(
                self.sync._live_status({"id": pid, "version": "0.0.0"}, live),
                [want, "index@" + live[pid]["version"]],
            )

    def test_live_status_skips_index_note_when_versions_match(self):
        live = {
            "acme/x": {"version": "1.0.0", "mirror": False, "ci_built": False, "upstream_asset": True, "mixed": False}
        }
        self.assertEqual(
            self.sync._live_status({"id": "acme/x", "version": "1.0.0"}, live),
            ["live (upstream asset)"],
        )

    def test_pr_status_none_without_pr_number(self):
        self.assertIsNone(self.sync._pr_status({"id": "acme/x"}, {}))

    def test_pr_status_all_states(self):
        pr_map = {1: "merged", 2: "open", 3: "closed", 4: None}
        base = "https://github.com/tonythethompson/numan-registry/pull"
        self.assertEqual(
            self.sync._pr_status({"id": "acme/x", "pr": 1}, pr_map),
            [f"merged in [#1]({base}/1) — publish pending?"],
        )
        self.assertEqual(
            self.sync._pr_status({"id": "acme/x", "pr": 2}, pr_map),
            [f"PR [#2]({base}/2) open"],
        )
        self.assertEqual(
            self.sync._pr_status({"id": "acme/x", "pr": 3}, pr_map),
            ["PR #3 closed (not merged)"],
        )
        self.assertEqual(
            self.sync._pr_status({"id": "acme/x", "pr": 4}, pr_map),
            [f"pending [#4]({base}/4)"],
        )

    def test_candidate_status_spec_written_vs_plain(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / "specs" / "acme-x-1.0.0.json"
            spec_file.parent.mkdir(parents=True)
            spec_file.write_text("{}", encoding="utf-8")
            with patch.object(self.sync, "REPO_ROOT", Path(tmp)):
                self.assertEqual(
                    self.sync._candidate_status({"id": "acme/x", "spec": "specs/acme-x-1.0.0.json"}),
                    ["spec written, not in index"],
                )
                self.assertEqual(self.sync._candidate_status({"id": "acme/x"}), ["candidate"])

    def test_package_status_appends_outreach_and_note_tail(self):
        entry = {"id": "acme/pr1", "pr": 1, "outreach": {"x": 1}, "note": "wave2"}
        status = self.sync.package_status(
            entry, {}, {1: "open"}, {"acme/pr1": {"summary": "responded — see acme/foo#3"}}
        )
        self.assertIn("PR [#1]", status)
        self.assertIn("outreach: responded — see acme/foo#3", status)
        self.assertTrue(status.endswith("— wave2"))

    def test_pr_status_not_used_when_entry_is_live(self):
        entry = {"id": "acme/x", "version": "1.0.0", "pr": 99}
        live = {
            "acme/x": {"version": "1.0.0", "mirror": False, "ci_built": False, "upstream_asset": True, "mixed": False}
        }
        status = self.sync.package_status(entry, live, {99: "open"}, {})
        self.assertTrue(status.startswith("live (upstream asset)"))
        self.assertNotIn("PR [#99]", status)

    def test_registry_summary_sorts_and_marks_mixed_versions(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "vyadh", "name": "nutest"},
                    "versions": [
                        {"version": "1.1.0", "artifact": {"url": "https://github.com/tonythethompson/numan-registry/releases/download/mirror-x/a.zip"}},
                        {"version": "1.2.0", "artifact": {"url": "https://github.com/acme/nutest/releases/download/v1.2.0/a.zip"}},
                    ],
                },
                {
                    "id": {"owner": "abusch", "name": "nu_plugin_semver"},
                    "versions": [{"version": "0.11.17", "artifact": {"url": "https://github.com/acme/semver/releases/download/v/a.zip"}}],
                },
            ]
        }
        rendered = self.sync.render_intake_doc({}, {}, index, {})
        self.assertIn("`abusch/nu_plugin_semver@0.11.17` (upstream)", rendered)
        self.assertIn("`vyadh/nutest` (1.1.0, 1.2.0; mixed)", rendered)

    def test_registry_summary_marks_mixed_binary_targets(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_mixed"},
                    "versions": [
                        {
                            "version": "1.0.0",
                            "artifact": {
                                "kind": "binary",
                                "targets": {
                                    "x86_64-pc-windows-msvc": {
                                        "url": "https://github.com/tonythethompson/numan-plugins/releases/download/x/win.zip"
                                    },
                                    "x86_64-unknown-linux-gnu": {
                                        "url": "https://github.com/acme/plugin/releases/download/v1.0.0/linux.zip"
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "id": {"owner": "acme", "name": "nu_plugin_empty_binary"},
                    "versions": [
                        {
                            "version": "0.1.0",
                            "artifact": {"kind": "binary", "targets": {}},
                        }
                    ],
                },
            ]
        }
        rendered = self.sync.render_intake_doc({}, {}, index, {})
        self.assertIn("`acme/nu_plugin_mixed@1.0.0` (mixed)", rendered)
        self.assertIn("`acme/nu_plugin_empty_binary@0.1.0` (other)", rendered)


if __name__ == "__main__":
    unittest.main()
