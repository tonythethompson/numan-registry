# Numan Official Registry

Curated registry index for the [Numan](https://github.com/tonythethompson/numan) Nushell package manager.

This repository is **not** the package manager itself. It publishes the signed registry index that Numan clients download, verify, and install from.

## Status

This registry is currently in **staging** mode: `registry/index.json` has real, verified seed packages (see below), but the production signing key has not been provisioned yet, so nothing here is signed for production trust. Do not rely on the current index for production installs until `docs/production-cutover-checklist.md` is complete.

## Layout

```text
.
├── docs/
│   ├── key-provisioning.md            # WSL-first maintainer key-provisioning instructions
│   ├── production-cutover-checklist.md # Step-by-step cutover runbook with rollback steps
│   ├── key-rotation-checklist.md      # Rotation runbook: successor-key ordering, propagation wait, rollback
│   ├── intake-candidates.md           # Running intake list (auto-synced; edit intake-state.json)
│   ├── intake-state.json              # Machine-readable intake catalog (source for sync)
│   ├── upstream-release-outreach.md   # Outreach plan + tracker (tracker auto-synced)
│   └── outreach-issues/               # Copy-paste GitHub issue drafts for upstream contact
├── .cursor/
│   └── hooks.json                     # Agent hooks: auto-sync intake docs after edits/gh/stop
├── keys/
│   └── official.pub               # Committed public key placeholder
├── registry/
│   ├── index.json                 # Signed registry index
│   └── index.json.sig             # Detached signature envelope
├── schemas/
│   └── index-v1.json              # JSON schema for index.json
├── scripts/
│   ├── validate.py                    # Index + signature validator
│   ├── ci-sign.py                     # CI signer (used by staging/production workflows)
│   ├── provision-production-key.sh    # WSL keypair generator / public-key verifier
│   ├── preflight.py                   # Key/workflow consistency checks (no secrets, no network)
│   ├── scan_for_secrets.py            # CI scan for probable private-key material
│   ├── add-package.py                 # Scaffold a package entry from a spec (computes sha256, never hand-typed)
│   ├── build-mirror-zip.py            # Build registry-hosted mirror zips from git tags/commits
│   └── sync-intake-candidates.py      # Regenerate intake-candidates.md from state + gh
└── .github/workflows/
    ├── staging.yml                # Deploy staging index with ephemeral key
    ├── production.yml             # Deploy production index from protected environment
    └── repo-safety.yml            # Secret scan + preflight checks on every push/PR
```

## Schema

The registry index is JSON with a required top-level `schema_version` of `1`. The canonical JSON form (sorted object keys, compact encoding, no whitespace) is what is signed and digested. See `schemas/index-v1.json` and the Numan source `src/core/official_registry.rs` for the exact canonicalization rules.

## Signing

The detached signature file `registry/index.json.sig` is a JSON envelope:

```json
{
  "key_id": "official-YYYY-MM",
  "algorithm": "ed25519",
  "signature": "base64..."
}
```

The `signature` value is an Ed25519 signature over the **canonical JSON bytes** of `registry/index.json`. The SHA-256 of those canonical bytes is the `index_sha256` that Numan clients record in their lockfiles.

## Key management

The registry private key is **never** committed, printed, or handled by coding agents. See `docs/key-provisioning.md` for the manual, WSL-first maintainer process, and `docs/production-cutover-checklist.md` for the full cutover runbook with rollback steps. `scripts/provision-production-key.sh` generates the keypair locally and never prints the private key.

## Environments

- **Staging**: deployed automatically from the default branch using an ephemeral CI-generated key or a separate staging secret. Used for schema and tooling validation.
- **Production**: deployed only from a protected GitHub Actions environment that requires manual approval and the `NUMAN_REGISTRY_PRIVATE_KEY` secret.

## Validation

```bash
python scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub
```

The CI validator also downloads and verifies artifact digests for non-fixture entries.
