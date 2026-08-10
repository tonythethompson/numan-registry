#!/usr/bin/env python3
"""Unit checks for scripts/migrate-provisional.py (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "migrate-provisional.py"


def load_migrate():
    spec = importlib.util.spec_from_file_location("migrate_provisional", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def plugin_version(**overrides):
    version = {
        "version": "1.0.0",
        "nu_version": ">=0.113.0 <0.114.0",
        "artifact": {"kind": "binary", "targets": {}},
    }
    version.update(overrides)
    return version


class NeedsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_migrate()

    def test_plugin_without_evidence_needs_migration(self):
        pkg = {"type": "plugin"}
        self.assertTrue(self.mod.needs_migration(pkg, plugin_version()))

    def test_module_with_activation_and_no_evidence_needs_migration(self):
        pkg = {"type": "module"}
        version = plugin_version(activation={"kind": "nu-module"})
        self.assertTrue(self.mod.needs_migration(pkg, version))

    def test_script_type_without_activation_is_not_activatable(self):
        pkg = {"type": "script"}
        self.assertFalse(self.mod.needs_migration(pkg, plugin_version()))

    def test_already_has_evidence_tier_is_untouched(self):
        pkg = {"type": "plugin"}
        version = plugin_version(evidence_tier="proven")
        self.assertFalse(self.mod.needs_migration(pkg, version))

    def test_has_verified_with_is_not_migrated(self):
        pkg = {"type": "plugin"}
        version = plugin_version(verified_with=["0.113.1"])
        self.assertFalse(self.mod.needs_migration(pkg, version))

    def test_non_dict_version_is_not_migrated(self):
        self.assertFalse(self.mod.needs_migration({"type": "plugin"}, "bad"))

    def test_malformed_truthy_verified_with_still_migrates(self):
        pkg = {"type": "plugin"}
        version = plugin_version(verified_with="0.113.1")
        self.assertTrue(self.mod.needs_migration(pkg, version))


class MigrateIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_migrate()

    def test_backfills_qualifying_entry(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "pkg"},
                    "type": "plugin",
                    "versions": [plugin_version()],
                }
            ]
        }
        touched = self.mod.migrate_index(index)
        self.assertEqual(touched, ["acme/pkg@1.0.0"])
        version = index["packages"][0]["versions"][0]
        self.assertEqual(version["evidence_tier"], "provisional")
        self.assertEqual(version["deferral_reason"], "pre-reform provisional intake")

    def test_is_idempotent(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "pkg"},
                    "type": "plugin",
                    "versions": [plugin_version()],
                }
            ]
        }
        self.mod.migrate_index(index)
        second_pass = self.mod.migrate_index(index)
        self.assertEqual(second_pass, [])

    def test_skips_proven_and_non_activatable_entries(self):
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "proven-pkg"},
                    "type": "plugin",
                    "versions": [plugin_version(verified_with=["0.113.1"])],
                },
                {
                    "id": {"owner": "acme", "name": "script-pkg"},
                    "type": "script",
                    "versions": [plugin_version()],
                },
            ]
        }
        touched = self.mod.migrate_index(index)
        self.assertEqual(touched, [])


class MainCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_migrate()

    def _write_index(self, tmp: str) -> Path:
        index_path = Path(tmp) / "index.json"
        index = {
            "packages": [
                {
                    "id": {"owner": "acme", "name": "pkg"},
                    "type": "plugin",
                    "versions": [plugin_version()],
                }
            ]
        }
        index_path.write_text(json.dumps(index), encoding="utf-8")
        return index_path

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = self._write_index(tmp)
            before = index_path.read_text(encoding="utf-8")
            code = self.mod.main(["--index", str(index_path)])
            self.assertEqual(code, 0)
            self.assertEqual(index_path.read_text(encoding="utf-8"), before)

    def test_write_applies_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = self._write_index(tmp)
            code = self.mod.main(["--index", str(index_path), "--write"])
            self.assertEqual(code, 0)
            written = json.loads(index_path.read_text(encoding="utf-8"))
            version = written["packages"][0]["versions"][0]
            self.assertEqual(version["evidence_tier"], "provisional")

    def test_no_qualifying_entries_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            index_path.write_text(json.dumps({"packages": []}), encoding="utf-8")
            code = self.mod.main(["--index", str(index_path)])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
