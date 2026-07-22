#!/usr/bin/env python3
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

    def test_main_rejects_missing_slash(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            numan = root / "numan"
            nu = root / "nu"
            numan.write_bytes(b"")
            nu.write_bytes(b"")
            code = self.mod.main(
                [
                    "--package",
                    "noslash",
                    "--numan",
                    str(numan),
                    "--nu",
                    str(nu),
                    "--root",
                    str(root / "numan-root"),
                ]
            )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
