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

    def read(self, nbytes=-1):
        """Return the response payload as bytes, optionally capped to *nbytes*."""
        if nbytes < 0:
            chunk = self.data
            self.data = b""
            return chunk
        if nbytes == 0:
            return b""
        chunk = self.data[:nbytes]
        self.data = self.data[nbytes:]
        return chunk


def _binary_target(url: str, executable_path: str) -> dict[str, str]:
    return {"url": url, "executable_path": executable_path}


class AddPackageArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _mock_opener_for_payloads(self, payloads: dict[str, bytes]):
        def open_side_effect(req, timeout=60):
            return FakeResponse(payloads[req.full_url])

        opener = mock.Mock()
        opener.open.side_effect = open_side_effect
        return opener

    def test_binary_parallel_hashes_all_targets(self):
        payloads = {
            "https://example.invalid/linux.tar.gz": b"linux artifact",
            "https://example.invalid/windows.zip": b"windows artifact",
            "https://example.invalid/macos.tar.gz": b"macos artifact",
        }
        targets = {
            "x86_64-unknown-linux-gnu": _binary_target(
                "https://example.invalid/linux.tar.gz", "nu_plugin"
            ),
            "x86_64-pc-windows-msvc": _binary_target(
                "https://example.invalid/windows.zip", "nu_plugin.exe"
            ),
            "x86_64-apple-darwin": _binary_target(
                "https://example.invalid/macos.tar.gz", "nu_plugin"
            ),
        }
        with mock.patch.object(
            self.mod, "http_opener", return_value=self._mock_opener_for_payloads(payloads)
        ) as http_opener:
            artifact = self.mod.build_artifact({"kind": "binary", "targets": targets})

        self.assertEqual(artifact["kind"], "binary")
        self.assertEqual(len(artifact["targets"]), len(targets))
        for triple, target in targets.items():
            built = artifact["targets"][triple]
            self.assertEqual(built["url"], target["url"])
            self.assertEqual(built["executable_path"], target["executable_path"])
            self.assertEqual(
                built["sha256"],
                hashlib.sha256(payloads[target["url"]]).hexdigest(),
            )
        self.assertEqual(http_opener.return_value.open.call_count, len(targets))

    def test_binary_parallel_preserves_input_target_order(self):
        payloads = {
            "https://example.invalid/linux.tar.gz": b"linux artifact",
            "https://example.invalid/windows.zip": b"windows artifact",
            "https://example.invalid/macos.tar.gz": b"macos artifact",
        }
        targets = {
            "x86_64-unknown-linux-gnu": _binary_target(
                "https://example.invalid/linux.tar.gz", "nu_plugin"
            ),
            "x86_64-pc-windows-msvc": _binary_target(
                "https://example.invalid/windows.zip", "nu_plugin.exe"
            ),
            "x86_64-apple-darwin": _binary_target(
                "https://example.invalid/macos.tar.gz", "nu_plugin"
            ),
        }

        def completion_order_reversed(futures):
            return reversed(list(futures))

        with (
            mock.patch.object(
                self.mod,
                "http_opener",
                return_value=self._mock_opener_for_payloads(payloads),
            ),
            mock.patch.object(self.mod, "as_completed", side_effect=completion_order_reversed),
        ):
            artifact = self.mod.build_artifact({"kind": "binary", "targets": targets})

        self.assertEqual(list(artifact["targets"]), list(targets))

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
