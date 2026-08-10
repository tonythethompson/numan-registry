#!/usr/bin/env python3.12
"""Regression checks for archive intake formats (no network)."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
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


class BuildArtifactEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_source_kind_rejected(self):
        with self.assertRaises(SystemExit) as raised:
            self.mod.build_artifact({"kind": "source"})
        self.assertEqual(raised.exception.code, 1)

    def test_unsupported_kind_rejected(self):
        with self.assertRaises(SystemExit) as raised:
            self.mod.build_artifact({"kind": "wat"})
        self.assertEqual(raised.exception.code, 1)

    def test_binary_requires_targets(self):
        with self.assertRaises(SystemExit) as raised:
            self.mod.build_artifact({"kind": "binary", "targets": {}})
        self.assertEqual(raised.exception.code, 1)

    def test_binary_target_missing_executable_path(self):
        with self.assertRaises(SystemExit) as raised:
            self.mod.build_artifact(
                {"kind": "binary", "targets": {"t": {"url": "https://x/y.tar.gz"}}}
            )
        self.assertEqual(raised.exception.code, 1)

    def test_binary_single_target_fast_path(self):
        payload = b"single target payload"
        targets = {"x86_64-unknown-linux-gnu": _binary_target("https://example.invalid/a.tar.gz", "nu_plugin")}
        with mock.patch.object(self.mod, "http_opener") as http_opener:
            http_opener.return_value.open.return_value = FakeResponse(payload)
            artifact = self.mod.build_artifact({"kind": "binary", "targets": targets})
        self.assertEqual(artifact["kind"], "binary")
        self.assertEqual(
            artifact["targets"]["x86_64-unknown-linux-gnu"]["sha256"],
            hashlib.sha256(payload).hexdigest(),
        )


class CheckModuleImportModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_no_activation_is_noop(self):
        self.mod.check_module_import_mode({"entry": "mod.nu"}, None)

    def test_non_nu_module_kind_is_noop(self):
        self.mod.check_module_import_mode({"entry": "mod.nu"}, {"kind": "other"})

    def test_mod_nu_with_module_import_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod.check_module_import_mode(
                {"entry": "mod.nu"}, {"kind": "nu-module", "import": "module"}
            )

    def test_mod_nu_with_all_import_ok(self):
        self.mod.check_module_import_mode(
            {"entry": "mod.nu"}, {"kind": "nu-module", "import": "all"}
        )

    def test_non_mod_nu_entry_ok(self):
        self.mod.check_module_import_mode(
            {"entry": "lib.nu"}, {"kind": "nu-module", "import": "module"}
        )


class CopySourceFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_absent_source_is_noop(self):
        version_entry = {}
        self.mod.copy_source_field({}, version_entry)
        self.assertNotIn("source", version_entry)

    def test_non_dict_source_exits(self):
        with self.assertRaises(SystemExit):
            self.mod.copy_source_field({"source": "nope"}, {})

    def test_missing_required_keys_exits(self):
        with self.assertRaises(SystemExit):
            self.mod.copy_source_field({"source": {"git": "https://x"}}, {})

    def test_copies_required_and_optional_fields(self):
        version_entry = {}
        self.mod.copy_source_field(
            {
                "source": {
                    "git": "https://x/y",
                    "rev": "a" * 40,
                    "cargo_name": "y",
                    "cargo_lock_sha256": "b" * 64,
                    "upstream": "https://upstream/y",
                }
            },
            version_entry,
        )
        self.assertEqual(
            version_entry["source"],
            {
                "git": "https://x/y",
                "rev": "a" * 40,
                "cargo_name": "y",
                "cargo_lock_sha256": "b" * 64,
                "upstream": "https://upstream/y",
            },
        )


class ValidateForkIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_non_fork_owner_with_upstream_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_fork_identity(
                {"owner": "someone", "source": {"upstream": "https://x"}}
            )

    def test_non_fork_owner_without_source_ok(self):
        self.mod.validate_fork_identity({"owner": "someone"})

    def test_maintained_fork_requires_source_object(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_fork_identity({"owner": "numan-maintained"})

    def test_maintained_fork_requires_upstream(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_fork_identity(
                {"owner": "numan-maintained", "source": {"git": "https://x"}}
            )

    def test_maintained_fork_upstream_must_differ_from_git(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_fork_identity(
                {
                    "owner": "numan-maintained",
                    "source": {"git": "https://x/y", "upstream": "https://x/y"},
                }
            )

    def test_maintained_fork_valid(self):
        self.mod.validate_fork_identity(
            {
                "owner": "numan-maintained",
                "source": {"git": "https://fork/y", "upstream": "https://upstream/y"},
            }
        )


class ValidateProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_absent_is_noop(self):
        self.mod.validate_provenance({})

    def test_unknown_provenance_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_provenance({"provenance": "bogus"})

    def test_commit_snapshot_requires_rev(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_provenance({"provenance": "commit-snapshot", "source": {}})

    def test_commit_snapshot_requires_full_sha(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_provenance(
                {"provenance": "commit-snapshot", "source": {"rev": "abc123"}}
            )

    def test_commit_snapshot_valid(self):
        self.mod.validate_provenance(
            {"provenance": "commit-snapshot", "source": {"rev": "a" * 40}}
        )


class ValidateSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _spec(self, **overrides):
        base = {
            "owner": "acme",
            "name": "pkg",
            "description": "d",
            "repo": "https://x",
            "type": "script",
            "tags": [],
            "version": "1.0.0",
            "nu_version": "0.100.0",
            "artifact": {"kind": "archive", "url": "https://x/y.tar.gz"},
        }
        base.update(overrides)
        return base

    def test_missing_required_field_rejected(self):
        spec = self._spec()
        del spec["repo"]
        with self.assertRaises(SystemExit):
            self.mod.validate_spec(spec)

    def test_invalid_type_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_spec(self._spec(type="bogus"))

    def test_plugin_without_evidence_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod.validate_spec(self._spec(type="plugin"))

    def test_plugin_without_evidence_allowed_provisional(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.mod.validate_spec(self._spec(type="plugin"), allow_provisional=True)
        self.assertIn("WARN", buf.getvalue())

    def test_plugin_with_valid_evidence_ok(self):
        self.mod.validate_spec(
            self._spec(type="plugin", verified_with=["0.100.0"])
        )

    def test_valid_non_activatable_spec_ok(self):
        self.mod.validate_spec(self._spec())


class MergeIntoIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _write_index(self, tmp, packages):
        path = Path(tmp) / "index.json"
        path.write_text(
            json.dumps({"schema_version": 1, "updated_at": "x", "packages": packages}),
            encoding="utf-8",
        )
        return path

    def _package_entry(self, version="1.0.0"):
        return {
            "id": {"owner": "acme", "name": "pkg"},
            "description": "d",
            "repo": "https://x",
            "type": "script",
            "tags": ["a"],
            "versions": [{"version": version, "nu_version": "0.100.0", "artifact": {}}],
        }

    def test_adds_new_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_index(tmp, [])
            index = self.mod.merge_into_index(path, self._package_entry(), force=False)
        self.assertEqual(len(index["packages"]), 1)

    def test_adds_new_version_to_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_index(tmp, [self._package_entry("1.0.0")])
            index = self.mod.merge_into_index(path, self._package_entry("2.0.0"), force=False)
        versions = [v["version"] for v in index["packages"][0]["versions"]]
        self.assertEqual(sorted(versions), ["1.0.0", "2.0.0"])

    def test_duplicate_version_without_force_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_index(tmp, [self._package_entry("1.0.0")])
            with self.assertRaises(SystemExit):
                self.mod.merge_into_index(path, self._package_entry("1.0.0"), force=False)

    def test_duplicate_version_with_force_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_index(tmp, [self._package_entry("1.0.0")])
            entry = self._package_entry("1.0.0")
            entry["description"] = "updated"
            index = self.mod.merge_into_index(path, entry, force=True)
        self.assertEqual(len(index["packages"][0]["versions"]), 1)
        self.assertEqual(index["packages"][0]["description"], "updated")


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _spec_dict(self):
        return {
            "owner": "acme",
            "name": "pkg",
            "description": "d",
            "repo": "https://x",
            "type": "script",
            "tags": [],
            "version": "1.0.0",
            "nu_version": "0.100.0",
            "artifact": {"kind": "archive", "url": "https://x/y.tar.gz"},
        }

    def test_no_write_prints_entry_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(self._spec_dict()), encoding="utf-8")
            argv = ["add-package.py", "--spec", str(spec_path)]
            buf = io.StringIO()
            with (
                mock.patch.object(self.mod.sys, "argv", argv),
                mock.patch.object(
                    self.mod, "build_artifact", return_value={"kind": "archive", "url": "x", "sha256": "y"}
                ),
                contextlib.redirect_stdout(buf),
            ):
                code = self.mod.main()
            self.assertEqual(code, 0)
            self.assertIn("package entry", buf.getvalue())

    def test_provisional_requires_deferral_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(self._spec_dict()), encoding="utf-8")
            argv = ["add-package.py", "--spec", str(spec_path), "--provisional"]
            with mock.patch.object(self.mod.sys, "argv", argv):
                with self.assertRaises(SystemExit) as raised:
                    self.mod.main()
            self.assertEqual(raised.exception.code, 1)

    def test_write_merges_into_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(self._spec_dict()), encoding="utf-8")
            index_path = Path(tmp) / "index.json"
            index_path.write_text(
                json.dumps({"schema_version": 1, "updated_at": "x", "packages": []}),
                encoding="utf-8",
            )
            argv = [
                "add-package.py", "--spec", str(spec_path),
                "--write", "--index", str(index_path),
            ]
            with (
                mock.patch.object(self.mod.sys, "argv", argv),
                mock.patch.object(
                    self.mod, "build_artifact", return_value={"kind": "archive", "url": "x", "sha256": "y"}
                ),
                mock.patch.object(self.mod, "validate_against_schema"),
            ):
                code = self.mod.main()
            self.assertEqual(code, 0)
            written = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(len(written["packages"]), 1)


if __name__ == "__main__":
    unittest.main()
