#!/usr/bin/env python3
"""Preflight checks for the Numan official registry's key/workflow safety.

Runs entirely on repository state (no network, no secrets). Intended to run
in CI on every push/PR so drift is caught before a maintainer ever reaches
the manual production-key procedure in docs/key-provisioning.md.

Checks:
  1. keys/official.pub is valid JSON with key_id + public_key_b64. If it is
     still the placeholder, that's fine pre-cutover. If it is not a
     placeholder, public_key_b64 must decode to exactly 32 bytes.
  2. keys/official.pub and registry/index.json.sig agree on key_id once
     both have moved past their placeholder values (catches "committed the
     new public key but forgot to re-sign" or vice versa).
  3. .github/workflows/production.yml:
       - declares `environment: production`
       - does not enable shell/debug tracing (`set -x`, `set -o xtrace`,
         `ACTIONS_STEP_DEBUG: true`, `RUNNER_DEBUG: 1`)
       - does not echo the private key secret
"""

import base64
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUB_PATH = REPO_ROOT / "keys" / "official.pub"
SIG_PATH = REPO_ROOT / "registry" / "index.json.sig"
PRODUCTION_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "production.yml"

PLACEHOLDER_KEY_IDS = {"official-placeholder"}
PLACEHOLDER_VALUES = {"PLACEHOLDER"}

DEBUG_TRACE_PATTERNS = [
    re.compile(r"\bset\s+-\w*x\w*\b"),
    re.compile(r"\bset\s+-o\s+xtrace\b"),
    re.compile(r"ACTIONS_STEP_DEBUG\s*:\s*true", re.IGNORECASE),
    re.compile(r"ACTIONS_RUNNER_DEBUG\s*:\s*true", re.IGNORECASE),
    re.compile(r"RUNNER_DEBUG\s*:\s*1"),
]

# Only flags echoing the *value* (a shell/GitHub-expression expansion of the
# variable), not prose that merely mentions the secret's name in a message.
ECHO_SECRET_RE = re.compile(
    r"echo.*(\$\{?NUMAN_REGISTRY_PRIVATE_KEY\}?|\$\{\{\s*(secrets|env)\.NUMAN_REGISTRY_PRIVATE_KEY)",
    re.IGNORECASE,
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_official_pub():
    errors = []
    try:
        data = load_json(PUB_PATH)
    except Exception as exc:
        return [f"{PUB_PATH}: could not parse JSON: {exc}"], None

    key_id = data.get("key_id")
    public_key_b64 = data.get("public_key_b64")
    if not key_id or not public_key_b64:
        errors.append(f"{PUB_PATH}: must contain key_id and public_key_b64")
        return errors, None

    if key_id in PLACEHOLDER_KEY_IDS or public_key_b64 in PLACEHOLDER_VALUES:
        print(f"OK: {PUB_PATH} is still a placeholder (expected pre-cutover)")
        return errors, None

    try:
        raw = base64.b64decode(public_key_b64, validate=True)
    except Exception as exc:
        errors.append(f"{PUB_PATH}: public_key_b64 is not valid base64: {exc}")
        return errors, key_id

    if len(raw) != 32:
        errors.append(f"{PUB_PATH}: public key must decode to 32 bytes, got {len(raw)}")
        return errors, key_id

    print(f"OK: {PUB_PATH} has a well-formed non-placeholder key (key_id={key_id})")
    return errors, key_id


def check_key_id_consistency(pub_key_id):
    errors = []
    try:
        sig = load_json(SIG_PATH)
    except Exception as exc:
        errors.append(f"{SIG_PATH}: could not parse JSON: {exc}")
        return errors

    sig_key_id = sig.get("key_id")
    sig_signature = sig.get("signature")

    sig_is_placeholder = sig_key_id in PLACEHOLDER_KEY_IDS or sig_signature in PLACEHOLDER_VALUES
    pub_is_placeholder = pub_key_id is None

    if sig_is_placeholder:
        # Nothing has been signed yet. This is fine whether or not the
        # public key has already been committed -- the real cutover flow
        # commits keys/official.pub first (its own small PR, no private key
        # involved), and signing only happens later, once the production
        # environment secret exists and the Production registry workflow
        # runs. Requiring both to move together would make the documented
        # sequential flow permanently fail preflight.
        print(f"OK: {SIG_PATH} is still a placeholder (nothing signed yet)")
        return errors

    # sig is non-placeholder: something was actually signed. Its key_id
    # must match the currently-committed public key, or the index was
    # signed with a key that isn't (or is no longer) the trust root.
    if pub_is_placeholder:
        errors.append(
            f"{SIG_PATH} is signed with key_id {sig_key_id!r} but {PUB_PATH} is "
            "still a placeholder -- the signing key was never committed as "
            "the trust root."
        )
        return errors

    if pub_key_id != sig_key_id:
        errors.append(
            f"key_id mismatch: {PUB_PATH} has key_id={pub_key_id!r} but "
            f"{SIG_PATH} has key_id={sig_key_id!r}"
        )
        return errors

    print(f"OK: {PUB_PATH} and {SIG_PATH} agree on key_id={pub_key_id}")
    return errors


def check_production_workflow():
    errors = []
    if not PRODUCTION_WORKFLOW_PATH.exists():
        return [f"{PRODUCTION_WORKFLOW_PATH}: does not exist"]

    text = PRODUCTION_WORKFLOW_PATH.read_text(encoding="utf-8")

    if not re.search(r"^\s*environment:\s*production\s*$", text, re.MULTILINE):
        errors.append(
            f"{PRODUCTION_WORKFLOW_PATH}: must declare 'environment: production' on the job"
        )
    else:
        print(f"OK: {PRODUCTION_WORKFLOW_PATH} targets the 'production' environment")

    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in DEBUG_TRACE_PATTERNS:
            if pattern.search(line):
                errors.append(
                    f"{PRODUCTION_WORKFLOW_PATH}:{lineno}: enables debug/trace output "
                    f"which could leak secret values: {line.strip()}"
                )
        if ECHO_SECRET_RE.search(line):
            errors.append(
                f"{PRODUCTION_WORKFLOW_PATH}:{lineno}: echoes the private key secret: {line.strip()}"
            )

    if not any(e.startswith(f"{PRODUCTION_WORKFLOW_PATH}") and "debug" in e for e in errors):
        print(f"OK: {PRODUCTION_WORKFLOW_PATH} does not enable debug/trace output")
    if not any("echoes the private key" in e for e in errors):
        print(f"OK: {PRODUCTION_WORKFLOW_PATH} does not echo the private key secret")

    return errors


def main():
    all_errors = []

    pub_errors, pub_key_id = check_official_pub()
    all_errors.extend(pub_errors)

    all_errors.extend(check_key_id_consistency(pub_key_id))
    all_errors.extend(check_production_workflow())

    if all_errors:
        print(f"\nFAIL: preflight found {len(all_errors)} issue(s):\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\nPreflight passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
