# AGENTS.md

## Cursor Cloud specific instructions

This is a **data-only repository**: the signed Numan registry index plus Python CI
tooling. There is no long-running service, web server, build step, or test framework
to start — the "application" is the command-line toolchain under `scripts/`.

### Dependencies

- Python 3.12 (matches CI `python-version: "3.12"`).
- `cryptography` (pre-installed on the image) and `jsonschema` are the only
  third-party Python dependencies. The update script installs them with
  `python3 -m pip install --user`. There is no `requirements.txt`; the dependency
  list lives in the CI workflows (`.github/workflows/staging.yml`,
  `production.yml`) and is `cryptography jsonschema`.

### Checks CI runs (there is no lint step)

- `python3 scripts/scan_for_secrets.py` — scans git-tracked files for private-key material.
- `python3 scripts/preflight.py` — key/workflow consistency checks (no network, no secrets).
- `python3 scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub` — schema + canonical-JSON + Ed25519 signature checks. Add `--skip-artifacts` to avoid network artifact-digest downloads.

### Non-obvious gotchas

- The repo is intentionally in **staging mode**: `registry/index.json.sig` ships a
  `PLACEHOLDER` signature, so `scripts/validate.py` reports `FAIL: signature ... is
  still a placeholder` (exit 1) against the committed state. That is expected until
  the production key is provisioned (see `docs/production-cutover-checklist.md`).
- To exercise the full sign→verify path locally, mirror `staging.yml`: generate an
  ephemeral Ed25519 keypair, sign with `scripts/ci-sign.py`, then validate with
  `scripts/validate.py` pointing `--sig`/`--pub` at your temp files. Write these to
  a temp dir so you never overwrite the committed placeholder signature.
- `scripts/add-package.py` downloads each artifact to compute its sha256, so it
  needs network for real specs; its guardrails (missing fields, `kind: source`,
  unsupported archive suffixes) fail fast before any download.
- Never commit private-key material. `*.key`, `*.pem`, `*_private_key*` etc. are
  gitignored and the secret scanner will fail CI if they are force-added.
