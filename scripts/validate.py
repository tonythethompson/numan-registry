#!/usr/bin/env python3
"""Validate the Numan registry index and its detached signature.

This script intentionally mirrors the verification logic in the Numan client
(src/core/official_registry.rs) so that CI and the client agree on:

- canonical JSON serialization (sorted object keys, compact, no whitespace)
- schema_version presence
- detached Ed25519 signature over the canonical bytes
- SHA-256 of the canonical bytes

It also optionally downloads and verifies artifact digests for non-fixture URLs.
"""

import argparse
import base64
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def canonical_json(value):
    """Return the canonical JSON string for a parsed JSON value."""
    if isinstance(value, dict):
        items = sorted((canonical_json(k), canonical_json(v)) for k, v in value.items())
        return "{" + ",".join(f"{k}:{v}" for k, v in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return json.dumps(value, separators=(",", ":"))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_pub_key(path):
    pub = load_json(path)
    key_id = pub.get("key_id")
    public_key_b64 = pub.get("public_key_b64")
    if not key_id or not public_key_b64:
        raise ValueError(f"Public key file {path} must contain key_id and public_key_b64")
    if public_key_b64 == "PLACEHOLDER":
        raise ValueError(f"Public key in {path} is still a placeholder")
    return key_id, public_key_b64


def load_sig(path):
    sig = load_json(path)
    key_id = sig.get("key_id")
    algorithm = sig.get("algorithm")
    signature_b64 = sig.get("signature")
    if not key_id or not algorithm or not signature_b64:
        raise ValueError(f"Signature file {path} must contain key_id, algorithm, and signature")
    if algorithm != "ed25519":
        raise ValueError(f"Unsupported signature algorithm: {algorithm}")
    if signature_b64 == "PLACEHOLDER":
        raise ValueError(f"Signature in {path} is still a placeholder")
    return key_id, signature_b64


def verify_ed25519(public_key_b64, signature_b64, data_bytes):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError(
            "The 'cryptography' package is required for signature verification. "
            "Install it with: pip install cryptography"
        ) from exc

    public_key_bytes = base64.b64decode(public_key_b64)
    if len(public_key_bytes) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(public_key_bytes)}")
    signature_bytes = base64.b64decode(signature_b64)
    if len(signature_bytes) != 64:
        raise ValueError(f"Ed25519 signature must be 64 bytes, got {len(signature_bytes)}")

    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    public_key.verify(signature_bytes, data_bytes)


def validate_schema(index, schema_path):
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError(
            "The 'jsonschema' package is required for schema validation. "
            "Install it with: pip install jsonschema"
        ) from exc

    schema = load_json(schema_path)
    jsonschema.validate(index, schema)


def collect_artifact_urls(index):
    """Yield (package_id, version, url, expected_sha256) for artifact URLs."""
    for package in index.get("packages", []):
        pkg_id = f"{package['id']['owner']}/{package['id']['name']}"
        for version_entry in package.get("versions", []):
            version = version_entry["version"]
            artifact = version_entry.get("artifact", {})
            if artifact.get("kind") == "binary":
                for target, target_artifact in artifact.get("targets", {}).items():
                    url = target_artifact.get("url", "")
                    sha256 = target_artifact.get("sha256", "")
                    yield f"{pkg_id}@{version} ({target})", url, sha256
            else:
                url = artifact.get("url", "")
                sha256 = artifact.get("sha256", "")
                yield f"{pkg_id}@{version}", url, sha256


def is_fixture_url(url):
    """Treat example.com / localhost URLs as fixture data that is not downloadable."""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    return hostname in ("example.com", "localhost", "127.0.0.1", "::1") or hostname.endswith(".test")


def download_and_verify(url, expected_sha256):
    if not expected_sha256:
        return False, "missing expected sha256"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:
        return False, f"download failed: {exc}"
    actual = hashlib.sha256(data).hexdigest()
    if actual.lower() != expected_sha256.lower():
        return False, f"sha256 mismatch: expected {expected_sha256}, got {actual}"
    return True, "ok"


def main():
    parser = argparse.ArgumentParser(description="Validate the Numan registry index")
    parser.add_argument("--index", default="registry/index.json")
    parser.add_argument("--sig", default="registry/index.json.sig")
    parser.add_argument("--pub", default="keys/official.pub")
    parser.add_argument("--schema", default="schemas/index-v1.json")
    parser.add_argument("--skip-artifacts", action="store_true", help="Skip artifact digest verification")
    parser.add_argument("--strict-artifacts", action="store_true", help="Fail on fixture URLs that cannot be downloaded")
    args = parser.parse_args()

    errors = []

    # Load index
    try:
        index = load_json(args.index)
    except Exception as exc:
        print(f"FAIL: could not load index: {exc}")
        return 1

    # Schema validation
    try:
        validate_schema(index, args.schema)
        print("OK: schema validation passed")
    except Exception as exc:
        print(f"FAIL: schema validation: {exc}")
        errors.append("schema")

    # schema_version check
    if index.get("schema_version") != 1:
        print(f"FAIL: schema_version must be 1, got {index.get('schema_version')}")
        errors.append("schema_version")

    # Canonical JSON and SHA-256
    with open(args.index, "r", encoding="utf-8") as f:
        raw_index = f.read()
    parsed_index = json.loads(raw_index)
    canonical = canonical_json(parsed_index).encode("utf-8")
    index_sha256 = hashlib.sha256(canonical).hexdigest()
    print(f"OK: canonical index sha256 = {index_sha256}")

    # Signature validation
    try:
        expected_key_id, public_key_b64 = load_pub_key(args.pub)
        sig_key_id, signature_b64 = load_sig(args.sig)
        if sig_key_id != expected_key_id:
            raise ValueError(
                f"Signature key_id '{sig_key_id}' does not match public key '{expected_key_id}'"
            )
        verify_ed25519(public_key_b64, signature_b64, canonical)
        print(f"OK: Ed25519 signature verified with key_id '{sig_key_id}'")
    except Exception as exc:
        print(f"FAIL: signature verification: {exc}")
        errors.append("signature")

    # Artifact digest verification
    if not args.skip_artifacts:
        for label, url, expected_sha256 in collect_artifact_urls(index):
            if not url:
                continue
            if is_fixture_url(url):
                msg = "fixture URL skipped"
                if args.strict_artifacts:
                    print(f"FAIL: {label} artifact: {msg}")
                    errors.append(f"artifact:{label}")
                else:
                    print(f"OK: {label} artifact: {msg}")
                continue
            ok, msg = download_and_verify(url, expected_sha256)
            if ok:
                print(f"OK: {label} artifact digest verified")
            else:
                print(f"FAIL: {label} artifact: {msg}")
                errors.append(f"artifact:{label}")

    if errors:
        print(f"\nValidation failed with {len(errors)} error(s)")
        return 1

    print("\nValidation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
