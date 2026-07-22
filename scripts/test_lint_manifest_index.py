#!/usr/bin/env python3
"""Unit checks for scripts/lint-manifest-index.py (no network)."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "lint-manifest-index.py"


def load_lint():
    spec = importlib.util.spec_from_file_location("lint_manifest_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class LintManifestIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lint = load_lint()

    def test_agreeing_constraints_pass(self):
        manifest = {
            "active": [
                {
                    "owner": "acme",
                    "name": "nu_plugin_x",
                    "version": "1.0.0",
                    "nu_version": ">=0.114.0 <0.115.0",
                }
            ]
        }
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.114.0 <0.115.0"}
                    ],
                }
            ]
        }
        errors, missing, checked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])
        self.assertEqual(checked, ["acme/nu_plugin_x@1.0.0"])

    def test_mismatch_is_error(self):
        manifest = {
            "active": [
                {
                    "owner": "acme",
                    "name": "nu_plugin_x",
                    "version": "1.0.0",
                    "nu_version": ">=0.114.0 <0.115.0",
                }
            ]
        }
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.113.0 <0.114.0"}
                    ],
                }
            ]
        }
        errors, missing, checked = self.lint.compare(manifest, index)
        self.assertEqual(missing, [])
        self.assertEqual(checked, ["acme/nu_plugin_x@1.0.0"])
        self.assertEqual(len(errors), 1)
        self.assertIn("!=", errors[0])

    def test_missing_from_index_is_skip_not_error(self):
        manifest = {
            "active": [
                {
                    "owner": "acme",
                    "name": "nu_plugin_new",
                    "version": "0.1.0",
                    "nu_version": ">=0.114.0 <0.115.0",
                }
            ]
        }
        index = {"packages": []}
        errors, missing, checked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(checked, [])
        self.assertEqual(len(missing), 1)
        self.assertIn("acme/nu_plugin_new@0.1.0", missing[0])

    def test_main_with_temp_files(self):
        manifest = {
            "active": [
                {
                    "owner": "acme",
                    "name": "nu_plugin_x",
                    "version": "1.0.0",
                    "nu_version": ">=0.114.0 <0.115.0",
                }
            ]
        }
        index = {
            "schema_version": 1,
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.114.0 <0.115.0"}
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            man_path = root / "manifest.json"
            idx_path = root / "index.json"
            man_path.write_text(json.dumps(manifest), encoding="utf-8")
            idx_path.write_text(json.dumps(index), encoding="utf-8")
            code = self.lint.main(["--index", str(idx_path), "--manifest", str(man_path)])
            self.assertEqual(code, 0)

            # mismatch exits 1
            index["packages"][0]["versions"][0]["nu_version"] = ">=0.113.0 <0.114.0"
            idx_path.write_text(json.dumps(index), encoding="utf-8")
            code = self.lint.main(["--index", str(idx_path), "--manifest", str(man_path)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
