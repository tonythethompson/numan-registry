#!/usr/bin/env python3.12
"""Checks that production promotion requires real-Nu lifecycle evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jsonschema

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_mod(name: str, filename: str):
    """
    Load and return a Python module from a file in the scripts directory.
    
    Parameters:
    	name (str): Name to register for the loaded module.
    	filename (str): Module filename relative to the scripts directory.
    
    Returns:
    	module: The loaded Python module.
    """
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def package(package_type: str, *, activation: bool, evidence=None):
    """
    Build a package index entry fixture with configurable package type, activation, and verification evidence.
    
    Parameters:
    	package_type (str): The package type to include in the fixture.
    	activation (bool): Whether to include Nu module activation metadata.
    	evidence: Verification evidence to include when provided.
    
    Returns:
    	dict: A package index entry containing one version and its artifact metadata.
    """
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
        """
        Load the validation helpers and index schema shared by the test class.
        
        Parameters:
        	cls: The test class receiving the loaded modules and parsed schema.
        """
        cls.validate = load_mod("validate_lifecycle", "validate.py")
        cls.add_package = load_mod("add_package_lifecycle", "add-package.py")
        cls.schema = json.loads((ROOT / "schemas" / "index-v1.json").read_text())

    def index(self, pkg):
        """
        Wrap a package entry in a versioned package index structure.
        
        Parameters:
        	pkg: The package entry to include in the index.
        
        Returns:
        	dict: An index containing the schema version, update timestamp, and package entry.
        """
        return {
            "schema_version": 1,
            "updated_at": "2026-07-29T00:00:00Z",
            "packages": [pkg],
        }

    def assert_schema_rejects(self, pkg):
        """Assert that a package causes its wrapped index to fail schema validation.
        
        Parameters:
        	pkg: The package dictionary to validate within the index.
        """
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.index(pkg), self.schema)

    def test_plugin_requires_nonempty_verified_with(self):
        pkg = package("plugin", activation=False)
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(self.index(pkg)),
            [
                "acme/pkg@1.0.0: verified_with must contain at least one "
                "exact Nu version"
            ],
        )
        # Schema permits a provisional staging shape; production validation
        # supplies the promotion gate.
        jsonschema.validate(self.index(pkg), self.schema)

    def test_explicitly_activated_module_requires_evidence(self):
        """Verify that explicitly activated modules require exact Nu-version evidence."""
        pkg = package("module", activation=True)
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(self.index(pkg)),
            [
                "acme/pkg@1.0.0: verified_with must contain at least one "
                "exact Nu version"
            ],
        )
        jsonschema.validate(self.index(pkg), self.schema)

    def test_install_only_package_does_not_require_evidence(self):
        pkg = package("script", activation=False)
        self.assertEqual(self.validate.lifecycle_evidence_errors(self.index(pkg)), [])
        jsonschema.validate(self.index(pkg), self.schema)

    def test_nonempty_evidence_passes_validator_and_schema(self):
        """
        Verify that valid evidence passes lifecycle and schema validation for plugins and activated modules.
        """
        for pkg in (
            package("plugin", activation=False, evidence=["0.114.1"]),
            package("module", activation=True, evidence=["0.114.1"]),
        ):
            self.assertEqual(self.validate.lifecycle_evidence_errors(self.index(pkg)), [])
            jsonschema.validate(self.index(pkg), self.schema)

    def test_blank_evidence_is_rejected(self):
        pkg = package("plugin", activation=False, evidence=["  "])
        self.assertIn(
            "is not an exact Nu version",
            self.validate.lifecycle_evidence_errors(self.index(pkg))[0],
        )
        self.assert_schema_rejects(pkg)

    def test_malformed_evidence_is_rejected(self):
        pkg = package("plugin", activation=False, evidence=["not-tested"])
        self.assertIn(
            "is not an exact Nu version",
            self.validate.lifecycle_evidence_errors(self.index(pkg))[0],
        )
        self.assert_schema_rejects(pkg)

    def test_incompatible_evidence_is_rejected(self):
        pkg = package("plugin", activation=False, evidence=["0.113.1"])
        self.assertIn(
            "does not satisfy",
            self.validate.lifecycle_evidence_errors(self.index(pkg))[0],
        )
        # Schema establishes syntax; production validation establishes
        # compatibility with the sibling nu_version constraint.
        jsonschema.validate(self.index(pkg), self.schema)

    def test_constraint_forms_match_numan_contract(self):
        for constraint, version in (
            ("*", "0.114.1"),
            (">=0.114.0", "0.114.1"),
            ("=0.114.x", "0.114.1"),
            ("0.114.x", "0.114.1"),
            ("0.114.1", "0.114.1"),
        ):
            pkg = package("plugin", activation=False, evidence=[version])
            pkg["versions"][0]["nu_version"] = constraint
            self.assertEqual(
                self.validate.lifecycle_evidence_errors(self.index(pkg)), []
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
        self.add_package.validate_spec(spec, allow_provisional=True)
        self.assertEqual(
            self.validate.lifecycle_evidence_errors(
                self.index(package("plugin", activation=False)),
                allow_missing=True,
            ),
            [],
        )
        valid = copy.deepcopy(spec)
        valid["verified_with"] = ["0.114.1"]
        self.add_package.validate_spec(valid)

        invalid = copy.deepcopy(spec)
        invalid["verified_with"] = ["0.113.1"]
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(invalid)
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(invalid, allow_provisional=True)

    def test_numan_maintained_owner_requires_source_upstream(self):
        spec = {
            "owner": "numan-maintained",
            "name": "pkg",
            "description": "fixture fork",
            "repo": "https://example.com/numan-maintained/pkg",
            "type": "plugin",
            "tags": [],
            "version": "1.0.0",
            "nu_version": ">=0.114.0 <0.115.0",
            "verified_with": ["0.114.1"],
            "artifact": {"kind": "binary", "targets": {}},
        }
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(spec)

        with_non_dict_source = copy.deepcopy(spec)
        with_non_dict_source["source"] = "oops"
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(with_non_dict_source)

        with_source_no_upstream = copy.deepcopy(spec)
        with_source_no_upstream["source"] = {
            "git": "https://example.com/numan-maintained/pkg",
            "rev": "a" * 40,
            "cargo_name": "pkg",
        }
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(with_source_no_upstream)

        with_whitespace_upstream = copy.deepcopy(spec)
        with_whitespace_upstream["source"] = {
            "upstream": "   ",
        }
        with self.assertRaises(SystemExit):
            self.add_package.validate_spec(with_whitespace_upstream)

        with_upstream = copy.deepcopy(spec)
        with_upstream["source"] = {
            "git": "https://example.com/numan-maintained/pkg",
            "rev": "a" * 40,
            "cargo_name": "pkg",
            "upstream": "https://example.com/original-author/pkg",
        }
        self.add_package.validate_spec(with_upstream)

    def test_schema_failure_skips_lifecycle_traversal(self):
        malformed = {
            "schema_version": 1,
            "updated_at": "2026-07-29T00:00:00Z",
            "packages": [None],
        }
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            index_path.write_text(json.dumps(malformed), encoding="utf-8")
            argv = [
                "validate.py",
                "--index",
                str(index_path),
                "--schema",
                str(ROOT / "schemas" / "index-v1.json"),
                "--skip-signature",
                "--skip-artifacts",
            ]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(self.validate.main(), 1)


if __name__ == "__main__":
    unittest.main()
