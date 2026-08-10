#!/usr/bin/env python3
"""Unit checks for scripts/scan_for_secrets.py (no network)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "scan_for_secrets.py"


def load_scan():
    spec = importlib.util.spec_from_file_location("scan_for_secrets", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class GitTrackedFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scan = load_scan()

    def test_parses_ls_files_output(self):
        result = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="a.txt\nb/c.txt\n", stderr=""
        )
        with patch.object(subprocess, "run", return_value=result) as run:
            files = self.scan.git_tracked_files()
        run.assert_called_once()
        self.assertEqual(
            files, [self.scan.REPO_ROOT / "a.txt", self.scan.REPO_ROOT / "b/c.txt"]
        )


class MatchesPrivateFilenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scan = load_scan()

    def test_matches_key_extension(self):
        self.assertEqual(self.scan.matches_private_filename(Path("id_rsa.key")), "*.key")

    def test_matches_pem_extension(self):
        self.assertEqual(self.scan.matches_private_filename(Path("cert.pem")), "*.pem")

    def test_matches_private_suffix(self):
        self.assertIsNotNone(self.scan.matches_private_filename(Path("signing-private")))

    def test_matches_private_key_infix(self):
        self.assertIsNotNone(
            self.scan.matches_private_filename(Path("official_private_key.bin"))
        )

    def test_no_match_for_normal_file(self):
        self.assertIsNone(self.scan.matches_private_filename(Path("official.pub")))


class ScanFileContentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scan = load_scan()

    def _write(self, tmp, text):
        path = Path(tmp) / "sample.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_pem_marker_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp, "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n"
            )
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("PEM", findings[0][1])

    def test_literal_private_b64_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b64 = "A" * 44
            path = self._write(tmp, f'priv_key = "{b64}"\n')
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("literal base64", findings[0][1])

    def test_public_key_b64_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            b64 = "A" * 44
            path = self._write(tmp, f'public_key_b64 = "{b64}"\n')
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(findings, [])

    def test_github_expression_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp, "NUMAN_REGISTRY_PRIVATE_KEY: ${{ secrets.NUMAN_REGISTRY_PRIVATE_KEY }}\n"
            )
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(findings, [])

    def test_hardcoded_secret_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp, "NUMAN_REGISTRY_PRIVATE_KEY: some-hardcoded-secret-value\n"
            )
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("literal value", findings[0][1])

    def test_allowlist_marker_skips_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "-----BEGIN PRIVATE KEY-----  # secretscan:allow\n")
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(findings, [])

    def test_binary_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bin.dat"
            path.write_bytes(b"\xff\xfe\x00\x01")
            findings = self.scan.scan_file_contents(path)
        self.assertEqual(findings, [])


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scan = load_scan()

    def test_main_returns_0_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.txt"
            clean.write_text("hello world\n", encoding="utf-8")
            with patch.object(self.scan, "git_tracked_files", return_value=[clean]):
                self.assertEqual(self.scan.main(), 0)

    def test_main_returns_1_on_filename_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "id_rsa.key"
            bad.write_text("x", encoding="utf-8")
            with patch.object(self.scan, "git_tracked_files", return_value=[bad]), patch.object(
                self.scan, "REPO_ROOT", Path(tmp)
            ):
                self.assertEqual(self.scan.main(), 1)

    def test_main_returns_1_on_content_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "leak.txt"
            bad.write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            with patch.object(self.scan, "git_tracked_files", return_value=[bad]), patch.object(
                self.scan, "REPO_ROOT", Path(tmp)
            ):
                self.assertEqual(self.scan.main(), 1)

    def test_main_skips_self(self):
        with patch.object(self.scan, "git_tracked_files", return_value=[self.scan.SELF_PATH]):
            self.assertEqual(self.scan.main(), 0)


if __name__ == "__main__":
    unittest.main()
