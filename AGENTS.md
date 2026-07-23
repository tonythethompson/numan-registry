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

### Checks CI runs

- `python3 scripts/scan_for_secrets.py` — scans git-tracked files for private-key material.
- `python3 scripts/preflight.py` — key/workflow consistency checks (no network, no secrets).
- `python3 scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub` — schema + canonical-JSON + Ed25519 signature checks. Add `--skip-artifacts` to avoid network artifact-digest downloads.
- `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json` — parse the catalog with Numan's production Rust registry parser (repo-safety + production workflows).
- `python3 scripts/lint-manifest-index.py --index registry/index.json --manifest <numan-plugins/manifest.json>` — Stage 2 gate: fail when an `active[]` plugin's `nu_version` disagrees with the same owner/name/version in the index (repo-safety).

### Non-obvious gotchas

- The production registry is live. The committed `registry/index.json.sig` still
  ships a `PLACEHOLDER` because production signing happens only in the protected
  deployment workflow; GitHub Pages contains the signed production artifact. Do not
  change that source-tree placeholder or treat it as an unsigned-production fallback.
- To exercise the full sign→verify path locally, mirror `staging.yml`: generate an
  ephemeral Ed25519 keypair, sign with `scripts/ci-sign.py`, then validate with
  `scripts/validate.py` pointing `--sig`/`--pub` at your temp files. Write these to
  a temp dir so you never overwrite the committed placeholder signature.
- `scripts/add-package.py` downloads each artifact to compute its sha256, so it
  needs network for real specs; its guardrails (missing fields, `kind: source`,
  unsupported archive suffixes) fail fast before any download.
- `scripts/lifecycle-prove.py` needs network plus a real `numan` and `nu` on
  PATH (or `--numan` / `--nu`). It is a maintainer Stage 1 gate, not a
  repo-safety CI job. See `docs/lifecycle-prove.md`.
- Never commit private-key material. `*.key`, `*.pem`, `*_private_key*` etc. are
  gitignored and the secret scanner will fail CI if they are force-added.
