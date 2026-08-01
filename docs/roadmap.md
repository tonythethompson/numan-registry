# Numan Registry Roadmap

**Status date:** 2026-07-31

**Consolidated plan:** Cross-repo priorities and the Wave 1 → registry → client
critical path live in
[`numan/docs/plans/consolidated-multi-repo-roadmap.md`](https://github.com/tonythethompson/numan/blob/master/docs/plans/consolidated-multi-repo-roadmap.md).
This file keeps registry-local operational detail.

This repository is the source of truth for the signed official Numan registry.
It should grow through small, evidenced catalog changes, not broad hand-written
JSON edits.

## Current Baseline

- Production registry publication is live through the protected
  `Production registry` workflow.
- Source-tree `registry/index.json.sig` remains a placeholder by design;
  production signing happens in the protected workflow.
- Intake tooling can scaffold entries from specs, compute artifact hashes,
  validate schemas, scan secrets, run preflight checks, parse the catalog with
  the production Numan parser, and lint Nu constraints against
  `numan-plugins/manifest.json`.
- Stage 1 lifecycle evidence is mandatory for activatable package promotion.
  The harness writes local evidence; the workflow uploads it.
- Stage 2 package lint + PR evidence checklist landed in
  [PR #31](https://github.com/tonythethompson/numan-registry/pull/31).
- The live candidate list is
  [`docs/intake-candidates.md`](intake-candidates.md).
- Wave 1 CI-built packages are in production:
  `port_extension@0.113.1` and `image@0.112.2`
  ([intake PR #32](https://github.com/tonythethompson/numan-registry/pull/32);
  production run
  [30600799679](https://github.com/tonythethompson/numan-registry/actions/runs/30600799679)).

## Highest Priority: Import The Next CI-Built Plugin Wave

Wave 1 intake for:

- `FMotalleb/nu_plugin_port_extension@0.113.1`
- `FMotalleb/nu_plugin_image@0.112.2`

Checklist:

- [x] Fetch the generated `spec-*.json` artifacts from the successful
  `numan-plugins` build workflow run.
- [x] Place specs under `specs/` in a focused registry branch.
- [x] Run `python scripts/add-package.py --spec specs/<file>.json --write` for
  each package. Let the script download artifacts and compute SHA256 values.
- [x] Do not add unrelated catalog targets in the same PR.
- [x] Run `python scripts/sync-intake-candidates.py` if intake-state or index
  changes need the human candidate doc refreshed.
- [x] Run local checks:
  `python scripts/scan_for_secrets.py`,
  `python scripts/preflight.py`,
  `python scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub --skip-artifacts`,
  `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json`,
  and `python scripts/lint-manifest-index.py --index registry/index.json --manifest ../numan-plugins/manifest.json`.
- [x] Open a PR with the spec artifacts, generated index diff, intake doc
  updates, and clear test evidence.
- [x] Staging after merge (green on `main`).
- [x] Lifecycle-prove against real Nu matching each package constraint
  (Linux x86_64: Nu 0.113.1 / 0.112.2).
- [x] Production dispatch after validation and approval.

## Catalog Maintenance

- [ ] Keep `docs/intake-state.json` as the editable candidate source and
  regenerate `docs/intake-candidates.md`; avoid hand-editing generated status
  tables unless the generator cannot express the needed state.
- [ ] Keep every live package entry tied to provenance:
  upstream URL, source revision where available, release asset URL, hashes, Nu
  constraints, supported targets, and package type.
- [ ] Preserve the distinction between upstream assets and registry-hosted
  mirrors. Mirrors are acceptable, but should stay visible and reviewable.
- [ ] Track upstream release asset outreach in
  `docs/upstream-release-outreach.md`.
- [ ] Prefer upstream-owned release assets over mirrors when maintainers ship
  byte-stable archives.
- [ ] Revisit currently blocked packages when upstreams add supported archive
  formats, newer Nu pins, or missing platform targets.

## Intake Automation Roadmap

Stage 1 is implemented. Remaining automation should follow the staged plan in
the Numan client repo's
[`docs/registry-intake-roadmap.md`](https://github.com/tonythethompson/numan/blob/master/docs/registry-intake-roadmap.md).

### Stage 2: Stronger Local Lint

- [x] Extend package linting to report actionable errors for missing metadata,
  duplicate targets, unknown target triples, unsupported archive suffixes,
  missing activation declarations, malformed Nu constraints, and source
  provenance mismatches (`scripts/lint_packages.py`).
- [x] Keep lint output deterministic so reviewers can compare before/after
  reports in PRs.
- [x] Make the PR template ask for lint, parser-check, and lifecycle evidence.

### Stage 3: Repo Discovery

- [x] Add read-only discovery for a GitHub repo, release URL, or local checkout
  (`scripts/discover.py`).
- [x] Detect `nupm.nuon`, module/script/completion layout, plugin Cargo
  metadata, release assets, license, homepage, tags, Nu dependency versions,
  and platform matrix.
- [x] Separate discovered facts from guessed fields and maintainer decisions.

### Stage 4: Candidate Generation

- [x] Generate draft specs, not committed registry entries
  (`scripts/gen_candidate.py`).
- [x] Include provenance for each inferred field (`_meta.field_provenance`).
- [x] Mark unresolved decisions explicitly (`_meta.unresolved`).
- [x] Keep generated JSON stable and reviewable.

### Stage 5: Validation Reports

- [x] Produce machine-readable and human-readable validation evidence for each
  candidate (`scripts/validate_candidate.py`).
- [x] Cover download, hash, archive layout, install, activation readiness,
  doctor, list, deactivate/remove/gc, and final state inspection (via
  `add-package.py` + `lint_packages.py` + `validate.py` + `lifecycle-prove.py`).
- [x] Keep production secrets unavailable to validation jobs.

### Stage 6: Registry PR Generation

- [x] Generate a PR branch from validated specs and evidence
  (`scripts/open_intake_pr.py`).
- [x] Include a concise summary of package type, provenance, supported targets,
  lifecycle results, limitations, and publish plan.
- [x] Keep human review and protected signing mandatory (`--push` required;
  dry-run is default; never signs or pushes to main).

## Production Safety Rules

- [ ] Never commit or print private key material.
- [ ] Never treat the source-tree placeholder signature as production evidence.
- [ ] Never publish a package before artifacts are hash-pinned and reviewable.
- [ ] Never add lifecycle-activatable packages without lifecycle evidence.
- [ ] Never mix catalog expansion with workflow/signing refactors unless the
  catalog change depends on the safety change.

## 1.0 Registry Gate

The registry side is ready for Numan 1.0 when:

- routine package additions are spec-driven and reproducible;
- the live catalog has meaningful Windows, macOS, and Linux coverage;
- every activatable package has lifecycle evidence or a documented exception;
- mirrors are tracked and upstream outreach status is clear;
- production signing is boring, protected, and auditable;
- `numan registry sync` plus client search/info/install behavior reflects the
  catalog accurately.
