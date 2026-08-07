#!/usr/bin/env python3
"""Unit checks for scripts/lint-manifest-index.py (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "lint-manifest-index.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))


def load_lint():
    spec = importlib.util.spec_from_file_location("lint_manifest_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class LintManifestIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lint = load_lint()

    def test_load_json_url_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            self.lint.load_json_url("file:///etc/passwd")

    def test_load_json_url_accepts_https(self):
        # No network in unit tests: mock urlopen to prove the guard passes
        # http(s) URLs through to the opener.
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"active": []}'

        with mock.patch.object(
            self.lint.urllib.request, "urlopen", return_value=_Resp()
        ) as urlopen:
            self.assertEqual(self.lint.load_json_url("https://example.invalid/manifest.json"), {"active": []})
        urlopen.assert_called_once()

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
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])
        self.assertEqual(unchecked, [])
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
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(missing, [])
        self.assertEqual(unchecked, [])
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
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(checked, [])
        self.assertEqual(unchecked, [])
        self.assertEqual(len(missing), 1)
        self.assertIn("acme/nu_plugin_new@0.1.0", missing[0])

    def test_missing_nu_version_is_unchecked_not_error(self):
        manifest = {
            "active": [
                {
                    "owner": "acme",
                    "name": "nu_plugin_x",
                    "version": "1.0.0",
                    "nu_version": None,
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
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])
        self.assertEqual(checked, [])
        self.assertEqual(len(unchecked), 1)
        self.assertIn("unknown", unchecked[0])

    def test_null_active_element_raises(self):
        with self.assertRaises(TypeError):
            self.lint.compare({"active": [None]}, {"packages": []})

    def test_null_package_element_raises(self):
        with self.assertRaises(TypeError):
            self.lint.compare({"active": []}, {"packages": [None]})

    def test_main_null_list_elements_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            man_path = root / "manifest.json"
            idx_path = root / "index.json"
            man_path.write_text(json.dumps({"active": [None]}), encoding="utf-8")
            idx_path.write_text(json.dumps({"packages": []}), encoding="utf-8")
            code = self.lint.main(
                ["--index", str(idx_path), "--manifest", str(man_path)]
            )
            self.assertEqual(code, 2)

            man_path.write_text(json.dumps({"active": []}), encoding="utf-8")
            idx_path.write_text(json.dumps({"packages": [None]}), encoding="utf-8")
            code = self.lint.main(
                ["--index", str(idx_path), "--manifest", str(man_path)]
            )
            self.assertEqual(code, 2)

    def test_index_missing_nu_version_is_unchecked_not_error(self):
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
                        {"version": "1.0.0"}  # nu_version key absent
                    ],
                }
            ]
        }
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])
        self.assertEqual(checked, [])
        self.assertEqual(len(unchecked), 1)
        self.assertIn("acme/nu_plugin_x@1.0.0", unchecked[0])
        self.assertIn("index nu_version unknown", unchecked[0])

    def test_index_non_string_nu_version_is_unchecked_not_error(self):
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
                        {"version": "1.0.0", "nu_version": None}  # non-string nu_version
                    ],
                }
            ]
        }
        errors, missing, checked, unchecked = self.lint.compare(manifest, index)
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])
        self.assertEqual(checked, [])
        self.assertEqual(len(unchecked), 1)
        self.assertIn("acme/nu_plugin_x@1.0.0", unchecked[0])
        self.assertIn("index nu_version unknown", unchecked[0])

    def test_index_duplicate_version_raises(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.114.0 <0.115.0"},
                        {"version": "1.0.0", "nu_version": ">=0.113.0 <0.114.0"},
                    ],
                }
            ]
        }
        with self.assertRaises(TypeError) as ctx:
            self.lint.index_version_map(index)
        self.assertIn("Duplicate", str(ctx.exception))
        self.assertIn("acme/nu_plugin_x@1.0.0", str(ctx.exception))

    def test_index_duplicate_across_packages_raises(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.114.0 <0.115.0"}
                    ],
                },
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.113.0 <0.114.0"}
                    ],
                },
            ]
        }
        with self.assertRaises(TypeError) as ctx:
            self.lint.index_version_map(index)
        self.assertIn("Duplicate", str(ctx.exception))
        self.assertIn("acme/nu_plugin_x@1.0.0", str(ctx.exception))

    def test_main_index_duplicate_exit_2(self):
        manifest = {"active": []}
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "versions": [
                        {"version": "1.0.0", "nu_version": ">=0.114.0 <0.115.0"},
                        {"version": "1.0.0", "nu_version": ">=0.113.0 <0.114.0"},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            man_path = root / "manifest.json"
            idx_path = root / "index.json"
            man_path.write_text(json.dumps(manifest), encoding="utf-8")
            idx_path.write_text(json.dumps(index), encoding="utf-8")
            code = self.lint.main(
                ["--index", str(idx_path), "--manifest", str(man_path)]
            )
            self.assertEqual(code, 2)

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

            index["packages"][0]["versions"][0]["nu_version"] = ">=0.113.0 <0.114.0"
            idx_path.write_text(json.dumps(index), encoding="utf-8")
            code = self.lint.main(["--index", str(idx_path), "--manifest", str(man_path)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
