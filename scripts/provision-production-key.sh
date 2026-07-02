#!/usr/bin/env bash
#
# Generate a production Ed25519 signing keypair for the Numan official
# registry, or (with --verify) validate an already-committed public key
# and optionally a signed index, without ever needing the private key.
#
# SAFETY:
#   - This script NEVER prints the private key to stdout/stderr.
#   - The private key is written to a local file with 600 permissions and
#     is intended to be copied into a password manager / encrypted vault
#     exactly once, then deleted. See docs/key-provisioning.md.
#   - Do not paste the private key file's contents anywhere: not into
#     chat, not into an issue/PR, not into a commit, not into a log.
#
# Usage:
#   ./scripts/provision-production-key.sh [--force] [--out-dir DIR]
#   ./scripts/provision-production-key.sh --verify --pub PATH [--index PATH --sig PATH]
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_PATH="${REPO_ROOT}/schemas/index-v1.json"
VALIDATE_PY="${REPO_ROOT}/scripts/validate.py"

MODE="generate"
FORCE=0
OUT_DIR=""
VERIFY_PUB=""
VERIFY_INDEX=""
VERIFY_SIG=""

usage() {
  cat <<'EOF'
Usage:
  provision-production-key.sh [--force] [--out-dir DIR]
      Generate a new Ed25519 keypair. Writes a timestamped output
      directory (default: provisioning/<UTC timestamp>/) containing a
      public key file, a private key file, and a safe-to-share JSON
      summary. Never prints the private key.

  provision-production-key.sh --verify --pub PATH [--index PATH --sig PATH]
      Validate a public key file (and optionally an index + signature
      against it) without touching any private key material.

Options:
  --force            Allow overwriting an existing output directory.
  --out-dir DIR       Output directory for generation (default:
                       provisioning/<UTC timestamp> under the repo root).
  --verify            Switch to verify mode.
  --pub PATH          Public key JSON file to verify (verify mode).
  --index PATH        Registry index to verify against the public key.
  --sig PATH           Detached signature file for --index.
  -h, --help          Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --verify) MODE="verify"; shift ;;
    --pub) VERIFY_PUB="$2"; shift 2 ;;
    --index) VERIFY_INDEX="$2"; shift 2 ;;
    --sig) VERIFY_SIG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is required. Install Python 3.9+ in WSL and re-run." >&2
  exit 1
fi

if ! python3 -c 'import cryptography' >/dev/null 2>&1; then
  echo "FAIL: the 'cryptography' package is required." >&2
  echo "       Install it with: python3 -m pip install --user cryptography" >&2
  exit 1
fi

if [[ "${MODE}" == "verify" ]]; then
  if [[ -z "${VERIFY_PUB}" ]]; then
    echo "FAIL: --verify requires --pub PATH" >&2
    exit 2
  fi
  if [[ -n "${VERIFY_INDEX}" || -n "${VERIFY_SIG}" ]]; then
    if [[ -z "${VERIFY_INDEX}" || -z "${VERIFY_SIG}" ]]; then
      echo "FAIL: --index and --sig must be supplied together" >&2
      exit 2
    fi
    echo "Verifying public key, index, and signature (no private key involved)..."
    python3 "${VALIDATE_PY}" \
      --index "${VERIFY_INDEX}" \
      --sig "${VERIFY_SIG}" \
      --pub "${VERIFY_PUB}" \
      --schema "${SCHEMA_PATH}" \
      --skip-artifacts
    exit $?
  fi

  echo "Verifying public key file only (no private key involved)..."
  python3 - "${VERIFY_PUB}" <<'PY'
import base64
import hashlib
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

key_id = data.get("key_id")
public_key_b64 = data.get("public_key_b64")
if not key_id or not public_key_b64:
    print(f"FAIL: {path} must contain key_id and public_key_b64")
    sys.exit(1)
if public_key_b64 == "PLACEHOLDER":
    print(f"FAIL: {path} is still a placeholder")
    sys.exit(1)

try:
    raw = base64.b64decode(public_key_b64, validate=True)
except Exception as exc:
    print(f"FAIL: public_key_b64 in {path} is not valid base64: {exc}")
    sys.exit(1)
if len(raw) != 32:
    print(f"FAIL: public key must decode to 32 bytes, got {len(raw)}")
    sys.exit(1)

fingerprint = hashlib.sha256(raw).hexdigest()[:16]
print(f"OK: key_id={key_id}")
print(f"OK: public key decodes to 32 bytes")
print(f"OK: fingerprint (sha256, first 16 hex chars) = {fingerprint}")
PY
  exit $?
fi

# --- generate mode ---

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MONTH_DAY_ID="official-$(date -u +%Y-%m)-01"

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${REPO_ROOT}/provisioning/${TIMESTAMP}"
fi

