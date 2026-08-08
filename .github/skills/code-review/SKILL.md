---
name: code-review
description: >-
  Review numan-registry pull requests against REVIEW.md severity labels, trust
  invariants, intake rules, and CI gates. Use for Copilot code review, PR review
  requests, and any pull-request or diff review in this repository.
---

# numan-registry code review

When reviewing a pull request or diff in this repository, follow the canonical
guide at [`REVIEW.md`](../../../REVIEW.md). Prefer that file over paraphrased
memory. [`AGENTS.md`](../../../AGENTS.md) remains the source for toolchain and
CI commands.

## How to review

1. Read the PR description and changed files; stay within the stated scope.
2. Apply severity labels from `REVIEW.md` (P0–P3). Lead with P0/P1 findings.
3. Flag any violation of the trust and intake invariants listed below.
4. For catalog or index changes, verify digests came from download, parser
   parity, and Stage 1 evidence expectations for activatable packages.
5. Leave actionable comments with concrete fixes. Do not approve or request
   changes as a human gate; report findings only.

## CI gates (must pass)

Use `python` (matches CI / Windows). From a clean checkout the index signature is an
intentional `PLACEHOLDER`, so unsigned validation is the local gate; full
signature verify requires a staging ephemeral sign or production deploy (do not
overwrite the committed placeholder).

- `python scripts/scan_for_secrets.py`
- `python scripts/preflight.py`
- `python scripts/validate.py --index registry/index.json --schema schemas/index-v1.json --skip-signature` (add `--skip-artifacts` when offline)
- Signature path: ephemeral sign via `scripts/ci-sign.py` (as in staging), then `python scripts/validate.py --index registry/index.json --sig PATH/TO/temp.sig --pub PATH/TO/temp.pub --schema schemas/index-v1.json`
- `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json`
- For CI-built plugins (sibling checkout): `python scripts/lint-manifest-index.py --index registry/index.json --manifest numan-plugins/manifest.json`
- Script unit tests: `python -m unittest discover -s scripts -p "test_*.py" -v` (see `.github/workflows/repo-safety.yml`)

## Severity labels

| Label | Meaning |
|-------|---------|
| **P0** | Trust bypass, private-key material, unsigned-production fallback, hand-typed artifact hashes, silent index corruption |
| **P1** | Incorrect intake/validation on happy path, missing lifecycle evidence for activatable packages, schema/parser mismatch |
| **P2** | Doc/intake-state drift, misleading checklists, maintainability of scripts |
| **P3** | Style, naming, non-blocking suggestions |

## Architecture invariants (flag violations)

1. **No private keys in tree** — never commit `*.key`, `*.pem`, or private-key material; secret scan must stay green.
2. **Placeholder signature is intentional** — committed `registry/index.json.sig` may be `PLACEHOLDER`; production signing happens only in the protected deployment workflow. Do not treat the placeholder as an unsigned-production fallback or replace it with a local "real" signature in source.
3. **Hashes from download only** — artifact digests come from `scripts/add-package.py` (download + compute). Never hand-type SHA256 values into the index or specs.
4. **Source builds stay out** — reject `kind: source` and unsupported archive suffixes at intake; binary artifacts only for official catalog promotion.
5. **Provenance preserved** — CI-built plugin intake must keep `source.rev` (immutable upstream commit) and human-facing tag provenance from the plugins handoff.
6. **Stage 1 evidence before promote** — activatable packages need lifecycle-prove evidence (or an explicit deferral with reason). See [`docs/lifecycle-prove.md`](../../../docs/lifecycle-prove.md).
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
