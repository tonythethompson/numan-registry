#!/usr/bin/env python3.12
"""Tests for scripts/open_intake_pr.py (Stage 6: PR generation)."""

from __future__ import annotations

import json
import subprocess
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

    def test_preserves_optional_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "intake-state.json"
            existing = {
                "schema_version": 1,
                "ready": [{
                    "id": "test/pkg",
                    "name": "pkg",
                    "owner": "test",
                    "type": "plugin",
                    "version": "0.9.0",
                    "platforms": "all",
                    "repo": "https://github.com/test/pkg",
                    "spec": "specs/test-pkg-0.9.0.json",
                    "pr": 42,
                    "note": "tracked",
                    "outreach": {"upstream_repo": "test/pkg"},
                }],
            }
            state_path.write_text(json.dumps(existing))
            with patch.object(open_intake_pr, "INTAKE_STATE_PATH", state_path):
                open_intake_pr._update_intake_state(
                    "test", "pkg", "1.0.0", "plugin", "specs/test-pkg-1.0.0.json",
                    "https://github.com/test/pkg", dry_run=False,
                )
            state = json.loads(state_path.read_text())
            self.assertEqual(len(state["ready"]), 1)
            entry = state["ready"][0]
            self.assertEqual(entry["version"], "1.0.0")
            self.assertEqual(entry["spec"], "specs/test-pkg-1.0.0.json")
            self.assertEqual(entry["platforms"], "all")
            self.assertEqual(entry["pr"], 42)
            self.assertEqual(entry["note"], "tracked")
            self.assertEqual(entry["outreach"], {"upstream_repo": "test/pkg"})

    def test_atomic_write_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "intake-state.json"
            state_path.write_text(json.dumps({"schema_version": 1, "ready": []}))
            with patch.object(open_intake_pr, "INTAKE_STATE_PATH", state_path):
                open_intake_pr._update_intake_state(
                    "test", "pkg", "1.0.0", "plugin", "specs/test-pkg-1.0.0.json",
                    "https://github.com/test/pkg", dry_run=False,
                )
            backup_path = state_path.with_suffix(state_path.suffix + ".bak")
            self.assertTrue(backup_path.is_file())
            backup = json.loads(backup_path.read_text())
            self.assertEqual(backup["schema_version"], 1)
            self.assertEqual(backup["ready"], [])


class TestGitSafetyHelpers(unittest.TestCase):
    def test_is_worktree_dirty_true_when_output_non_empty(self):
        fake_result = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=" M scripts/open_intake_pr.py",
            stderr="",
        )
        with patch.object(open_intake_pr.subprocess, "run", return_value=fake_result):
            self.assertTrue(open_intake_pr._is_worktree_dirty())

    def test_is_worktree_dirty_false_when_output_empty(self):
        fake_result = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch.object(open_intake_pr.subprocess, "run", return_value=fake_result):
            self.assertFalse(open_intake_pr._is_worktree_dirty())

    def test_is_worktree_dirty_true_when_git_status_fails(self):
        fake_result = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository",
        )
        with patch.object(open_intake_pr.subprocess, "run", return_value=fake_result):
            self.assertTrue(open_intake_pr._is_worktree_dirty())

    def test_current_branch_returns_stripped_stdout(self):
        fake_result = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="intake/feature-branch",
            stderr="",
        )
        with patch.object(open_intake_pr.subprocess, "run", return_value=fake_result):
            self.assertEqual(open_intake_pr._current_branch(), "intake/feature-branch")

    def test_cleanup_intake_branch_runs_checkout_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracked.txt"
            path.write_text("staged", encoding="utf-8")

            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with patch.object(open_intake_pr.subprocess, "run", side_effect=fake_run):
                open_intake_pr._cleanup_intake_branch(
                    "intake/test-pkg-1.0.0", "main", [path]
                )

        self.assertEqual(
            calls,
            [
                ["git", "checkout", "--", str(path)],
                ["git", "checkout", "main"],
                ["git", "branch", "-D", "intake/test-pkg-1.0.0"],
            ],
        )

    def test_cleanup_restores_tracked_files_before_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracked = Path(tmp) / "tracked.txt"
            missing = Path(tmp) / "missing.txt"
            tracked.write_text("staged changes", encoding="utf-8")

            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with patch.object(open_intake_pr.subprocess, "run", side_effect=fake_run):
                open_intake_pr._cleanup_intake_branch(
                    "intake/test-pkg-1.0.0", "main", [tracked, missing]
                )

            self.assertEqual(
                calls[0],
                ["git", "checkout", "--", str(tracked)],
            )
            self.assertFalse(tracked.exists())

    def test_cleanup_warns_without_raising_on_git_failure(self):
        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        with patch.object(open_intake_pr.subprocess, "run", side_effect=fake_run):
            open_intake_pr._cleanup_intake_branch(
                "intake/test-pkg-1.0.0", "main", [Path("registry/index.json")]
            )

if __name__ == "__main__":
    unittest.main()
