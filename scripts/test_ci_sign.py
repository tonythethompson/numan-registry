#!/usr/bin/env python3
"""Unit checks for scripts/ci-sign.py (real crypto round trip, no network)."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPT = Path(__file__).resolve().parent / "ci-sign.py"


def load_ci_sign():
    spec = importlib.util.spec_from_file_location("ci_sign", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CI_SIGN = load_ci_sign()



class CanonicalJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci_sign = CI_SIGN

    def test_sorts_dict_keys(self):
        self.assertEqual(self.ci_sign.canonical_json({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_list_preserves_order(self):
        self.assertEqual(self.ci_sign.canonical_json([3, 1, 2]), "[3,1,2]")

    def test_bool_lowercase(self):
        self.assertEqual(self.ci_sign.canonical_json(True), "true")
        self.assertEqual(self.ci_sign.canonical_json(False), "false")

    def test_none_is_null(self):
        self.assertEqual(self.ci_sign.canonical_json(None), "null")

    def test_nested_structures_deterministic(self):
        value = {"z": [1, {"y": 2, "x": 3}], "a": "hi"}
        first = self.ci_sign.canonical_json(value)
        second = self.ci_sign.canonical_json(value)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith('{"a":"hi"'))


class SignIndexRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci_sign = CI_SIGN

    def test_sign_then_verify(self):
        private_key = Ed25519PrivateKey.generate()
        key_bytes = private_key.private_bytes_raw()
        public_key = private_key.public_key()
        data = b'{"packages":[]}'
        signature = self.ci_sign.sign_index(data, key_bytes)
        public_key.verify(signature, data)

    def test_verify_fails_on_tampered_data(self):
        private_key = Ed25519PrivateKey.generate()
        key_bytes = private_key.private_bytes_raw()
        public_key = private_key.public_key()
        signature = self.ci_sign.sign_index(b"original", key_bytes)
        with self.assertRaises(InvalidSignature):
            public_key.verify(signature, b"tampered")


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci_sign = CI_SIGN

    def test_main_writes_valid_signature(self):
        private_key = Ed25519PrivateKey.generate()
        key_bytes = private_key.private_bytes_raw()
        public_key = private_key.public_key()
        priv_b64 = base64.b64encode(key_bytes).decode()

        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            sig_path = Path(tmp) / "index.json.sig"
            index_path.write_text(json.dumps({"b": 1, "a": 2}), encoding="utf-8")

            argv = [
                "ci-sign.py",
                "--index",
                str(index_path),
                "--sig",
                str(sig_path),
                "--key-id",
                "test-key",
                "--priv-b64",
                priv_b64,
            ]
            with patch.object(sys, "argv", argv):
                rc = self.ci_sign.main()
            self.assertEqual(rc, 0)

            envelope = json.loads(sig_path.read_text(encoding="utf-8"))
            self.assertEqual(envelope["key_id"], "test-key")
            self.assertEqual(envelope["algorithm"], "ed25519")
            signature = base64.b64decode(envelope["signature"])
            canonical = self.ci_sign.canonical_json({"a": 2, "b": 1}).encode("utf-8")
            public_key.verify(signature, canonical)

    def test_main_rejects_wrong_length_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            sig_path = Path(tmp) / "index.json.sig"
            index_path.write_text("{}", encoding="utf-8")
            short_b64 = base64.b64encode(b"short").decode()
            argv = [
                "ci-sign.py",
                "--index",
                str(index_path),
                "--sig",
                str(sig_path),
                "--key-id",
                "test-key",
                "--priv-b64",
                short_b64,
            ]
            with patch.object(sys, "argv", argv):
                rc = self.ci_sign.main()
            self.assertEqual(rc, 1)
            self.assertFalse(sig_path.exists())

    def test_main_reads_key_from_file(self):
        private_key = Ed25519PrivateKey.generate()
        key_bytes = private_key.private_bytes_raw()

        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "index.json"
            sig_path = Path(tmp) / "index.json.sig"
            key_path = Path(tmp) / "priv.key"
            index_path.write_text("{}", encoding="utf-8")
            key_path.write_bytes(key_bytes)

            argv = [
                "ci-sign.py",
                "--index",
                str(index_path),
                "--sig",
                str(sig_path),
                "--key-id",
                "file-key",
                "--priv-file",
                str(key_path),
            ]
            with patch.object(sys, "argv", argv):
                rc = self.ci_sign.main()
            self.assertEqual(rc, 0)
            envelope = json.loads(sig_path.read_text(encoding="utf-8"))
            self.assertEqual(envelope["key_id"], "file-key")


if __name__ == "__main__":
    unittest.main()
