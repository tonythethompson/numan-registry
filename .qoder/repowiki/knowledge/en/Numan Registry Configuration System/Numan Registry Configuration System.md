---
kind: configuration_system
name: Numan Registry Configuration System
category: configuration_system
scope:
    - '**'
source_files:
    - scripts/add-package.py
    - scripts/validate.py
    - scripts/lifecycle-prove.py
    - schemas/index-v1.json
    - registry/index.json
    - keys/official.pub
---

This repository is a curated Nushell package registry that does not use a traditional application configuration system (no `.env`, `config.yaml`, `application.properties`, or centralized config loader). Instead, runtime behavior is controlled through three complementary mechanisms:

**1. Command-line arguments (primary configuration)**
All scripts in `scripts/` are CLI-first: `add-package.py`, `validate.py`, `lifecycle-prove.py`, `lint-manifest-index.py`, etc. accept explicit flags via `argparse` for every tunable parameter (e.g. `--index`, `--sig`, `--pub`, `--schema`, `--package`, `--numan`, `--nu`, `--root`, `--write`, `--force`, `--provisional`, `--skip-signature`, `--skip-artifacts`, `--strict-artifacts`, `--allow-provisional-lifecycle`). There is no fallback to environment variables or config files — if a flag is needed, it must be passed on the command line.

**2. Environment variables (minimal, targeted overrides)**
The only environment variable used by the tooling is `NUMAN_ROOT`, set by `lifecycle-prove.py` (line 263) to point the Numan client at an isolated temporary root directory during lifecycle verification. The script copies `os.environ` and injects this single variable before invoking `numan`. No other script reads environment variables for configuration; `scan_for_secrets.py` explicitly looks for `os.environ` / `getenv` usage as part of secret scanning.

**3. Data-driven configuration (JSON schema + index)**
The registry's actual "configuration" is the JSON index (`registry/index.json`) validated against the JSON Schema (`schemas/index-v1.json`). This schema enforces structure, required fields, allowed enum values (`type`: plugin/module/script/completion; `artifact.kind`: binary/archive/source; `activation.import`: module/all), URL formats, SHA-256 patterns, and version constraints. The schema also defines the `trust` block for key rotation and the `source` provenance block for CI-built artifacts.

**Key design decisions:**
- No file-based config loading exists anywhere in the Python tooling; configuration is positional (CLI args) and declarative (JSON spec files under `specs/`).
- The `keys/official.pub` file holds the production Ed25519 public key used for signature verification, loaded directly by `validate.py` via `--pub keys/official.pub`.
- Lifecycle evidence (`verified_with`) and activation metadata are treated as data, not configuration — they are validated by `nu_version_constraint.lifecycle_evidence_error()` rather than parsed from config files.
- Provisional staging is supported via `--provisional` / `--allow-provisional-lifecycle` flags, allowing activatable entries without `verified_with` during intake, but production validation rejects them.