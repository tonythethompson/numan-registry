#!/usr/bin/env python3.12
"""Tests for scripts/open_intake_pr.py (Stage 6: PR generation)."""

from __future__ import annotations

import contextlib
import io
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


class TestStageHelpers(unittest.TestCase):
    """Lock in behavior parity of the stage helpers extracted from open_intake_pr()."""

    def _stderr_of(self, fn):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            fn()
        return buf.getvalue()

    def test_guard_evidence_passes_on_pass(self):
        # Should not raise or exit for pass/partial.
        open_intake_pr._guard_evidence({"overall": "pass"})
        open_intake_pr._guard_evidence({"overall": "partial"})

    def test_guard_evidence_exits_on_fail(self):
        with self.assertRaises(SystemExit) as raised:
            open_intake_pr._guard_evidence({"overall": "fail"})
        self.assertEqual(raised.exception.code, 1)

    def test_stage_create_branch_dry_run_prints_and_skips_run(self):
        with patch.object(open_intake_pr, "_run") as run:
            out = self._stderr_of(
                lambda: open_intake_pr._stage_create_branch("intake/x", dry_run=True)
            )
        self.assertIn("[dry-run] would: git checkout -b intake/x", out)
        run.assert_not_called()

    def test_stage_create_branch_real_runs_git(self):
        with patch.object(open_intake_pr, "_run") as run:
            open_intake_pr._stage_create_branch("intake/x", dry_run=False)
        run.assert_called_once_with(["git", "checkout", "-b", "intake/x"])

    def test_stage_merge_into_index_real_runs_add_package(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        with (
            patch.object(open_intake_pr, "_run") as run,
            tempfile.TemporaryDirectory() as tmp,
        ):
            with patch.object(
                open_intake_pr.tempfile, "mkdtemp", return_value=tmp
            ):
                open_intake_pr._stage_merge_into_index(
                    Path(tmp) / "spec.json", spec, "acme-pkg-1.0.0.json", dry_run=False
                )
        args, kwargs = run.call_args
        self.assertIn("add-package.py", " ".join(args[0]))
        self.assertIn("--spec", args[0])
        self.assertIn("--write", args[0])
        self.assertIn("--provisional", args[0])
        self.assertFalse(kwargs["dry_run"])

    def test_stage_commit_and_push_dry_run_prints_exact_lines(self):
        with patch.object(open_intake_pr, "_run") as run:
            out = self._stderr_of(
                lambda: open_intake_pr._stage_commit_and_push(
                    "acme", "pkg", "1.0.0", "intake/acme-pkg-1.0.0",
                    Path("specs/acme-pkg-1.0.0.json"), dry_run=True,
                )
            )
        self.assertIn("[dry-run] would: git add specs/acme-pkg-1.0.0.json registry/index.json docs/", out)
        self.assertIn("[dry-run] would: git commit -m 'Intake acme/pkg v1.0.0'", out)
        self.assertIn("[dry-run] would: git push origin intake/acme-pkg-1.0.0", out)
        run.assert_not_called()

    def test_stage_commit_and_push_real_runs_git(self):
        with patch.object(open_intake_pr, "_run") as run:
            open_intake_pr._stage_commit_and_push(
                "acme", "pkg", "1.0.0", "intake/acme-pkg-1.0.0",
                Path("specs/acme-pkg-1.0.0.json"), dry_run=False,
            )
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[0].args[0][:2], ["git", "add"])
        self.assertTrue(any("specs" in arg for arg in run.call_args_list[0].args[0]))
        self.assertEqual(run.call_args_list[1].args[0][:2], ["git", "commit"])
        self.assertEqual(run.call_args_list[2].args[0][:3], ["git", "push", "origin"])

    def test_stage_open_pr_dry_run_prints_preview(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        with patch.object(open_intake_pr, "_run") as run:
            out = self._stderr_of(
                lambda: open_intake_pr._stage_open_pr(
                    "acme", "pkg", "1.0.0", spec, evidence, dry_run=True
                )
            )
        self.assertIn("[dry-run] would: gh pr create --title 'Intake: acme/pkg v1.0.0'", out)
        self.assertIn("--- PR body preview ---", out)
        self.assertIn("## Intake: acme/pkg v1.0.0", out)
        run.assert_not_called()

    def test_stage_open_pr_real_runs_gh(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        with patch.object(open_intake_pr, "_run") as run:
            open_intake_pr._stage_open_pr(
                "acme", "pkg", "1.0.0", spec, evidence, dry_run=False
            )
        args, _kwargs = run.call_args
        self.assertEqual(args[0][:3], ["gh", "pr", "create"])
        self.assertIn("--body", args[0])
        self.assertIn("--base", args[0])

    def test_print_intake_header_includes_dry_run_mode(self):
        out = self._stderr_of(
            lambda: open_intake_pr._print_intake_header(
                "acme", "pkg", "1.0.0", "intake/acme-pkg-1.0.0",
                "acme-pkg-1.0.0.json", dry_run=True,
            )
        )
        self.assertIn("Intake: acme/pkg v1.0.0", out)
        self.assertIn("  Branch: intake/acme-pkg-1.0.0", out)
        self.assertIn("  Spec:   specs/acme-pkg-1.0.0.json", out)
        self.assertIn("  Mode:   DRY RUN (no mutations)", out)


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
