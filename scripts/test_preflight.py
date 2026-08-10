#!/usr/bin/env python3
"""Unit checks for scripts/preflight.py (no network)."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "preflight.py"


def load_preflight():
    spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class CheckOfficialPubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = load_preflight()

    def _write_pub(self, tmp, data):
        path = Path(tmp) / "official.pub"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_placeholder_key_id_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_pub(
                tmp, {"key_id": "official-placeholder", "public_key_b64": "PLACEHOLDER"}
            )
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(errors, [])
        self.assertIsNone(key_id)

    def test_missing_fields_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_pub(tmp, {"key_id": "x"})
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(len(errors), 1)
        self.assertIsNone(key_id)

    def test_invalid_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "official.pub"
            path.write_text("not json", encoding="utf-8")
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(len(errors), 1)
        self.assertIsNone(key_id)

    def test_invalid_base64_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_pub(
                tmp, {"key_id": "real-key", "public_key_b64": "not-valid-base64!!"}
            )
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(len(errors), 1)
        self.assertEqual(key_id, "real-key")

    def test_wrong_length_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            b64 = base64.b64encode(b"short").decode()
            path = self._write_pub(tmp, {"key_id": "real-key", "public_key_b64": b64})
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(len(errors), 1)
        self.assertIn("32 bytes", errors[0])

    def test_valid_key_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            b64 = base64.b64encode(b"0" * 32).decode()
            path = self._write_pub(tmp, {"key_id": "real-key", "public_key_b64": b64})
            with patch.object(self.preflight, "PUB_PATH", path):
                errors, key_id = self.preflight.check_official_pub()
        self.assertEqual(errors, [])
        self.assertEqual(key_id, "real-key")


class CheckKeyIdConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = load_preflight()

    def _write_sig(self, tmp, data):
        path = Path(tmp) / "index.json.sig"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_invalid_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json.sig"
            path.write_text("not json", encoding="utf-8")
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency(None)
        self.assertEqual(len(errors), 1)

    def test_both_placeholder_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_sig(
                tmp, {"key_id": "official-placeholder", "signature": "PLACEHOLDER"}
            )
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency(None)
        self.assertEqual(errors, [])

    def test_half_placeholder_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_sig(
                tmp, {"key_id": "official-placeholder", "signature": "abc123"}
            )
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency(None)
        self.assertEqual(len(errors), 1)
        self.assertIn("inconsistent placeholder", errors[0])

    def test_real_sig_but_pub_still_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_sig(tmp, {"key_id": "real-key", "signature": "abc123"})
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency(None)
        self.assertEqual(len(errors), 1)
        self.assertIn("never committed", errors[0])

    def test_key_id_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_sig(tmp, {"key_id": "sig-key", "signature": "abc123"})
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency("pub-key")
        self.assertEqual(len(errors), 1)
        self.assertIn("key_id mismatch", errors[0])

    def test_key_id_match_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_sig(tmp, {"key_id": "same-key", "signature": "abc123"})
            with patch.object(self.preflight, "SIG_PATH", path):
                errors = self.preflight.check_key_id_consistency("same-key")
        self.assertEqual(errors, [])


class CheckProductionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = load_preflight()

    def _write_workflow(self, tmp, text):
        path = Path(tmp) / "production.yml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_missing_file_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.yml"
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_missing_environment_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_workflow(tmp, "jobs:\n  build:\n    runs-on: ubuntu-latest\n")
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertTrue(any("must declare" in e for e in errors))

    def test_debug_trace_flag_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "environment: production\nrun: set -x\n"
            path = self._write_workflow(tmp, text)
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertTrue(any("debug/trace" in e for e in errors))

    def test_actions_step_debug_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "environment: production\nACTIONS_STEP_DEBUG: true\n"
            path = self._write_workflow(tmp, text)
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertTrue(any("debug/trace" in e for e in errors))

    def test_echo_secret_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "environment: production\nrun: echo ${{ secrets.NUMAN_REGISTRY_PRIVATE_KEY }}\n"
            path = self._write_workflow(tmp, text)
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertTrue(any("echoes the private key" in e for e in errors))

    def test_clean_workflow_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "environment: production\nrun: echo hello\n"
            path = self._write_workflow(tmp, text)
            with patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", path):
                errors = self.preflight.check_production_workflow()
        self.assertEqual(errors, [])


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = load_preflight()

    def test_main_returns_0_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "official.pub"
            pub.write_text(
                json.dumps({"key_id": "official-placeholder", "public_key_b64": "PLACEHOLDER"}),
                encoding="utf-8",
            )
            sig = Path(tmp) / "index.json.sig"
            sig.write_text(
                json.dumps({"key_id": "official-placeholder", "signature": "PLACEHOLDER"}),
                encoding="utf-8",
            )
            wf = Path(tmp) / "production.yml"
            wf.write_text("environment: production\n", encoding="utf-8")
            with patch.object(self.preflight, "PUB_PATH", pub), patch.object(
                self.preflight, "SIG_PATH", sig
            ), patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", wf):
                self.assertEqual(self.preflight.main(), 0)

    def test_main_returns_1_when_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "official.pub"
            pub.write_text("not json", encoding="utf-8")
            sig = Path(tmp) / "index.json.sig"
            sig.write_text(
                json.dumps({"key_id": "official-placeholder", "signature": "PLACEHOLDER"}),
                encoding="utf-8",
            )
            wf = Path(tmp) / "production.yml"
            wf.write_text("environment: production\n", encoding="utf-8")
            with patch.object(self.preflight, "PUB_PATH", pub), patch.object(
                self.preflight, "SIG_PATH", sig
            ), patch.object(self.preflight, "PRODUCTION_WORKFLOW_PATH", wf):
                self.assertEqual(self.preflight.main(), 1)


if __name__ == "__main__":
    unittest.main()
