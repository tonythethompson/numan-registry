---
kind: dependency_management
name: 'Numan Registry: Signed JSON Index with Spec-Driven Package Intake and Artifact Hash Pinning'
category: dependency_management
scope:
    - '**'
source_files:
    - registry/index.json
    - registry/index.json.sig
    - schemas/index-v1.json
    - scripts/add-package.py
    - scripts/ci-sign.py
    - scripts/lifecycle-prove.py
    - scripts/lint-manifest-index.py
    - scripts/validate.py
    - tools/numan-parser-check/Cargo.toml
    - tools/numan-parser-check/Cargo.lock
    - specs/nushell-prophet-numd-0.4.0.json
---

This repository implements a curated Nushell package registry ("Numan") that manages third-party Nushell plugins, modules, scripts, and completions through a signed JSON index. The dependency management approach centers on declarative per-package spec files, automated artifact hashing, schema validation, and cryptographic signing of the published index.

**System and tools used**
- A Rust tool (`tools/numan-parser-check`) pins an exact git revision of `numan-cli` to ensure CI parses candidates with the same parser shipped in production.
- Python scripts under `scripts/` scaffold registry entries from human-authored specs, download artifacts, compute SHA-256 digests, validate against a JSON Schema, merge entries into `registry/index.json`, and sign the result via CI.
- A JSON Schema (`schemas/index-v1.json`) defines the canonical index format enforced by the intake pipeline.
- Ed25519 keys are stored under `keys/official.pub`; the signed index is published as `registry/index.json.sig` alongside `registry/index.json`.

**Key files and packages**
- `registry/index.json` — the canonical signed registry index listing all packages, versions, artifact URLs, and SHA-256 digests.
- `registry/index.json.sig` — the detached signature over the index.
- `schemas/index-v1.json` — JSON Schema v1 for the index structure.
- `specs/*.json` — per-package spec files describing owner, name, type, version, Nu version constraints, artifact URLs, activation metadata, and optional lifecycle evidence (`verified_with`).
- `scripts/add-package.py` — scaffolds a package entry from a spec, downloads artifacts, computes sha256, validates schema, and merges into the index.
- `scripts/ci-sign.py`, `scripts/lifecycle-prove.py`, `scripts/lint-manifest-index.py`, `scripts/validate.py` — CI signing, lifecycle verification, manifest linting, and general validation helpers.
- `tools/numan-parser-check/Cargo.toml` and `Cargo.lock` — pin the exact `numan-cli` git revision used for parsing candidate specs.
- `mirrors/*.zip` — byte-stable mirror archives of upstream releases used when upstream assets cannot be hash-pinned directly.

**Architecture and conventions**
- **Spec-driven intake**: Maintainers write a small JSON spec in `specs/`. `add-package.py` resolves artifact URLs, computes SHA-256 digests, enforces supported archive formats (`.zip`, `.tar.gz`), validates lifecycle evidence (`verified_with`), and either prints or merges the resulting package entry into `registry/index.json`. Source builds (`artifact.kind: "source"`) are explicitly rejected until client support lands.
- **Schema enforcement**: Every generated index is validated against `schemas/index-v1.json` using `jsonschema` when available; the schema restricts fields like `type` to `[plugin, module, script, completion]`, requires `sha256` for every artifact URL, and constrains `nu_version` patterns.
- **Artifact integrity**: All binary and archive artifacts must include a computed `sha256` field. Archive entries may specify `entry`, `archive_root`, and `include` to control activation. Binary entries enumerate per-target `url`, `sha256`, and `executable_path`.
- **Activation model**: Activatable packages declare an `activation` block (`kind: "nu-module"`, `import: "module|all"`). The intake script rejects `mod.nu` entries paired with `import: "module"` because Numan imports the file directly rather than the directory.
- **Lifecycle evidence**: Packages requiring activation must list `verified_with` Nushell versions where they have been tested. Provisional staging is allowed via `--provisional`, but production validation rejects entries without genuine evidence.
- **Signing and trust**: The index is signed with an Ed25519 key (`keys/official.pub`) and the signature is published alongside the index. Trust root updates follow a separate script in the upstream `numan` repo.
- **Mirror strategy**: When upstream release assets cannot be reliably hash-pinned, the registry publishes its own mirrored zip archives under `mirrors/` and references those stable URLs in the index.

**Conventions and constraints**
- Package types are restricted to `plugin`, `module`, `script`, or `completion` as enforced by the schema and `add-package.py` validation.
- Every artifact URL must end in a supported suffix (`.zip`, `.tar.gz`); unsupported formats cause immediate failure during intake.
- `verified_with` must contain at least one semver Nushell version string matching the pattern `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`.
- The Rust parser dependency is pinned to a specific git commit (`rev = "6e93c27307a5a256fa6e6dcab602edf1707ed7d1"`) to guarantee CI uses the same parser as production.
- Source-only builds are not yet supported; attempting to use `artifact.kind: "source"` aborts the intake script.
- Replacing an existing version in the index requires explicit `--force`; otherwise the script refuses to overwrite.