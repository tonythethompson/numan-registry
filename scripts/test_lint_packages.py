#!/usr/bin/env python3.12
"""Unit checks for scripts/lint_packages.py (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "lint_packages.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))


def load_lint():
    spec = importlib.util.spec_from_file_location("lint_packages", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_package(**overrides):
    pkg = {
        "id": {"owner": "acme", "name": "nu_plugin_demo"},
        "description": "demo",
        "repo": "https://github.com/acme/nu_plugin_demo",
        "type": "plugin",
        "tags": ["plugin"],
        "versions": [
            {
                "version": "1.0.0",
                "nu_version": ">=0.113.0 <0.114.0",
                "verified_with": ["0.113.1"],
                "artifact": {
                    "kind": "binary",
                    "targets": {
                        "x86_64-unknown-linux-gnu": {
                            "url": "https://example.com/demo.tar.gz",
                            "sha256": "a" * 64,
                            "executable_path": "nu_plugin_demo",
                        }
                    },
                },
                "source": {
                    "git": "https://github.com/acme/nu_plugin_demo",
                    "rev": "v1.0.0",
                    "cargo_name": "nu_plugin_demo",
                },
            }
        ],
    }
    pkg.update(overrides)
    return pkg


class LintPackagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lint = load_lint()

    def test_clean_index_passes(self):
        errors = self.lint.lint_index({"packages": [base_package()]})
        self.assertEqual(errors, [])

    def test_missing_metadata_is_error(self):
        pkg = base_package(description="")
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("missing metadata description" in e for e in errors))

    def test_unknown_triple_is_error(self):
        pkg = base_package()
        pkg["versions"][0]["artifact"]["targets"] = {
            "powerpc-unknown-linux-gnu": {
                "url": "https://example.com/demo.tar.gz",
                "sha256": "b" * 64,
                "executable_path": "nu_plugin_demo",
            }
        }
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("unknown target triple" in e for e in errors))

    def test_unsupported_archive_suffix_is_error(self):
        pkg = base_package()
        pkg["versions"][0]["artifact"]["targets"]["x86_64-unknown-linux-gnu"][
            "url"
        ] = "https://example.com/demo.rar"
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("unsupported archive suffix" in e for e in errors))

    def test_malformed_nu_constraint_is_error(self):
        pkg = base_package()
        pkg["versions"][0]["nu_version"] = "latest"
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("nu_version token" in e for e in errors))

    def test_duplicate_sha256_is_error(self):
        pkg = base_package()
        pkg["versions"][0]["artifact"]["targets"]["aarch64-unknown-linux-gnu"] = {
            "url": "https://example.com/demo2.tar.gz",
            "sha256": "a" * 64,
            "executable_path": "nu_plugin_demo",
        }
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("duplicate sha256" in e for e in errors))

    def test_source_rev_head_is_error(self):
        pkg = base_package()
        pkg["versions"][0]["source"]["rev"] = "HEAD"
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("not immutable provenance" in e for e in errors))

    def test_module_activation_tag_requires_declaration(self):
        pkg = base_package(
            type="module",
            tags=["module", "activatable"],
            id={"owner": "acme", "name": "demo_mod"},
        )
        pkg["versions"][0]["artifact"] = {
            "kind": "archive",
            "url": "https://example.com/mod.zip",
            "sha256": "c" * 64,
        }
        pkg["versions"][0].pop("source", None)
        errors = self.lint.lint_index({"packages": [pkg]})
        self.assertTrue(any("missing activation declaration" in e for e in errors))

    def test_main_ok_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            index_path.write_text(
                '{"packages": ['
                + json.dumps(base_package())
                + "]}",
                encoding="utf-8",
            )
            code = self.lint.main(["--index", str(index_path)])
            self.assertEqual(code, 0)

    def test_errors_are_sorted_deterministic(self):
        # Process zz before aa so generation order differs from sorted order.
        # Repeat zz so main()'s sorted(set(...)) collapses duplicate messages.
        zz = base_package(
            id={"owner": "zz", "name": "pkg"},
            description="",
            repo="",
        )
        aa = base_package(
            id={"owner": "aa", "name": "pkg"},
            description="",
            repo="",
        )
        index = {"packages": [zz, "not-a-package", aa, zz]}
        raw = self.lint.lint_index(index)
        expected = sorted(set(raw))
        self.assertNotEqual(raw, expected)
        self.assertLess(len(expected), len(raw))
        expected_lines = [f"  - {error}" for error in expected]

        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            buf = StringIO()
            with redirect_stdout(buf):
                code = self.lint.main(["--index", str(index_path)])
            self.assertEqual(code, 1)
            emitted = [
                line for line in buf.getvalue().splitlines() if line.startswith("  - ")
            ]
            self.assertEqual(emitted, expected_lines)
            self.assertTrue(emitted[0].startswith("  - aa/"))
            self.assertTrue(any("packages[1]:" in line for line in emitted))

    def test_malformed_entries_keep_distinct_labels(self):
        errors = self.lint.lint_index(
            {"packages": ["x", "y", {"description": "no-id"}]}
        )
        self.assertIn("packages[0]: entry must be an object", errors)
        self.assertIn("packages[1]: entry must be an object", errors)
        self.assertTrue(
            any(e.startswith("<unknown-package#2>:") for e in errors)
        )


if __name__ == "__main__":
    unittest.main()
