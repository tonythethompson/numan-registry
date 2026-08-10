#!/usr/bin/env python3.12
"""Unit checks for scripts/validate.py download/verify path (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "validate.py"
ROOT = SCRIPT.parent.parent
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))


def load_validate():
    spec = importlib.util.spec_from_file_location("validate_verify", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


MINIMAL_INDEX = {
    "schema_version": 1,
    "updated_at": "2026-07-29T00:00:00Z",
    "packages": [],
}


class DownloadAndVerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = load_validate()

    def test_missing_sha256_short_circuits(self):
        ok, msg = self.validate.download_and_verify("https://example.com/a.zip", "")
        self.assertFalse(ok)
        self.assertEqual(msg, "missing expected sha256")

    def test_rejects_file_scheme_without_urlopen(self):
        with mock.patch.object(self.validate, "http_opener") as http_opener:
            ok, msg = self.validate.download_and_verify(
                "file:///etc/passwd", "a" * 64
            )
        self.assertFalse(ok)
        self.assertIn("http(s)", msg)
        http_opener.assert_not_called()

    def test_rejects_custom_scheme_without_urlopen(self):
        with mock.patch.object(self.validate, "http_opener") as http_opener:
            ok, msg = self.validate.download_and_verify(
                "ftp://example.com/a.zip", "a" * 64
            )
        self.assertFalse(ok)
        self.assertIn("http(s)", msg)
        http_opener.assert_not_called()

    def test_https_url_reaches_urlopen(self):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b"payload"

        with mock.patch.object(self.validate, "http_opener") as http_opener:
            http_opener.return_value.open.return_value = _Resp()
            ok, msg = self.validate.download_and_verify(
                "https://example.com/a.zip",
                # sha256 of b"payload"
                "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5",
            )
        http_opener.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "ok")


class ValidateMainHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = load_validate()

    def test_load_index_missing_file_returns_none(self):
        buf = StringIO()
        with redirect_stdout(buf):
            loaded = self.validate._load_index("/nonexistent/index.json")
        self.assertIsNone(loaded)
        self.assertIn("FAIL: could not load index", buf.getvalue())

    def test_validate_schema_step_records_failure(self):
        errors: list[str] = []
        with mock.patch.object(
            self.validate,
            "validate_schema",
            side_effect=RuntimeError("boom"),
        ):
            buf = StringIO()
            with redirect_stdout(buf):
                ok = self.validate._validate_schema_step({}, "schema.json", errors)
        self.assertFalse(ok)
        self.assertEqual(errors, ["schema"])
        self.assertIn("FAIL: schema validation: boom", buf.getvalue())

    def test_validate_lifecycle_step_appends_errors_and_provisional_ok(self):
        errors: list[str] = []
        with mock.patch.object(
            self.validate,
            "lifecycle_evidence_errors",
            return_value=["acme/pkg@1.0.0: bad evidence"],
        ):
            buf = StringIO()
            with redirect_stdout(buf):
                self.validate._validate_lifecycle_step(
                    MINIMAL_INDEX,
                    allow_missing=True,
                    errors=errors,
                )
        self.assertEqual(len(errors), 1)
        self.assertIn("lifecycle_evidence:", errors[0])
        self.assertNotIn("provisional lifecycle evidence", buf.getvalue())

        errors = []
        with mock.patch.object(
            self.validate,
            "lifecycle_evidence_errors",
            return_value=[],
        ):
            buf = StringIO()
            with redirect_stdout(buf):
                self.validate._validate_lifecycle_step(
                    MINIMAL_INDEX,
                    allow_missing=True,
                    errors=errors,
                )
        self.assertEqual(errors, [])
        self.assertIn(
            "OK: provisional lifecycle evidence is allowed for staging",
            buf.getvalue(),
        )

    def test_validate_schema_version_rejects_non_one(self):
        errors: list[str] = []
        buf = StringIO()
        with redirect_stdout(buf):
            self.validate._validate_schema_version({"schema_version": 2}, errors)
        self.assertEqual(errors, ["schema_version"])
        self.assertIn("schema_version must be 1", buf.getvalue())

    def test_verify_one_artifact_fixture_strict_vs_lenient(self):
        errors: list[str] = []
        buf = StringIO()
        with redirect_stdout(buf):
            self.validate._verify_one_artifact(
                "acme/pkg@1.0.0",
                "https://example.com/pkg.zip",
                "a" * 64,
                strict_artifacts=False,
                errors=errors,
            )
        self.assertEqual(errors, [])
        self.assertIn("fixture URL skipped", buf.getvalue())

        errors = []
        buf = StringIO()
        with redirect_stdout(buf):
            self.validate._verify_one_artifact(
                "acme/pkg@1.0.0",
                "https://example.com/pkg.zip",
                "a" * 64,
                strict_artifacts=True,
                errors=errors,
            )
        self.assertEqual(errors, ["artifact:acme/pkg@1.0.0"])

    def test_validate_signature_step_skips_when_requested(self):
        args = self.validate._parse_args(["--skip-signature"])
        errors: list[str] = []
        buf = StringIO()
        with redirect_stdout(buf):
            self.validate._validate_signature_step(args, b"canonical", errors)
        self.assertEqual(errors, [])
        self.assertIn("signature verification skipped", buf.getvalue())

    def test_main_schema_failure_skips_lifecycle_traversal(self):
        malformed = {
            "schema_version": 1,
            "updated_at": "2026-07-29T00:00:00Z",
            "packages": [None],
        }
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            index_path.write_text(json.dumps(malformed), encoding="utf-8")
            argv = [
                "--index",
                str(index_path),
                "--schema",
                str(ROOT / "schemas" / "index-v1.json"),
                "--skip-signature",
                "--skip-artifacts",
            ]
            with mock.patch.object(
                self.validate,
                "lifecycle_evidence_errors",
            ) as lifecycle_errors:
                code = self.validate.main(argv)
            lifecycle_errors.assert_not_called()
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
