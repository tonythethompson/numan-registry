---
kind: build_system
name: GitHub Actions CI/CD Pipeline for Signed Numan Registry
category: build_system
scope:
    - '**'
source_files:
    - .github/workflows/staging.yml
    - .github/workflows/production.yml
    - .github/workflows/repo-safety.yml
    - scripts/ci-sign.py
    - scripts/validate.py
    - scripts/preflight.py
    - scripts/scan_for_secrets.py
    - scripts/add-package.py
    - scripts/build-mirror-zip.py
    - scripts/provision-production-key.sh
    - schemas/index-v1.json
    - keys/official.pub
---

This repository uses GitHub Actions as its build and deployment system, with three dedicated workflows orchestrating validation, staging publication, and production signing/publishing of a signed JSON registry index for the Numan Nushell package manager.

**Build & Validation Pipeline**
The `repo-safety.yml` workflow runs on every push and pull request across Ubuntu and Windows runners. It executes Python unit tests (`scripts/test_*.py`) via `python -m unittest discover`, scans for secrets using `scan_for_secrets.py`, runs preflight checks against key/workflow consistency, validates the index schema with `validate.py --schema schemas/index-v1.json`, parses the catalog with a pinned Rust parser from `tools/numan-parser-check`, and lints Nu version constraints between the index and the upstream `numan-plugins/manifest.json`. Dependencies are installed inline via `python -m pip install cryptography jsonschema` — there is no `requirements.txt`; the dependency list lives exclusively in the CI workflows.

**Staging Pipeline**
The `staging.yml` workflow generates an ephemeral Ed25519 keypair at runtime (never committed), signs `registry/index.json` with `ci-sign.py`, validates the signature locally, and publishes the signed artifacts to the `staging` directory on GitHub Pages when pushed to the default branch. It uses read-only `contents: read` permissions during validation and only grants `contents: write` to the separate publish job.

**Production Pipeline**
The `production.yml` workflow is triggered manually via `workflow_dispatch` with a required reason input. It first runs all no-secret validation steps (secret scan, preflight, schema validation, Rust parser check, manifest lint). The second job, gated by the `production` GitHub environment, requires the `NUMAN_REGISTRY_PRIVATE_KEY` secret, explicitly blocks debug logging, reads the production key ID from `keys/official.pub`, signs the index, validates it against the committed public key, and publishes to the root of GitHub Pages. Debug flags (`ACTIONS_STEP_DEBUG`, `RUNNER_DEBUG`) are rejected before signing proceeds.

**Artifact Management**
Per-package specs live in `specs/*.json`, mirror archives in `mirrors/*.zip`, and the canonical signed index in `registry/index.json` plus `registry/index.json.sig`. The index format is defined by `schemas/index-v1.json` and must be canonicalized (sorted keys, compact encoding) before signing. Mirror zips are built via `build-mirror-zip.py` from git tags/commits.

**Tooling & Conventions**
- Python scripts use `unittest` for testing; no pytest or tox configuration exists.
- A small Rust tool (`tools/numan-parser-check`) pins the exact Numan production parser revision for compatibility validation.
- Shell scripts handle key provisioning (`provision-production-key.sh`) and are WSL-first per documentation.
- All workflows pin action versions explicitly and set `persist-credentials: false` for security.
- No Dockerfiles, Makefiles, or traditional build systems exist; the entire pipeline is expressed as GitHub Actions YAML.