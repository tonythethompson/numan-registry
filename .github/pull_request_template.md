## Summary

<!-- What changed and why (intake package, docs, tooling, …). -->

Reviewers: see [`REVIEW.md`](../REVIEW.md).

## Checklist

- [ ] `python scripts/lint_packages.py --index registry/index.json`
- [ ] `cargo run --locked --manifest-path tools/numan-parser-check/Cargo.toml -- registry/index.json`
- [ ] `registry/index.json` validates (`schemas/index-v1.json` / staging workflow)
- [ ] Artifact digests were produced by `scripts/add-package.py` (never hand-typed)
- [ ] For CI-built plugins: `nu_version` matches `numan-plugins/manifest.json` `active[]`
      (CI runs `scripts/lint-manifest-index.py`; run locally if iterating)
- [ ] Lifecycle-prove evidence attached for new/changed activatable packages
      (or explicitly deferred with reason)

## Test plan

- [ ] …
