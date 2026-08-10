#!/usr/bin/env python3
"""Unit checks for scripts/build-mirror-zip.py (no network)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "build-mirror-zip.py"


def load_build_mirror_zip():
    spec = importlib.util.spec_from_file_location("build_mirror_zip", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class IgnoreVcsMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_filters_vcs_dirs_only(self):
        result = self.bmz.ignore_vcs_metadata(
            "ignored", ["a.txt", ".git", ".hg", ".svn", "sub"]
        )
        self.assertEqual(result, {".git", ".hg", ".svn"})


class AssertMirrorPathsSafeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_allows_regular_file_and_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("hi", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("bye", encoding="utf-8")
            self.bmz.assert_mirror_paths_safe(root, ["a.txt", "sub"])

    def test_rejects_top_level_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real.txt"
            target.write_text("hi", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(SystemExit):
                self.bmz.assert_mirror_paths_safe(root, ["link.txt"])

    def test_rejects_nested_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "sub"
            sub.mkdir()
            target = root / "real.txt"
            target.write_text("hi", encoding="utf-8")
            (sub / "link.txt").symlink_to(target)
            with self.assertRaises(SystemExit):
                self.bmz.assert_mirror_paths_safe(root, ["sub"])

    def test_rejects_path_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "clone"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("hi", encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.bmz.assert_mirror_paths_safe(root, ["../outside.txt"])

    def test_rejects_missing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SystemExit):
                self.bmz.assert_mirror_paths_safe(root, ["missing"])


class CopyPathsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_copies_file_and_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.txt").write_text("hi", encoding="utf-8")
            sub = src / "sub"
            sub.mkdir()
            (sub / "b.txt").write_text("bye", encoding="utf-8")

            dest = Path(tmp) / "dest"
            self.bmz.copy_paths(src, ["a.txt", "sub"], dest)

            self.assertEqual((dest / "a.txt").read_text(encoding="utf-8"), "hi")
            self.assertEqual((dest / "sub" / "b.txt").read_text(encoding="utf-8"), "bye")

    def test_missing_path_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            dest = Path(tmp) / "dest"
            with self.assertRaises(SystemExit):
                self.bmz.copy_paths(src, ["missing"], dest)


class MakeZipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_creates_zip_with_expected_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "pkg-1.0.0"
            source.mkdir()
            (source / "a.txt").write_text("hello", encoding="utf-8")
            sub = source / "sub"
            sub.mkdir()
            (sub / "b.txt").write_text("world", encoding="utf-8")
            (source / ".git").mkdir()
            (source / ".git" / "config").write_text("x", encoding="utf-8")

            output = Path(tmp) / "out.zip"
            digest = self.bmz.make_zip(source, output)

            with zipfile.ZipFile(output) as zf:
                names = sorted(zf.namelist())
            self.assertEqual(names, ["pkg-1.0.0/a.txt", "pkg-1.0.0/sub/b.txt"])
            self.assertEqual(len(digest), 64)

    def test_zip_bytes_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "pkg"
            source.mkdir()
            (source / "a.txt").write_text("stable", encoding="utf-8")

            out1 = Path(tmp) / "out1.zip"
            out2 = Path(tmp) / "out2.zip"
            digest1 = self.bmz.make_zip(source, out1)
            digest2 = self.bmz.make_zip(source, out2)

            self.assertEqual(digest1, digest2)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_fixed_metadata_on_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "pkg"
            source.mkdir()
            (source / "a.txt").write_text("x", encoding="utf-8")
            output = Path(tmp) / "out.zip"
            self.bmz.make_zip(source, output)
            with zipfile.ZipFile(output) as zf:
                info = zf.getinfo("pkg/a.txt")
            self.assertEqual(info.date_time, self.bmz.FIXED_ZIP_DT)
            self.assertEqual(info.create_system, self.bmz.FIXED_ZIP_CREATE_SYSTEM)


class CloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_clone_at_ref_invokes_git_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
                result = self.bmz.clone_at_ref(
                    "https://example.com/repo.git", "v1.0.0", workdir
                )
        self.assertEqual(result, workdir / "src")
        run.assert_called_once()
        cmd = run.call_args.args[0]
        self.assertIn("clone", cmd)
        self.assertIn("v1.0.0", cmd)

    def test_clone_at_ref_removes_existing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            existing = workdir / "src"
            existing.mkdir()
            (existing / "stale.txt").write_text("x", encoding="utf-8")
            with patch.object(subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
                self.bmz.clone_at_ref("https://example.com/repo.git", "v1.0.0", workdir)
        self.assertFalse((existing / "stale.txt").exists())

    def test_clone_at_commit_invokes_git_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
                result = self.bmz.clone_at_commit(
                    "https://example.com/repo.git", "abc123", workdir
                )
        self.assertEqual(result, workdir / "src")
        self.assertEqual(run.call_count, 4)


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmz = load_build_mirror_zip()

    def test_main_end_to_end_with_mocked_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "work"
            output = Path(tmp) / "out.zip"

            def fake_run(cmd, cwd=None, check=True):
                if cmd[:2] == ["git", "clone"]:
                    clone_dir = Path(cmd[-1])
                    pkg_dir = clone_dir / "pkgs" / "demo"
                    pkg_dir.mkdir(parents=True, exist_ok=True)
                    (pkg_dir / "plugin.nu").write_text("echo hi", encoding="utf-8")
                return subprocess.CompletedProcess(args=cmd, returncode=0)

            argv = [
                "build-mirror-zip.py",
                "--repo",
                "https://example.com/repo.git",
                "--ref",
                "v1.0.0",
                "--paths",
                "pkgs/demo",
                "--archive-root",
                "demo-1.0.0",
                "--output",
                str(output),
                "--workdir",
                str(workdir),
            ]
            with patch.object(subprocess, "run", side_effect=fake_run), patch.object(
                sys, "argv", argv
            ):
                rc = self.bmz.main()

            self.assertEqual(rc, 0)
            self.assertTrue(output.exists())
            with zipfile.ZipFile(output) as zf:
                names = sorted(zf.namelist())
            self.assertEqual(names, ["demo-1.0.0/pkgs/demo/plugin.nu"])

    def test_main_rejects_both_ref_and_commit(self):
        argv = [
            "build-mirror-zip.py",
            "--repo",
            "https://example.com/repo.git",
            "--ref",
            "v1.0.0",
            "--commit",
            "abc123",
            "--paths",
            "pkgs/demo",
            "--archive-root",
            "demo-1.0.0",
            "--output",
            "/tmp/whatever.zip",
        ]
        with patch.object(sys, "argv", argv):
            rc = self.bmz.main()
        self.assertEqual(rc, 1)

    def test_main_rejects_missing_ref_and_commit(self):
        argv = [
            "build-mirror-zip.py",
            "--repo",
            "https://example.com/repo.git",
            "--paths",
            "pkgs/demo",
            "--archive-root",
            "demo-1.0.0",
            "--output",
            "/tmp/whatever.zip",
        ]
        with patch.object(sys, "argv", argv):
            rc = self.bmz.main()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
