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


def load_mod():
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
        return self.data


class AddPackageArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def assert_downloaded_archive(self, suffix: str):
        payload = b"deterministic archive bytes"
        url = f"https://example.invalid/package{suffix}"
        with mock.patch.object(
            self.mod.urllib.request,
            "urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            artifact = self.mod.build_artifact({"kind": "archive", "url": url})
        self.assertEqual(artifact["url"], url)
        self.assertEqual(artifact["sha256"], hashlib.sha256(payload).hexdigest())
        urlopen.assert_called_once()

    def test_accepts_tar_xz_and_hashes_download(self):
        self.assert_downloaded_archive(".tar.xz")

    def test_accepts_txz_and_hashes_download(self):
        self.assert_downloaded_archive(".txz")

    def test_rejects_unknown_suffix_before_download(self):
        with (
            mock.patch.object(self.mod.urllib.request, "urlopen") as urlopen,
            self.assertRaises(SystemExit) as raised,
        ):
            self.mod.build_artifact(
                {"kind": "archive", "url": "https://example.invalid/package.rar"}
            )
        self.assertEqual(raised.exception.code, 1)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
