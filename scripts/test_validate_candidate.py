#!/usr/bin/env python3.12
"""Tests for scripts/validate_candidate.py (Stage 5: validation harness)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import validate_candidate


def _write_spec(tmp: str) -> Path:
    """Write a minimal valid spec fixture and return its path."""
    spec = {
        "owner": "vyadh",
        "name": "nutest",
        "description": "Test framework",
        "repo": "https://github.com/vyadh/nutest",
        "type": "module",
        "tags": ["module"],
        "version": "1.2.0",
        "nu_version": "*",
        "artifact": {"kind": "archive", "url": "https://example.com/nutest.zip", "entry": "mod.nu"},
    }
    path = Path(tmp) / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


class TestRunScript(unittest.TestCase):
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        ok, output = validate_candidate._run_script(["script.py"], label="test")
        self.assertTrue(ok)
        self.assertEqual(output, "ok")

    @patch("subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: bad")
        ok, output = validate_candidate._run_script(["script.py"], label="test")
        self.assertFalse(ok)
        self.assertIn("error: bad", output)

    @patch("subprocess.run", side_effect=FileNotFoundError("no python"))
    def test_missing_binary(self, mock_run):
        ok, output = validate_candidate._run_script(["script.py"], label="test")
        self.assertFalse(ok)
        self.assertIn("no python", output)


class TestValidateCandidate(unittest.TestCase):
    @patch("validate_candidate._run_script")
    def test_all_pass(self, mock_run):
        # Simulate all steps passing
        def side_effect(args, *, label):
            if label == "add-package":
                # Write a fake index so target counting works
                idx_arg = args.index("--index") + 1 if "--index" in args else None
                if idx_arg:
                    Path(args[idx_arg]).write_text(json.dumps({
                        "schema_version": 1,
                        "registry": "test",
                        "packages": [{"id": "vyadh/nutest", "versions": [{"version": "1.2.0", "artifact": {"kind": "archive", "url": "x"}}]}],
                    }))
                return True, "ok"
            return True, ""

        mock_run.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmp:
            spec_path = _write_spec(tmp)
            evidence = validate_candidate.validate_candidate(spec_path)

        self.assertEqual(evidence["overall"], "pass")
        self.assertEqual(evidence["package_id"], "vyadh/nutest")
        self.assertEqual(len(evidence["checks"]), 4)
        # Lifecycle should be skip (no --prove)
        lifecycle = next(c for c in evidence["checks"] if c["name"] == "lifecycle")
        self.assertEqual(lifecycle["status"], "skip")

    @patch("validate_candidate._run_script")
    def test_download_fail(self, mock_run):
        def side_effect(args, *, label):
            if label == "add-package":
                return False, "download failed: 404"
            return True, ""

        mock_run.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmp:
            spec_path = _write_spec(tmp)
            evidence = validate_candidate.validate_candidate(spec_path)

        self.assertEqual(evidence["overall"], "fail")
        dl = next(c for c in evidence["checks"] if c["name"] == "download_and_hash")
        self.assertEqual(dl["status"], "fail")

    @patch("validate_candidate._run_script")
    def test_wrapped_spec_format(self, mock_run):
        """Handles {spec, _meta} wrapped format from gen_candidate."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            wrapped = {
                "spec": {
                    "owner": "test",
                    "name": "pkg",
                    "description": "d",
                    "repo": "https://x",
                    "type": "module",
                    "tags": ["module"],
                    "version": "1.0.0",
                    "nu_version": "*",
                    "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
                },
                "_meta": {"generated_from": "discovery-v1"},
            }
            path = Path(tmp) / "wrapped.json"
            path.write_text(json.dumps(wrapped), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path)

        self.assertEqual(evidence["package_id"], "test/pkg")

    @patch("validate_candidate._run_script")
    def test_activatable_plugin_requires_lifecycle_evidence(self, mock_run):
        """A plugin without --prove or deferral cannot report overall pass."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "nu_plugin_x",
                "description": "d",
                "repo": "https://x",
                "type": "plugin",
                "tags": ["plugin"],
                "version": "1.0.0",
                "nu_version": ">=0.114.0 <0.115.0",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path)

        self.assertEqual(evidence["overall"], "fail")
        lifecycle = next(c for c in evidence["checks"] if c["name"] == "lifecycle")
        self.assertEqual(lifecycle["status"], "skip")
        self.assertIn("Lifecycle evidence required", evidence["human_summary"])

    @patch("validate_candidate._run_script")
    def test_activatable_plugin_with_deferral_passes(self, mock_run):
        """A plugin can pass when lifecycle is explicitly deferred with a reason."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "nu_plugin_x",
                "description": "d",
                "repo": "https://x",
                "type": "plugin",
                "tags": ["plugin"],
                "version": "1.0.0",
                "nu_version": ">=0.114.0 <0.115.0",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(
                path, lifecycle_deferral="not yet in live registry",
            )

        self.assertEqual(evidence["overall"], "pass")
        lifecycle = next(c for c in evidence["checks"] if c["name"] == "lifecycle")
        self.assertEqual(lifecycle["detail"], "deferred: not yet in live registry")
        self.assertEqual(evidence.get("lifecycle_deferral"), {"reason": "not yet in live registry"})
        self.assertIn("Lifecycle deferred", evidence["human_summary"])

    @patch("validate_candidate._run_script")
    def test_non_activatable_module_passes_without_lifecycle(self, mock_run):
        """A module without activation does not require lifecycle evidence."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "pkg",
                "description": "d",
                "repo": "https://x",
                "type": "module",
                "tags": ["module"],
                "version": "1.0.0",
                "nu_version": "*",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path)

        self.assertEqual(evidence["overall"], "pass")

    @patch("validate_candidate._run_script")
    def test_activatable_module_requires_lifecycle_evidence(self, mock_run):
        """A module with activation requires lifecycle evidence or deferral."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "pkg",
                "description": "d",
                "repo": "https://x",
                "type": "module",
                "tags": ["module"],
                "version": "1.0.0",
                "nu_version": "*",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
                "activation": {"kind": "nu-module", "import": "all"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path)

        self.assertEqual(evidence["overall"], "fail")


    @patch("validate_candidate._run_script")
    def test_failed_lifecycle_proof_fails_activatable(self, mock_run):
        """A failed lifecycle proof must not satisfy lifecycle evidence."""
        def side_effect(args, *, label):
            if label == "add-package":
                idx_arg = args.index("--index") + 1 if "--index" in args else None
                if idx_arg:
                    Path(args[idx_arg]).write_text(json.dumps({
                        "schema_version": 1,
                        "registry": "test",
                        "packages": [{
                            "id": "test/nu_plugin_x",
                            "versions": [{"version": "1.0.0", "artifact": {"kind": "archive", "url": "x"}}],
                        }],
                    }))
                return True, "ok"
            if label == "lifecycle-prove":
                return False, "package not found in live registry"
            return True, ""

        mock_run.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "nu_plugin_x",
                "description": "d",
                "repo": "https://x",
                "type": "plugin",
                "tags": ["plugin"],
                "version": "1.0.0",
                "nu_version": ">=0.114.0 <0.115.0",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path, prove=True)

        self.assertEqual(evidence["overall"], "fail")
        lifecycle = next(c for c in evidence["checks"] if c["name"] == "lifecycle")
        self.assertEqual(lifecycle["status"], "fail")
        self.assertIn("Lifecycle FAILED", evidence["human_summary"])

    @patch("validate_candidate._run_script")
    def test_whitespace_deferral_treated_as_missing(self, mock_run):
        """A whitespace-only deferral is not a valid reason."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "nu_plugin_x",
                "description": "d",
                "repo": "https://x",
                "type": "plugin",
                "tags": ["plugin"],
                "version": "1.0.0",
                "nu_version": ">=0.114.0 <0.115.0",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            evidence = validate_candidate.validate_candidate(path, lifecycle_deferral="   ")

        self.assertEqual(evidence["overall"], "fail")
        self.assertNotIn("lifecycle_deferral", evidence)
        self.assertIn("Lifecycle evidence required", evidence["human_summary"])

    @patch("validate_candidate._run_script")
    def test_prove_and_deferral_mutually_exclusive(self, mock_run):
        """--prove cannot be combined with --lifecycle-deferral."""
        mock_run.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmp:
            spec = {
                "owner": "test",
                "name": "nu_plugin_x",
                "description": "d",
                "repo": "https://x",
                "type": "plugin",
                "tags": ["plugin"],
                "version": "1.0.0",
                "nu_version": ">=0.114.0 <0.115.0",
                "artifact": {"kind": "archive", "url": "https://x/a.zip", "entry": "mod.nu"},
            }
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_candidate.validate_candidate(
                    path, prove=True, lifecycle_deferral="not yet staged"
                )


if __name__ == "__main__":
    unittest.main()
