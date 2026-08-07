#!/usr/bin/env python3.12
"""Unit checks for scripts/validate.py download/verify path (no network)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "validate.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))


def load_validate():
    spec = importlib.util.spec_from_file_location("validate_verify", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class DownloadAndVerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = load_validate()

    def test_missing_sha256_short_circuits(self):
        ok, msg = self.validate.download_and_verify("https://example.com/a.zip", "")
        self.assertFalse(ok)
        self.assertEqual(msg, "missing expected sha256")

    def test_rejects_file_scheme_without_urlopen(self):
        with mock.patch.object(self.validate.urllib.request, "urlopen") as urlopen:
            ok, msg = self.validate.download_and_verify(
                "file:///etc/passwd", "a" * 64
            )
        self.assertFalse(ok)
        self.assertIn("http(s)", msg)
        urlopen.assert_not_called()

    def test_rejects_custom_scheme_without_urlopen(self):
        with mock.patch.object(self.validate.urllib.request, "urlopen") as urlopen:
            ok, msg = self.validate.download_and_verify(
                "ftp://example.com/a.zip", "a" * 64
            )
        self.assertFalse(ok)
        self.assertIn("http(s)", msg)
        urlopen.assert_not_called()

    def test_https_url_reaches_urlopen(self):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b"payload"

        with mock.patch.object(
            self.validate.urllib.request,
            "urlopen",
            return_value=_Resp(),
        ) as urlopen:
            ok, msg = self.validate.download_and_verify(
                "https://example.com/a.zip",
                # sha256 of b"payload"
                "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5",
            )
        urlopen.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "ok")


if __name__ == "__main__":
    unittest.main()
