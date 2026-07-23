#!/usr/bin/env python3.12
"""Unit checks for scripts/lifecycle-prove.py (no network, no real numan)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "lifecycle-prove.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("lifecycle_prove", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class LifecycleProveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_package_search_query(self):
        self.assertEqual(
            self.mod.package_search_query("owner/nu_plugin_x"),
            "nu_plugin_x",
        )
        self.assertEqual(self.mod.package_search_query("plain"), "plain")

    def test_build_steps_order(self):
        names = [s.name for s in self.mod.build_steps("acme/pkg")]
        self.assertEqual(
            names,
            [
                "init",
                "registry sync",
                "search",
                "info",
                "install",
                "activate",
                "doctor",
                "list",
                "deactivate",
                "remove",
                "gc",
            ],
        )

    def test_prove_stops_on_first_failure(self):
        calls: list[str] = []

        def fake_run(step, **_kwargs):
            calls.append(step.name)

            class R:
                returncode = 0 if step.name != "install" else 7

            return R()

        with mock.patch.object(self.mod, "run_step", side_effect=fake_run):
            code = self.mod.prove(
                "acme/pkg",
                numan=Path("numan"),
                nu=Path("nu"),
                root=Path("root"),
                keep_root=True,
            )
        self.assertEqual(code, 7)
        self.assertEqual(
            calls,
            ["init", "registry sync", "search", "info", "install"],
        )

    def test_validate_package_id_valid(self):
        # Valid package IDs should not raise
        self.mod.validate_package_id("owner/name")
        self.mod.validate_package_id("my-owner/my-name")
        self.mod.validate_package_id("o/n")

    def test_validate_package_id_missing_slash(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_package_id("noslash")
        self.assertIn("must be owner/name", str(ctx.exception))

    def test_validate_package_id_empty_owner(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_package_id("/name")
        self.assertIn("empty owner", str(ctx.exception))

    def test_validate_package_id_empty_name(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_package_id("owner/")
        self.assertIn("empty name", str(ctx.exception))

    def test_validate_package_id_extra_components(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_package_id("owner/name/extra")
        self.assertIn("exactly two components", str(ctx.exception))

    def test_main_rejects_missing_slash(self):
        code = self.mod.main(
            [
                "--package",
                "noslash",
                "--numan",
                "/nonexistent/numan",
                "--nu",
                "/nonexistent/nu",
            ]
        )
        self.assertEqual(code, 2)

    def test_main_rejects_empty_owner(self):
        code = self.mod.main(
            [
                "--package",
                "/name",
                "--numan",
                "/nonexistent/numan",
                "--nu",
                "/nonexistent/nu",
            ]
        )
        self.assertEqual(code, 2)

    def test_main_rejects_empty_name(self):
        code = self.mod.main(
            [
                "--package",
                "owner/",
                "--numan",
                "/nonexistent/numan",
                "--nu",
                "/nonexistent/nu",
            ]
        )
        self.assertEqual(code, 2)

    def test_main_rejects_extra_components(self):
        code = self.mod.main(
            [
                "--package",
                "owner/name/extra",
                "--numan",
                "/nonexistent/numan",
                "--nu",
                "/nonexistent/nu",
            ]
        )
        self.assertEqual(code, 2)

    def test_main_rejects_non_executable_path(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            numan = root / "numan"
            nu = root / "nu"
            numan.write_bytes(b"")
            nu.write_bytes(b"")
            # Make files non-executable
            numan.chmod(0o644)
            nu.chmod(0o644)
            code = self.mod.main(
                [
                    "--package",
                    "owner/name",
                    "--numan",
                    str(numan),
                    "--nu",
                    str(nu),
                    "--root",
                    str(root / "numan-root"),
                ]
            )
        self.assertEqual(code, 2)

    def test_main_rejects_non_empty_root(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "existing-root"
            root_dir.mkdir()
            # Make it non-empty
            (root_dir / "somefile.txt").write_text("content")

            numan = Path(tmp) / "numan"
            nu = Path(tmp) / "nu"
            numan.write_bytes(b"#!/bin/sh\n")
            nu.write_bytes(b"#!/bin/sh\n")
            numan.chmod(0o755)
            nu.chmod(0o755)

            code = self.mod.main(
                [
                    "--package",
                    "owner/name",
                    "--numan",
                    str(numan),
                    "--nu",
                    str(nu),
                    "--root",
                    str(root_dir),
                ]
            )
        self.assertEqual(code, 2)

    def test_main_accepts_empty_root(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "empty-root"
            root_dir.mkdir()

            numan = Path(tmp) / "numan"
            nu = Path(tmp) / "nu"
            numan.write_bytes(b"#!/bin/sh\nexit 0\n")
            nu.write_bytes(b"#!/bin/sh\nexit 0\n")
            numan.chmod(0o755)
            nu.chmod(0o755)

            with mock.patch.object(self.mod, "build_steps", return_value=[]):
                code = self.mod.main(
                    [
                        "--package",
                        "owner/name",
                        "--numan",
                        str(numan),
                        "--nu",
                        str(nu),
                        "--root",
                        str(root_dir),
                    ]
                )
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
