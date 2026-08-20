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
            tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
            patch.object(open_intake_pr.tempfile, "mkdtemp", return_value=tmp),
        ):
            open_intake_pr._stage_merge_into_index(
                Path(tmp) / "spec.json", spec, "acme-pkg-1.0.0.json",
                "lifecycle validation deferred", dry_run=False
            )
        args, kwargs = run.call_args
        self.assertIn("add-package.py", " ".join(args[0]))
        self.assertIn("--spec", args[0])
        self.assertIn("--write", args[0])
        self.assertIn("--provisional", args[0])
        self.assertFalse(kwargs["dry_run"])

    def test_stage_merge_into_index_proven_skips_provisional(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0", "verified_with": "1.2.3"}
        with (
            patch.object(open_intake_pr, "_run") as run,
            tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
            patch.object(open_intake_pr.tempfile, "mkdtemp", return_value=tmp),
        ):
            open_intake_pr._stage_merge_into_index(
                Path(tmp) / "spec.json", spec, "acme-pkg-1.0.0.json", dry_run=False
            )
        args, kwargs = run.call_args
        self.assertIn("add-package.py", " ".join(args[0]))
        self.assertIn("--spec", args[0])
        self.assertIn("--write", args[0])
        self.assertNotIn("--provisional", args[0])
        self.assertNotIn("--deferral-reason", args[0])
        self.assertFalse(kwargs["dry_run"])

    def test_stage_commit_and_push_dry_run_prints_exact_lines(self):
        with patch.object(open_intake_pr, "_run") as run:
            out = self._stderr_of(
                lambda: open_intake_pr._stage_commit_and_push(
                    "acme", "pkg", "1.0.0", "intake/acme-pkg-1.0.0",
                    Path("specs/acme-pkg-1.0.0.json"), dry_run=True,
                )
            )
        expected_add = " ".join(
            [
                str(Path("specs/acme-pkg-1.0.0.json")),
                str(open_intake_pr.INDEX_PATH),
                str(open_intake_pr.INTAKE_STATE_PATH),
                str(open_intake_pr.REPO_ROOT / "docs" / "intake-candidates.md"),
            ]
        )
        self.assertIn(f"[dry-run] would: git add {expected_add}", out)
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

    def test_stage_open_pr_dry_run_auto_merge_prints_preview(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        with patch.object(open_intake_pr, "_run") as run:
            out = self._stderr_of(
                lambda: open_intake_pr._stage_open_pr(
                    "acme", "pkg", "1.0.0", spec, evidence, dry_run=True, auto_merge=True
                )
            )
        self.assertIn("[dry-run] would: gh pr create --title 'Intake: acme/pkg v1.0.0'", out)
        self.assertIn("[dry-run] would: gh pr merge intake/acme-pkg-1.0.0 --auto --squash", out)
        run.assert_not_called()

    def test_stage_open_pr_real_runs_gh(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        success = subprocess.CompletedProcess(
            args=["gh", "pr", "create"], returncode=0, stdout="https://github.com/numan-cli/numan-registry/pull/99\n", stderr=""
        )
        with patch.object(open_intake_pr, "gh_run", return_value=success) as run:
            open_intake_pr._stage_open_pr(
                "acme", "pkg", "1.0.0", spec, evidence, dry_run=False
            )
        args, _kwargs = run.call_args
        self.assertEqual(args[0][:2], ["pr", "create"])
        self.assertIn("--body", args[0])
        self.assertIn("--base", args[0])

    def test_stage_open_pr_real_auto_merge_passes_pr_target(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        create_success = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/numan-cli/numan-registry/pull/99\n",
            stderr="",
        )
        merge_success = subprocess.CompletedProcess(
            args=["gh", "pr", "merge"], returncode=0, stdout="", stderr=""
        )
        with patch.object(open_intake_pr, "gh_run", side_effect=[create_success, merge_success]) as run:
            open_intake_pr._stage_open_pr(
                "acme", "pkg", "1.0.0", spec, evidence, dry_run=False, auto_merge=True
            )
        self.assertEqual(run.call_count, 2)
        create_args = run.call_args_list[0].args[0]
        merge_args = run.call_args_list[1].args[0]
        self.assertEqual(create_args[:2], ["pr", "create"])
        self.assertEqual(merge_args, ["pr", "merge", "https://github.com/numan-cli/numan-registry/pull/99", "--auto", "--squash"])

    def test_stage_open_pr_real_exits_when_gh_fails(self):
        spec = {"owner": "acme", "name": "pkg", "version": "1.0.0"}
        evidence = {"overall": "pass", "human_summary": "ok"}
        failed = subprocess.CompletedProcess(
            args=["gh", "pr", "create"], returncode=1, stdout="", stderr="boom"
        )
        with (
            patch.object(open_intake_pr, "gh_run", return_value=failed),
            patch.object(open_intake_pr, "gh_json", return_value=[]),
            patch.object(open_intake_pr, "_run", return_value=None) as run,
        ):
            with self.assertRaises(SystemExit) as raised:
                self._stderr_of(
                    lambda: open_intake_pr._stage_open_pr(
                        "acme", "pkg", "1.0.0", spec, evidence, dry_run=False
                    )
                )
        self.assertEqual(raised.exception.code, 1)
        # No PR existed for the pushed branch, so the orphaned remote ref is deleted.
        delete_calls = [c.args[0] for c in run.call_args_list]
        self.assertTrue(
            any(c[:4] == ["git", "push", "origin", "--delete"] for c in delete_calls)
        )

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


class TestReconcileFailedPrCreate(TestStageHelpers):
    """Lock in the remote-branch reconcile behavior after gh pr create fails."""

    def test_pr_exists_keeps_remote_branch_and_reports_url(self):
        with (
            patch.object(
                open_intake_pr, "gh_json",
                return_value=[{"number": 99, "url": "https://github.com/o/r/pull/99"}],
            ),
            patch.object(open_intake_pr, "_run") as run,
        ):
            out = self._stderr_of(
                lambda: open_intake_pr._reconcile_failed_pr_create("acme", "pkg", "1.0.0")
            )
        self.assertIn("https://github.com/o/r/pull/99", out)
        self.assertIn("remote branch kept", out)
        run.assert_not_called()

    def test_no_pr_deletes_remote_branch(self):
        with (
            patch.object(open_intake_pr, "gh_json", return_value=[]),
            patch.object(open_intake_pr, "_run", return_value=None) as run,
        ):
            out = self._stderr_of(
                lambda: open_intake_pr._reconcile_failed_pr_create("acme", "pkg", "1.0.0")
            )
        self.assertIn("deleting remote ref", out)
        run.assert_called_once()
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:4], ["git", "push", "origin", "--delete"])
        self.assertEqual(cmd[4], "intake/acme-pkg-1.0.0")

    def test_unknown_pr_status_keeps_branch(self):
        with (
            patch.object(open_intake_pr, "gh_json", return_value=None),
            patch.object(open_intake_pr, "_run") as run,
        ):
            out = self._stderr_of(
                lambda: open_intake_pr._reconcile_failed_pr_create("acme", "pkg", "1.0.0")
            )
        self.assertIn("remote branch kept", out)
        run.assert_not_called()

    def test_pr_entry_without_url_keeps_branch_and_warns(self):
        with (
            patch.object(open_intake_pr, "gh_json", return_value=[{"number": 99}]),
            patch.object(open_intake_pr, "_run") as run,
        ):
            out = self._stderr_of(
                lambda: open_intake_pr._reconcile_failed_pr_create("acme", "pkg", "1.0.0")
            )
        self.assertIn("URL unavailable", out)
        self.assertIn("remote branch kept", out)
        run.assert_not_called()

    def test_delete_failure_reported_but_keeps_going(self):
        failed_delete = subprocess.CompletedProcess(
            args=["git", "push", "origin", "--delete", "intake/acme-pkg-1.0.0"],
            returncode=1, stdout="", stderr="remote ref does not exist",
        )
        with (
            patch.object(open_intake_pr, "gh_json", return_value=[]),
            patch.object(open_intake_pr, "_run", return_value=failed_delete),
        ):
            out = self._stderr_of(
                lambda: open_intake_pr._reconcile_failed_pr_create("acme", "pkg", "1.0.0")
            )
        self.assertIn("could not delete remote branch", out)
        self.assertIn("remote ref does not exist", out)


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


class TestLoadInputs(unittest.TestCase):
    def test_unwraps_spec_meta_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            evidence_path = Path(tmp) / "evidence.json"
            spec_path.write_text(
                json.dumps({"spec": {"owner": "acme"}, "_meta": {"x": 1}}),
                encoding="utf-8",
            )
            evidence_path.write_text(json.dumps({"overall": "pass"}), encoding="utf-8")
            spec_data, spec, evidence = open_intake_pr._load_inputs(spec_path, evidence_path)
            self.assertEqual(spec_data["_meta"], {"x": 1})
            self.assertEqual(spec, {"owner": "acme"})
            self.assertEqual(evidence, {"overall": "pass"})

    def test_bare_spec_passthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            evidence_path = Path(tmp) / "evidence.json"
            spec_path.write_text(json.dumps({"owner": "acme"}), encoding="utf-8")
            evidence_path.write_text(json.dumps({"overall": "pass"}), encoding="utf-8")
            spec_data, spec, evidence = open_intake_pr._load_inputs(spec_path, evidence_path)
            self.assertEqual(spec_data, {"owner": "acme"})
            self.assertIs(spec, spec_data)
            self.assertEqual(evidence, {"overall": "pass"})


class TestPreparePushBranch(unittest.TestCase):
    def test_refuses_dirty_worktree(self):
        with patch.object(open_intake_pr, "_is_worktree_dirty", return_value=True):
            with self.assertRaises(SystemExit) as raised:
                open_intake_pr._prepare_push_branch()
        self.assertEqual(raised.exception.code, 1)

    def test_refuses_detached_head(self):
        with (
            patch.object(open_intake_pr, "_is_worktree_dirty", return_value=False),
            patch.object(open_intake_pr, "_current_branch", return_value=""),
        ):
            with self.assertRaises(SystemExit) as raised:
                open_intake_pr._prepare_push_branch()
        self.assertEqual(raised.exception.code, 1)

    def test_returns_current_branch(self):
        with (
            patch.object(open_intake_pr, "_is_worktree_dirty", return_value=False),
            patch.object(open_intake_pr, "_current_branch", return_value="main"),
        ):
            self.assertEqual(open_intake_pr._prepare_push_branch(), "main")


class TestStageLintAndRefreshDocs(unittest.TestCase):
    def test_stage_lint_and_validate_runs_lint_then_validate(self):
        with patch.object(open_intake_pr, "_run") as run:
            open_intake_pr._stage_lint_and_validate(dry_run=False)
        self.assertEqual(run.call_count, 2)
        first_args = run.call_args_list[0][0][0]
        second_args = run.call_args_list[1][0][0]
        self.assertIn("lint_packages.py", " ".join(first_args))
        self.assertIn("validate.py", " ".join(second_args))
        self.assertIn("--skip-signature", second_args)
        self.assertIn("--skip-artifacts", second_args)
        self.assertIn("--allow-provisional-lifecycle", second_args)
    def test_stage_refresh_docs_runs_sync_with_check_false(self):
        with patch.object(open_intake_pr, "_run") as run:
            open_intake_pr._stage_refresh_docs(dry_run=False)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertIn("sync-intake-candidates.py", " ".join(args[0]))
        self.assertFalse(kwargs["check"])


class TestOpenIntakePrOrchestration(unittest.TestCase):
    def _write_inputs(self, tmp):
        spec_path = Path(tmp) / "spec.json"
        evidence_path = Path(tmp) / "evidence.json"
        spec_path.write_text(
            json.dumps({"owner": "acme", "name": "pkg", "version": "1.0.0", "type": "script"}),
            encoding="utf-8",
        )
        evidence_path.write_text(json.dumps({"overall": "pass"}), encoding="utf-8")
        return spec_path, evidence_path

    def test_dry_run_completes_without_mutating(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path, evidence_path = self._write_inputs(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                open_intake_pr.open_intake_pr(spec_path, evidence_path, push=False)
        output = buf.getvalue()
        self.assertIn("Dry run complete. Use --push to execute.", output)
        self.assertIn("[dry-run] would: git checkout -b intake/acme-pkg-1.0.0", output)

    def test_guard_evidence_failure_aborts_before_any_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            evidence_path = Path(tmp) / "evidence.json"
            spec_path.write_text(json.dumps({"owner": "acme", "name": "pkg"}), encoding="utf-8")
            evidence_path.write_text(json.dumps({"overall": "fail"}), encoding="utf-8")
            with (
                patch.object(open_intake_pr, "_stage_create_branch") as create_branch,
                patch.object(open_intake_pr, "_stage_copy_spec") as copy_spec,
                patch.object(open_intake_pr, "_stage_merge_into_index") as merge_into_index,
                patch.object(open_intake_pr, "_stage_lint_and_validate") as lint_and_validate,
                patch.object(open_intake_pr, "_update_intake_state") as update_intake_state,
                patch.object(open_intake_pr, "_stage_refresh_docs") as refresh_docs,
                patch.object(open_intake_pr, "_stage_commit_and_push") as commit_and_push,
                patch.object(open_intake_pr, "_stage_open_pr") as open_pr,
            ):
                with self.assertRaises(SystemExit):
                    open_intake_pr.open_intake_pr(spec_path, evidence_path, push=False)
            for stage in (
                create_branch, copy_spec, merge_into_index, lint_and_validate,
                update_intake_state, refresh_docs, commit_and_push, open_pr,
            ):
                stage.assert_not_called()

    def test_push_cleans_up_on_stage_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path, evidence_path = self._write_inputs(tmp)
            with (
                patch.object(open_intake_pr, "_prepare_push_branch", return_value="main"),
                patch.object(open_intake_pr, "_stage_create_branch"),
                patch.object(
                    open_intake_pr, "_stage_copy_spec", side_effect=RuntimeError("boom")
                ),
                patch.object(open_intake_pr, "_cleanup_intake_branch") as cleanup,
            ):
                with self.assertRaises(RuntimeError):
                    open_intake_pr.open_intake_pr(spec_path, evidence_path, push=True)
            expected_mutated_paths = [
                open_intake_pr.SPECS_DIR / "acme-pkg-1.0.0.json",
                open_intake_pr.INDEX_PATH,
                open_intake_pr.INTAKE_STATE_PATH,
                open_intake_pr.REPO_ROOT / "docs" / "intake-candidates.md",
                open_intake_pr.INTAKE_STATE_PATH.with_suffix(
                    open_intake_pr.INTAKE_STATE_PATH.suffix + ".bak"
                ),
            ]
            cleanup.assert_called_once_with(
                "intake/acme-pkg-1.0.0", "main", expected_mutated_paths
            )


class TestMain(unittest.TestCase):
    def test_main_parses_args_and_delegates(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "s.json"
            evidence_path = Path(tmp) / "e.json"
            spec_path.write_text("{}", encoding="utf-8")
            evidence_path.write_text("{}", encoding="utf-8")
            argv = ["open_intake_pr.py", "--spec", str(spec_path), "--evidence", str(evidence_path)]
            with (
                patch.object(open_intake_pr.sys, "argv", argv),
                patch.object(open_intake_pr, "open_intake_pr") as delegate,
            ):
                open_intake_pr.main()
            delegate.assert_called_once_with(spec_path, evidence_path, push=False, auto_merge=False)

    def test_main_push_flag_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "s.json"
            evidence_path = Path(tmp) / "e.json"
            spec_path.write_text("{}", encoding="utf-8")
            evidence_path.write_text("{}", encoding="utf-8")
            argv = [
                "open_intake_pr.py", "--spec", str(spec_path),
                "--evidence", str(evidence_path), "--push", "--auto-merge",
            ]
            with (
                patch.object(open_intake_pr.sys, "argv", argv),
                patch.object(open_intake_pr, "open_intake_pr") as delegate,
            ):
                open_intake_pr.main()
            delegate.assert_called_once_with(spec_path, evidence_path, push=True, auto_merge=True)

    def test_main_missing_spec_exits(self):
        argv = ["open_intake_pr.py", "--spec", "/nonexistent/s.json", "--evidence", "/nonexistent/e.json"]
        with patch.object(open_intake_pr.sys, "argv", argv):
            with self.assertRaises(SystemExit) as raised:
                open_intake_pr.main()
        self.assertEqual(raised.exception.code, 1)

    def test_main_missing_evidence_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "s.json"
            spec_path.write_text("{}", encoding="utf-8")
            argv = [
                "open_intake_pr.py", "--spec", str(spec_path),
                "--evidence", "/nonexistent/e.json",
            ]
            with patch.object(open_intake_pr.sys, "argv", argv):
                with self.assertRaises(SystemExit) as raised:
                    open_intake_pr.main()
            self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
