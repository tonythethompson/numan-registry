#!/usr/bin/env python3
"""Unit checks for scripts/render_catalog_compat.py (no network)."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "render_catalog_compat.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("render_catalog_compat", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class RenderCatalogCompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_mod()

    def test_render_includes_packages_and_bands(self):
        index = {
            "updated_at": "2026-08-05T00:00:00Z",
            "registry_revision": "test",
            "packages": [
                {
                    "id": {"owner": "acme", "name": "nu_plugin_x"},
                    "type": "plugin",
                    "versions": [
                        {
                            "version": "1.0.0",
                            "nu_version": ">=0.114.0 <0.115.0",
                            "artifact": {
                                "kind": "binary",
                                "targets": {
                                    "x86_64-unknown-linux-gnu": {
                                        "url": "https://example.com/x.tar.gz"
                                    },
                                    "x86_64-pc-windows-msvc": {
                                        "url": "https://example.com/x.zip"
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "id": {"owner": "acme", "name": "mod"},
                    "type": "module",
                    "versions": [
                        {
                            "version": "2.0.0",
                            "nu_version": "*",
                            "artifact": {"url": "https://example.com/m.zip"},
                        }
                    ],
                },
            ],
        }
        text = self.mod.render(index, generated_at="2026-08-05T00:00:00Z")
        self.assertIn("**2** packages total", text)
        self.assertIn("`plugin` 1", text)
        self.assertIn("`module` 1", text)
        self.assertIn("`0.114` 1", text)
        self.assertIn("`*` 1", text)
        self.assertIn("`acme/nu_plugin_x`", text)
        self.assertIn("win,linux", text)
        self.assertIn("upstream", text)

    def test_nu_band_uses_lower_bound_not_upper(self):
        self.assertEqual(self.mod.nu_band(">=0.113.0 <0.114.0"), "0.113")
        self.assertEqual(self.mod.nu_band(">=0.112.0 <0.113.0"), "0.112")
        self.assertEqual(self.mod.nu_band(">=0.114.0 <0.115.0"), "0.114")
        self.assertEqual(self.mod.nu_band("*"), "*")
        self.assertEqual(self.mod.nu_band(">=0.92.0"), "other")
        index = {
            "updated_at": "2026-08-05T00:00:00Z",
            "registry_revision": "test",
            "packages": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_path = root / "index.json"
            out_path = root / "catalog-compat.md"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            out_path.write_text("stale\n", encoding="utf-8")
            # monkeypatch via argv-style call by invoking main pieces
            text = self.mod.render(index, generated_at="2026-08-05T00:00:00Z")
            self.assertNotEqual(out_path.read_text(encoding="utf-8"), text)
            out_path.write_text(text, encoding="utf-8")
            self.assertEqual(out_path.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
