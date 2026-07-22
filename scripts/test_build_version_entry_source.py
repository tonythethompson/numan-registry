#!/usr/bin/env python3
"""Unit checks for source provenance passthrough in add-package.py.

No network: tests copy_source_field only.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "add-package.py"


def load_add_package():
    spec = importlib.util.spec_from_file_location("add_package", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CopySourceFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ap = load_add_package()

    def test_copies_source_when_present(self):
        version_entry = {"version": "1.0.0", "nu_version": ">=0.113.0 <0.114.0"}
        spec = {
            "source": {
                "git": "https://github.com/example/nu_plugin_x",
                "rev": "v1.0.0",
                "cargo_name": "nu_plugin_x",
            }
        }
        self.ap.copy_source_field(spec, version_entry)
        self.assertEqual(
            version_entry["source"],
            {
                "git": "https://github.com/example/nu_plugin_x",
                "rev": "v1.0.0",
                "cargo_name": "nu_plugin_x",
            },
        )

    def test_copies_optional_cargo_lock_sha256(self):
        version_entry = {}
        spec = {
            "source": {
                "git": "https://github.com/example/nu_plugin_x",
                "rev": "v1.0.0",
                "cargo_name": "nu_plugin_x",
                "cargo_lock_sha256": "a" * 64,
            }
        }
        self.ap.copy_source_field(spec, version_entry)
        self.assertEqual(version_entry["source"]["cargo_lock_sha256"], "a" * 64)

    def test_noop_when_source_absent(self):
        version_entry = {"version": "1.0.0"}
        self.ap.copy_source_field({}, version_entry)
        self.assertNotIn("source", version_entry)

    def test_rejects_partial_source(self):
        version_entry = {}
        spec = {"source": {"git": "https://github.com/example/x", "rev": "v1"}}
        with self.assertRaises(SystemExit) as ctx:
            self.ap.copy_source_field(spec, version_entry)
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CopySourceFieldTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
