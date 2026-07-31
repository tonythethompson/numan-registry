# numan-registry PR review

Use this file when reviewing pull requests (human or automated). [`AGENTS.md`](AGENTS.md) remains the source for toolchain and CI commands; this file focuses on **what to flag in review**.

## CI gates (must pass)

- `python3 scripts/scan_for_secrets.py`
- `python3 scripts/preflight.py`
- `python3 scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub` (add `--skip-artifacts` when offline)
- `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json`
- For CI-built plugins: `python3 scripts/lint-manifest-index.py --index registry/index.json --manifest <numan-plugins/manifest.json>`

## Severity labels

| Label | Meaning |
|-------|---------|
| **P0** | Trust bypass, private-key material, unsigned-production fallback, hand-typed artifact hashes, silent index corruption |
| **P1** | Incorrect intake/validation on happy path, missing lifecycle evidence for activatable packages, schema/parser mismatch |
| **P2** | Doc/intake-state drift, misleading checklists, maintainability of scripts |
| **P3** | Style, naming, non-blocking suggestions |

## Architecture invariants (flag violations)

1. **No private keys in tree** — never commit `*.key`, `*.pem`, or private-key material; secret scan must stay green.
2. **Placeholder signature is intentional** — committed `registry/index.json.sig` may be `PLACEHOLDER`; production signing happens only in the protected deployment workflow. Do not treat the placeholder as an unsigned-production fallback or replace it with a local “real” signature in source.
3. **Hashes from download only** — artifact digests come from `scripts/add-package.py` (download + compute). Never hand-type SHA256 values into the index or specs.
4. **Source builds stay out** — reject `kind: source` and unsupported archive suffixes at intake; binary artifacts only for official catalog promotion.
5. **Provenance preserved** — CI-built plugin intake must keep `source.rev` (immutable upstream commit) and human-facing tag provenance from the plugins handoff.
6. **Stage 1 evidence before promote** — activatable packages need lifecycle-prove evidence (or an explicit deferral with reason). See [`docs/lifecycle-prove.md`](docs/lifecycle-prove.md).
7. **Human review before production sign** — protected `production.yml` + reviewer approval; scripts must not auto-publish to the trust root.
8. **Parser parity** — index changes must parse with Numan's production Rust registry parser (`tools/numan-parser-check`).

## Review checklist

- [ ] No secrets or private-key paths added (including force-adds that bypass gitignore).
- [ ] Index/schema changes validated; Numan parser check considered for catalog edits.
- [ ] Artifact URLs and digests produced by `add-package.py`, not edited by hand.
- [ ] For plugins from `numan-plugins`: `nu_version` agrees with `manifest.json` `active[]`.
- [ ] Intake docs / `docs/intake-state.json` / candidates stay consistent when catalog state changes.
- [ ] Scope matches PR description; no unrelated catalog churn on tooling-only PRs.

## Intake-specific notes

- Follow the PR template checklist for new or changed packages.
- Staging may sign with ephemeral keys; that path must not overwrite committed production placeholder material.
- `scripts/lifecycle-prove.py` is a maintainer Stage 1 gate, not a substitute for repo-safety CI.
