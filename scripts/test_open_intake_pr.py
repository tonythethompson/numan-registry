#!/usr/bin/env python3.12
"""Tests for scripts/open_intake_pr.py (Stage 6: PR generation)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import open_intake_pr


class TestSpecFilename(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(
            open_intake_pr._spec_filename("fdncred", "nu_plugin_emoji", "0.23.0"),
            "fdncred-nu_plugin_emoji-0.23.0.json",
        )

    def test_module(self):
        self.assertEqual(
            open_intake_pr._spec_filename("vyadh", "nutest", "1.2.0"),
            "vyadh-nutest-1.2.0.json",
        )


class TestBranchName(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(
            open_intake_pr._branch_name("fdncred", "nu_plugin_emoji", "0.23.0"),
            "intake/fdncred-nu_plugin_emoji-0.23.0",
        )


class TestGeneratePrBody(unittest.TestCase):
    def test_plugin_body(self):
        spec = {
            "owner": "fdncred",
            "name": "nu_plugin_emoji",
            "version": "0.23.0",
            "type": "plugin",
            "nu_version": ">=0.114.0 <0.115.0",
            "repo": "https://github.com/fdncred/nu_plugin_emoji",
            "artifact": {
                "kind": "binary",
                "targets": {
                    "x86_64-pc-windows-msvc": {"url": "x"},
                    "x86_64-unknown-linux-gnu": {"url": "x"},
                },
            },
        }
        evidence = {
            "overall": "pass",
            "human_summary": "2 artifacts downloaded. Lint clean. Schema valid.",
            "checks": [{"name": "lifecycle", "status": "pass"}],
        }
        body = open_intake_pr._generate_pr_body(spec, evidence)
        self.assertIn("## Intake: fdncred/nu_plugin_emoji v0.23.0", body)
        self.assertIn("| Type | plugin |", body)
        self.assertIn("| Targets | 2", body)
        self.assertIn("| Lifecycle | pass |", body)
        self.assertIn("2 artifacts downloaded", body)
        self.assertIn("- [ ] Human reviewed spec fields", body)

    def test_module_body(self):
        spec = {
            "owner": "vyadh",
            "name": "nutest",
            "version": "1.2.0",
            "type": "module",
            "nu_version": "*",
            "repo": "https://github.com/vyadh/nutest",
            "artifact": {"kind": "archive", "url": "x", "entry": "mod.nu"},
        }
        evidence = {"overall": "pass", "human_summary": "ok", "checks": []}
        body = open_intake_pr._generate_pr_body(spec, evidence)
        self.assertIn("| Targets | 1 (archive) |", body)
        self.assertIn("| Lifecycle | not run |", body)


class TestUpdateIntakeState(unittest.TestCase):
    def test_dry_run_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "intake-state.json"
            state_path.write_text(json.dumps({"schema_version": 1, "ready": []}))
            with patch.object(open_intake_pr, "INTAKE_STATE_PATH", state_path):
                open_intake_pr._update_intake_state(
                    "test", "pkg", "1.0.0", "plugin", "specs/test-pkg-1.0.0.json",
                    "https://github.com/test/pkg", dry_run=True,
                )
            # Should not have changed
            state = json.loads(state_path.read_text())
            self.assertEqual(len(state["ready"]), 0)

    def test_actual_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "intake-state.json"
            state_path.write_text(json.dumps({"schema_version": 1, "ready": []}))
            with patch.object(open_intake_pr, "INTAKE_STATE_PATH", state_path):
                open_intake_pr._update_intake_state(
                    "test", "pkg", "1.0.0", "plugin", "specs/test-pkg-1.0.0.json",
                    "https://github.com/test/pkg", dry_run=False,
                )
            state = json.loads(state_path.read_text())
            self.assertEqual(len(state["ready"]), 1)
            self.assertEqual(state["ready"][0]["id"], "test/pkg")

    def test_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "intake-state.json"
            existing = {"schema_version": 1, "ready": [{"id": "test/pkg", "name": "pkg"}]}
            state_path.write_text(json.dumps(existing))
            with patch.object(open_intake_pr, "INTAKE_STATE_PATH", state_path):
                open_intake_pr._update_intake_state(
                    "test", "pkg", "1.0.0", "plugin", "specs/test-pkg-1.0.0.json",
                    "https://github.com/test/pkg", dry_run=False,
                )
            state = json.loads(state_path.read_text())
            self.assertEqual(len(state["ready"]), 1)  # No duplicate added


if __name__ == "__main__":
    unittest.main()
