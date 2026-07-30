# Numan Registry Roadmap

**Status date:** 2026-07-29

**Consolidated plan:** Cross-repo priorities and the Wave 1 → registry → client
critical path live in
[`numan/docs/plans/2026-07-30-consolidated-multi-repo-roadmap.md`](https://github.com/tonythethompson/numan/blob/master/docs/plans/2026-07-30-consolidated-multi-repo-roadmap.md).
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
- The live candidate list is
  [`docs/intake-candidates.md`](intake-candidates.md).

## Highest Priority: Import The Next CI-Built Plugin Wave

The next registry change should wait for `numan-plugins` PR #4 to merge and for
the manual `build-plugins` workflow to publish immutable assets for:

- `FMotalleb/nu_plugin_port_extension@0.113.1`
- `FMotalleb/nu_plugin_image@0.112.2`

Checklist:

- [ ] Fetch the generated `spec-*.json` artifacts from the successful
  `numan-plugins` build workflow run.
- [ ] Place specs under `specs/` in a focused registry branch.
- [ ] Run `python scripts/add-package.py --spec specs/<file>.json --write` for
  each package. Let the script download artifacts and compute SHA256 values.
- [ ] Do not add unrelated catalog targets in the same PR.
- [ ] Run `python scripts/sync-intake-candidates.py` if intake-state or index
  changes need the human candidate doc refreshed.
- [ ] Run local checks:
  `python scripts/scan_for_secrets.py`,
  `python scripts/preflight.py`,
  `python scripts/validate.py --index registry/index.json --sig registry/index.json.sig --pub keys/official.pub --skip-artifacts`,
  `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json`,
  and `python scripts/lint-manifest-index.py --index registry/index.json --manifest ../numan-plugins/manifest.json`.
- [ ] Open a PR with the spec artifacts, generated index diff, intake doc
  updates, and clear test evidence.
- [ ] Run staging after review if needed.
- [ ] Run lifecycle-prove against a real Nu matching each package constraint
  before production promotion.
- [ ] Dispatch production only after validation is green and reviewer approval
  exists.

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

- [ ] Extend package linting to report actionable errors for missing metadata,
  duplicate targets, unknown target triples, unsupported archive suffixes,
  missing activation declarations, malformed Nu constraints, and source
  provenance mismatches.
- [ ] Keep lint output deterministic so reviewers can compare before/after
  reports in PRs.
- [ ] Make the PR template ask for lint, parser-check, and lifecycle evidence.

### Stage 3: Repo Discovery

- [ ] Add read-only discovery for a GitHub repo, release URL, or local checkout.
- [ ] Detect `nupm.nuon`, module/script/completion layout, plugin Cargo
  metadata, release assets, license, homepage, tags, Nu dependency versions,
  and platform matrix.
- [ ] Separate discovered facts from guessed fields and maintainer decisions.

### Stage 4: Candidate Generation

- [ ] Generate draft specs, not committed registry entries.
- [ ] Include provenance for each inferred field.
- [ ] Mark unresolved decisions explicitly.
- [ ] Keep generated JSON stable and reviewable.

### Stage 5: Validation Reports

- [ ] Produce machine-readable and human-readable validation evidence for each
  candidate.
- [ ] Cover download, hash, archive layout, install, activation readiness,
  doctor, list, deactivate/remove/gc, and final state inspection.
- [ ] Keep production secrets unavailable to validation jobs.

### Stage 6: Registry PR Generation

- [ ] Generate a PR branch from validated specs and evidence.
- [ ] Include a concise summary of package type, provenance, supported targets,
  lifecycle results, limitations, and publish plan.
- [ ] Keep human review and protected signing mandatory.

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
