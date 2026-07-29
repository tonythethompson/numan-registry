#!/usr/bin/env python3.12
"""Checks that production promotion requires real-Nu lifecycle evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import jsonschema

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent


def load_mod(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def package(package_type: str, *, activation: bool, evidence=None):
    version = {
        "version": "1.0.0",
        "nu_version": ">=0.114.0 <0.115.0",
        "artifact": {
            "kind": "archive",
            "url": "https://example.com/package.zip",
            "sha256": "a" * 64,
        },
    }
    if activation:
        version["activation"] = {"kind": "nu-module", "import": "all"}
    if evidence is not None:
        version["verified_with"] = evidence
    return {
        "id": {"owner": "acme", "name": "pkg"},
        "description": "fixture",
        "repo": "https://example.com/acme/pkg",
        "type": package_type,
        "tags": [],
        "versions": [version],
    }


class LifecycleEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = load_mod("validate_lifecycle", "validate.py")
        cls.add_package = load_mod("add_package_lifecycle", "add-package.py")
        cls.schema = json.loads((ROOT / "schemas" / "index-v1.json").read_text())

    def index(self, pkg):
        return {
            "schema_version": 1,
            "updated_at": "2026-07-29T00:00:00Z",
            "packages": [pkg],
        }

    def assert_schema_rejects(self, pkg):
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.index(pkg), self.schema)

    def test_plugin_requires_nonempty_verified_with(self):
        pkg = package("plugin", activation=False)
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(self.index(pkg)),
            ["acme/pkg@1.0.0"],
        )
        self.assert_schema_rejects(pkg)

    def test_explicitly_activated_module_requires_evidence(self):
        pkg = package("module", activation=True)
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(self.index(pkg)),
            ["acme/pkg@1.0.0"],
        )
        self.assert_schema_rejects(pkg)

    def test_install_only_package_does_not_require_evidence(self):
        pkg = package("script", activation=False)
        self.assertEqual(self.validate.lifecycle_evidence_errors(self.index(pkg)), [])
        jsonschema.validate(self.index(pkg), self.schema)

    def test_nonempty_evidence_passes_validator_and_schema(self):
        for pkg in (
            package("plugin", activation=False, evidence=["0.114.1"]),
            package("module", activation=True, evidence=["0.114.1"]),
        ):
            self.assertEqual(self.validate.lifecycle_evidence_errors(self.index(pkg)), [])
            jsonschema.validate(self.index(pkg), self.schema)

    def test_blank_evidence_is_rejected(self):
        pkg = package("plugin", activation=False, evidence=["  "])
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(self.index(pkg)),
            ["acme/pkg@1.0.0"],
        )

    def test_intake_rejects_activatable_spec_without_evidence(self):
        spec = {
            "owner": "acme",
            "name": "pkg",
            "description": "fixture",
            "repo": "https://example.com/acme/pkg",
            "type": "plugin",
            "tags": [],
            "version": "1.0.0",
            "nu_version": ">=0.114.0 <0.115.0",
            "artifact": {"kind": "binary", "targets": {}},
        }
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(spec)
        valid = copy.deepcopy(spec)
        valid["verified_with"] = ["0.114.1"]
        self.add_package.validate_spec(valid)


if __name__ == "__main__":
    unittest.main()
