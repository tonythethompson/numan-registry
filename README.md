# Numan Official Registry

Curated registry index for the [Numan](https://github.com/tonythethompson/numan) Nushell package manager.

This repository is **not** the package manager itself. It publishes the signed registry index that Numan clients download, verify, and install from.

## Status

The official production registry is live at [tonythethompson.github.io/numan-registry](https://tonythethompson.github.io/numan-registry/). It is signed with the provisioned `official-2026-07-01` trust root (committed in `keys/official.pub` and built into Numan). Clients should use Numan's `official` registry URL, not a checkout of this repo.

This `main` branch is the catalog source. The committed `registry/index.json.sig` remains a deliberate placeholder: real production signatures are created only by the protected production workflow (which holds `NUMAN_REGISTRY_PRIVATE_KEY`) and published to GitHub Pages. Do not treat the source-tree `.sig` as an installable trust artifact.

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
│   └── outreach-issues/               # Copy-paste GitHub issue drafts for upstream contact
├── .cursor/
│   └── hooks.json                     # Agent hooks: auto-sync intake docs after edits/gh/stop
├── keys/
│   └── official.pub               # Committed production public key
├── registry/
│   ├── index.json                 # Catalog source (signed at publish time)
│   └── index.json.sig             # Placeholder in-repo; live signed envelope is on GitHub Pages
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
├── tools/
│   └── numan-parser-check/             # Pinned check using Numan's production registry parser
└── .github/workflows/
    ├── staging.yml                # Deploy staging index with ephemeral key
    ├── production.yml             # Deploy production index from protected environment
    └── repo-safety.yml            # Secret scan, preflight, and Numan parser checks on every push/PR
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
- **Production**: live. Dispatched from `main` only through the protected GitHub Actions environment that requires manual approval and the provisioned `NUMAN_REGISTRY_PRIVATE_KEY` secret. That workflow parses the catalog with Numan's production parser, signs with the real key, verifies against `keys/official.pub`, and publishes to GitHub Pages.

## Validation

The committed `registry/index.json.sig` is a placeholder, so validating the source tree against it will fail. To verify the live production artifacts:

```bash
curl -fsSL https://tonythethompson.github.io/numan-registry/index.json -o /tmp/numan-index.json
curl -fsSL https://tonythethompson.github.io/numan-registry/index.json.sig -o /tmp/numan-index.json.sig
python scripts/validate.py \
  --index /tmp/numan-index.json \
  --sig /tmp/numan-index.json.sig \
  --pub keys/official.pub
```

CI validates the JSON schema, verifies artifact digests for non-fixture entries, parses the catalog with a pinned revision of Numan's production Rust registry parser, and (on production publish) verifies the freshly signed index against the committed public key.

## Operations

- [Incident response and user remediation](docs/incident-response.md)
- [Production cutover and key-exposure runbook](docs/production-cutover-checklist.md)
- [Signing-key rotation checklist](docs/key-rotation-checklist.md)
