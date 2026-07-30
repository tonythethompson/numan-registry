#!/usr/bin/env python3
"""Unit checks for scripts/sync-intake-candidates.py (no network)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

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

    def test_package_status_uses_ci_built_label(self):
        entry = {
            "id": "FMotalleb/nu_plugin_image",
            "version": "0.112.2",
            "note": "ci-built via numan-plugins Wave 1",
        }
        live = {
            "FMotalleb/nu_plugin_image": {
                "version": "0.112.2",
                "mirror": False,
                "ci_built": True,
                "upstream_asset": False,
            }
        }
        status = self.sync.package_status(entry, live, {}, {})
        self.assertTrue(status.startswith("live (ci-built asset)"))
        self.assertIn("ci-built via numan-plugins Wave 1", status)
        self.assertNotIn("upstream asset", status)


if __name__ == "__main__":
    unittest.main()
