## Summary

<!-- What changed and why (intake package, docs, tooling, …). -->

## Checklist

- [ ] `registry/index.json` validates (`schemas/index-v1.json` / staging workflow)
- [ ] Artifact digests were produced by `scripts/add-package.py` (never hand-typed)
- [ ] For CI-built plugins: `nu_version` matches `numan-plugins/manifest.json` `active[]`
      (CI runs `scripts/lint-manifest-index.py`; run locally if iterating)
- [ ] Lifecycle-prove noted for new/changed installable packages (or explicitly deferred)

## Test plan

- [ ] …