if [[ -e "${OUT_DIR}" && "${FORCE}" -ne 1 ]]; then
  echo "FAIL: output directory already exists: ${OUT_DIR}" >&2
  echo "       Re-run with --force to overwrite, or remove it first." >&2
  exit 1
fi

# Restrictive umask so the private key file is never briefly group/world
# readable between creation and the chmod below, even transiently.
umask 077

mkdir -p "${OUT_DIR}"

PUB_FILE="${OUT_DIR}/${MONTH_DAY_ID}.pub"
KEY_FILE="${OUT_DIR}/${MONTH_DAY_ID}.key"
SUMMARY_FILE="${OUT_DIR}/${MONTH_DAY_ID}.summary.json"

if [[ ( -e "${PUB_FILE}" || -e "${KEY_FILE}" || -e "${SUMMARY_FILE}" ) && "${FORCE}" -ne 1 ]]; then
  echo "FAIL: output files already exist under ${OUT_DIR}" >&2
  echo "       Re-run with --force to overwrite." >&2
  exit 1
fi

echo "=============================================================="
echo " Numan official registry — production key provisioning"
echo "=============================================================="
echo "This generates a new Ed25519 keypair LOCALLY. The private key"
echo "is written to a local file only and is NEVER printed here."
echo
echo "  Do NOT paste the private key file's contents into chat, an"
echo "  issue, a PR, a commit, or a CI log. See docs/key-provisioning.md."
echo "=============================================================="
echo

python3 - "${MONTH_DAY_ID}" "${PUB_FILE}" "${KEY_FILE}" "${SUMMARY_FILE}" <<'PY'
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key_id, pub_path, key_path, summary_path = sys.argv[1:5]

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

pub_raw = public_key.public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
)
priv_raw = private_key.private_bytes(
    serialization.Encoding.Raw,
    serialization.PrivateFormat.Raw,
    serialization.NoEncryption(),
)

pub_b64 = base64.b64encode(pub_raw).decode()
priv_b64 = base64.b64encode(priv_raw).decode()
fingerprint = hashlib.sha256(pub_raw).hexdigest()[:16]
created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(pub_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "key_id": key_id,
            "public_key_b64": pub_b64,
            "note": "Production public key for the Numan official registry.",
        },
        f,
        indent=2,
    )
    f.write("\n")

with open(key_path, "w", encoding="utf-8") as f:
    f.write(priv_b64)
    f.write("\n")

summary = {
    "key_id": key_id,
    "public_key_b64": pub_b64,
    "fingerprint_sha256_16": fingerprint,
    "created_at": created_at,
    "next_steps": [
        "Commit keys/official.pub with this key_id and public_key_b64.",
        "Open a PR in tonythethompson/numan-registry with only that change.",
        "After it merges, add NUMAN_REGISTRY_PRIVATE_KEY as an environment "
        "secret on the 'production' GitHub Environment, using the private "
        "key file's contents (never this summary file).",
        "Copy the private key into a password manager / encrypted vault "
        "exactly once, then delete the local private key file.",
        "Update tonythethompson/numan's src/core/official_registry.rs with "
        "the same key_id and public_key_b64.",
        "Follow docs/production-cutover-checklist.md before dispatching "
        "the Production registry workflow.",
    ],
}
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
    f.write("\n")

# Print only public material.
print(f"key_id: {key_id}")
print(f"public_key_b64: {pub_b64}")
print(f"fingerprint (sha256, first 16 hex chars): {fingerprint}")
print(f"created_at: {created_at}")
PY

chmod 600 "${KEY_FILE}"
chmod 644 "${PUB_FILE}" "${SUMMARY_FILE}"

echo
echo "Wrote:"
echo "  public key   : ${PUB_FILE}"
echo "  private key  : ${KEY_FILE}  (permissions 600, NEVER printed above)"
echo "  safe summary : ${SUMMARY_FILE}  (no private key material; safe to share)"
echo
echo "Next steps (see docs/key-provisioning.md for full detail):"
echo "  1. Commit keys/official.pub with the key_id and public_key_b64 above"
echo "     via GitHub's web UI or a PR, in tonythethompson/numan-registry."
echo "  2. GitHub UI: Settings > Environments > production > Environment"
echo "     secrets > New secret, name NUMAN_REGISTRY_PRIVATE_KEY, value ="
echo "     the contents of: ${KEY_FILE}"
echo "  3. Copy that same file's contents into your password manager /"
echo "     encrypted vault exactly once, then delete the local file."
echo "  4. Follow docs/production-cutover-checklist.md before triggering"
echo "     the Production registry workflow."
echo
echo "Reminder: the private key was written to a file, never to this"
echo "terminal. Do not paste that file's contents anywhere but the GitHub"
echo "secret field and your password manager."
