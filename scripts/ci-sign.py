#!/usr/bin/env python3
"""Sign a registry index with an Ed25519 private key.

This script is used by CI workflows. It accepts the private key as a base64
string or from a file. The private key is never logged or persisted beyond the
caller's responsibility.
"""

import argparse
import base64
import json
import sys


def sign_index(index_bytes, key_bytes):
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError(
            "The 'cryptography' package is required for signing. "
            "Install it with: pip install cryptography"
        ) from exc

    private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    signature = private_key.sign(index_bytes)
    return signature


def canonical_json(value):
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


def main():
    parser = argparse.ArgumentParser(description="Sign a Numan registry index")
    parser.add_argument("--index", required=True)
    parser.add_argument("--sig", required=True)
    parser.add_argument("--key-id", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--priv-b64", help="Base64-encoded Ed25519 private key (32 bytes)")
    group.add_argument("--priv-file", help="Path to a raw 32-byte Ed25519 private key file")
    args = parser.parse_args()

    if args.priv_b64:
        key_bytes = base64.b64decode(args.priv_b64)
    else:
        with open(args.priv_file, "rb") as f:
            key_bytes = f.read()

    if len(key_bytes) != 32:
        print(f"Private key must be 32 bytes, got {len(key_bytes)}", file=sys.stderr)
        return 1

    with open(args.index, "r", encoding="utf-8") as f:
        raw = f.read()
    parsed = json.loads(raw)
    canonical = canonical_json(parsed).encode("utf-8")

    signature = sign_index(canonical, key_bytes)
    envelope = {
        "key_id": args.key_id,
        "algorithm": "ed25519",
        "signature": base64.b64encode(signature).decode(),
    }

    with open(args.sig, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)
        f.write("\n")

    print(f"Signed {args.index} -> {args.sig} with key_id {args.key_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
