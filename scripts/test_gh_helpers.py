#!/usr/bin/env python3.12
"""Unit checks for scripts/gh_helpers.py (no network, no gh binary)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "gh_helpers.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

import gh_helpers  # noqa: E402
from gh_helpers import gh_json, gh_text  # noqa: E402


def _result(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh", "api"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class GhJsonTests(unittest.TestCase):
    def test_parses_json_stdout(self):
        with mock.patch.object(
            subprocess, "run", return_value=_result(0, stdout='{"key": "value"}')
        ) as run:
            self.assertEqual(gh_json(["api", "user"]), {"key": "value"})
        run.assert_called_once()

    def test_returns_none_when_gh_missing(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError) as run:
            self.assertIsNone(gh_json(["api", "user"]))
        run.assert_called_once()

    def test_returns_none_on_nonzero_exit(self):
        with mock.patch.object(
            subprocess, "run", return_value=_result(1, stdout="boom", stderr="err")
        ):
            self.assertIsNone(gh_json(["api", "user"]))

    def test_returns_none_on_empty_stdout(self):
        with mock.patch.object(subprocess, "run", return_value=_result(0, stdout="")):
            self.assertIsNone(gh_json(["api", "user"]))

    def test_returns_none_on_invalid_json(self):
        with mock.patch.object(subprocess, "run", return_value=_result(0, stdout="not json")):
            self.assertIsNone(gh_json(["api", "user"]))

    def test_uses_repo_root_as_cwd(self):
        with mock.patch.object(
            subprocess, "run", return_value=_result(0, stdout="{}")
        ) as run:
            gh_json(["api", "user"])
        cwd = run.call_args.kwargs.get("cwd")
        self.assertEqual(cwd, gh_helpers.REPO_ROOT)


class GhTextTests(unittest.TestCase):
    def test_strips_stdout(self):
        with mock.patch.object(
            subprocess, "run", return_value=_result(0, stdout="  some-text  ")
        ) as run:
            self.assertEqual(gh_text(["api", "user", "--jq", ".login"]), "some-text")
        run.assert_called_once()

    def test_returns_none_when_gh_missing(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(gh_text(["api", "user"]))

    def test_returns_none_on_nonzero_exit(self):
        with mock.patch.object(subprocess, "run", return_value=_result(1, stdout="x")):
            self.assertIsNone(gh_text(["api", "user"]))

    def test_returns_none_on_blank_stdout(self):
        with mock.patch.object(subprocess, "run", return_value=_result(0, stdout="   ")):
            self.assertIsNone(gh_text(["api", "user"]))


if __name__ == "__main__":
    unittest.main()
