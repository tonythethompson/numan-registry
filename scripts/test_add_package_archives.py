#!/usr/bin/env python3.12
"""Regression checks for archive intake formats (no network)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "add-package.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

from archive_formats import (  # noqa: E402
    SUPPORTED_ARCHIVE_SUFFIXES,
    SUPPORTED_ARCHIVE_SUFFIXES_MARKDOWN,
)


def load_mod():
    """
    Load and return the add-package module from its script path.
    
    Returns:
        module: The dynamically loaded add-package module.
    """
    spec = importlib.util.spec_from_file_location("add_package_archives", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        """Return the response payload as bytes."""
        return self.data


class AddPackageArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def assert_downloaded_archive(self, suffix: str):
        """
        Verify that an archive suffix is accepted, downloaded, and hashed correctly.
        
        Parameters:
            suffix (str): Archive filename suffix to test.
        """
        payload = b"deterministic archive bytes"
        url = f"https://example.invalid/package{suffix}"
        with mock.patch.object(self.mod, "http_opener") as http_opener:
            http_opener.return_value.open.return_value = FakeResponse(payload)
            artifact = self.mod.build_artifact({"kind": "archive", "url": url})
        self.assertEqual(artifact["url"], url)
        self.assertEqual(artifact["sha256"], hashlib.sha256(payload).hexdigest())
        http_opener.assert_called_once()

    def test_accepts_tar_xz_and_hashes_download(self):
        self.assert_downloaded_archive(".tar.xz")

    def test_accepts_txz_and_hashes_download(self):
        self.assert_downloaded_archive(".txz")

    def test_rejects_unknown_suffix_before_download(self):
        with (
            mock.patch.object(self.mod, "http_opener") as http_opener,
            self.assertRaises(SystemExit) as raised,
        ):
            self.mod.build_artifact(
                {"kind": "archive", "url": "https://example.invalid/package.rar"}
            )
        self.assertEqual(raised.exception.code, 1)
        http_opener.assert_not_called()

    def test_rejects_non_http_scheme_before_download(self):
        with (
            mock.patch.object(self.mod, "http_opener") as http_opener,
            self.assertRaises(SystemExit) as raised,
        ):
            self.mod.build_artifact(
                {"kind": "archive", "url": "file:///etc/passwd.tar.gz"}
            )
        self.assertEqual(raised.exception.code, 1)
        http_opener.assert_not_called()

    def test_generated_intake_doc_uses_shared_archive_suffixes(self):
        self.assertEqual(
            self.mod.SUPPORTED_ARCHIVE_SUFFIXES,
            SUPPORTED_ARCHIVE_SUFFIXES,
        )
        intake_doc = (SCRIPT.parent.parent / "docs" / "intake-candidates.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"artifact must be {SUPPORTED_ARCHIVE_SUFFIXES_MARKDOWN};",
            intake_doc,
        )


if __name__ == "__main__":
    unittest.main()
