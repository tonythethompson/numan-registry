# Numan Official Registry

Curated registry index for the [Numan](https://github.com/tonythethompson/numan) Nushell package manager.

This repository is **not** the package manager itself. It publishes the signed registry index that Numan clients download, verify, and install from.

## Status

The official production registry is live at [tonythethompson.github.io/numan-registry](https://tonythethompson.github.io/numan-registry/) and signed with the `official-2026-07-01` trust root built into Numan.

This `main` branch is the catalog source. Its committed `registry/index.json.sig` is deliberately a placeholder: the protected production workflow signs the catalog with `NUMAN_REGISTRY_PRIVATE_KEY` and publishes the resulting detached signature to GitHub Pages. Do not use the source-tree signature for an install; use Numan's `official` registry URL.

## Layout

```text
.
├── docs/
│   ├── key-provisioning.md            # WSL-first maintainer key-provisioning instructions
│   ├── production-cutover-checklist.md # Step-by-step cutover runbook with rollback steps
│   ├── key-rotation-checklist.md      # Rotation runbook: successor-key ordering, propagation wait, rollback
│   ├── incident-response.md            # Yank, rollback, compromise, and user-remediation policy
│   ├── intake-candidates.md           # Running intake list (auto-synced; edit intake-state.json)
│   ├── intake-state.json              # Machine-readable intake catalog (source for sync)
│   ├── upstream-release-outreach.md   # Outreach plan + tracker (tracker auto-synced)
│   ├── lifecycle-prove.md             # Stage 1: scripted search→…→gc against real Nu
│   └── outreach-issues/               # Copy-paste GitHub issue drafts for upstream contact
├── .cursor/
│   └── hooks.json                     # Agent hooks: auto-sync intake docs after edits/gh/stop
├── keys/
│   └── official.pub               # Committed production public key
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
│   ├── lifecycle-prove.py             # Stage 1 acceptance: prove a package on a clean root + real Nu
│   ├── lint-manifest-index.py         # Fail if numan-plugins manifest Nu range ≠ index (when both known)
│   ├── build-mirror-zip.py            # Build registry-hosted mirror zips from git tags/commits
│   └── sync-intake-candidates.py      # Regenerate intake-candidates.md from state + gh
├── tools/
│   └── numan-parser-check/             # Pinned check using Numan's production registry parser
└── .github/workflows/
    ├── staging.yml                # Deploy staging index with ephemeral key
    ├── production.yml             # Deploy production index from protected environment
    └── repo-safety.yml            # Secret scan, preflight, Numan parser, manifest↔index Nu lint
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

The registry private key is **never** committed, printed, or handled by coding agents. See `docs/key-provisioning.md` for the manual, WSL-first maintainer process, and `docs/production-cutover-checklist.md` for the original cutover runbook. For an active incident, follow `docs/incident-response.md`; it covers yanks, compromised artifacts, index rollback, key exposure, and user remediation. `scripts/provision-production-key.sh` generates the keypair locally and never prints the private key.

## Environments

- **Staging**: deployed automatically from the default branch using an ephemeral CI-generated key. It validates source changes without asserting production trust.
- **Production**: deployed from `main` only through the protected GitHub Actions environment that requires manual approval and the `NUMAN_REGISTRY_PRIVATE_KEY` secret.

## Validation

```bash
python scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub
```

CI validates the JSON schema, verifies the signed production candidate, downloads and verifies artifact digests for non-fixture entries, and parses the catalog with a pinned revision of Numan's production Rust registry parser.

## Intake prove (Stage 1)

After `add-package.py --write`, the package **must be staged or published** in the
configured registry before running `scripts/lifecycle-prove.py`, unless a
registry-target override is added. Prove the package on a clean root with a real
Nu that matches its constraint:

```bash
python scripts/lifecycle-prove.py --package owner/name --numan /path/to/numan --nu /path/to/nu
```

See [docs/lifecycle-prove.md](docs/lifecycle-prove.md).

## Operations

- [Incident response and user remediation](docs/incident-response.md)
- [Production cutover and key-exposure runbook](docs/production-cutover-checklist.md)
- [Signing-key rotation checklist](docs/key-rotation-checklist.md)
