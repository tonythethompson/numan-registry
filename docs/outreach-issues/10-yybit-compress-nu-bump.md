Heads-up from the [Numan](https://github.com/tonythethompson/numan) catalog triage.

`nu_plugin_compress` (zstd/gzip/bzip2/xz) is a strong everyday plugin candidate, but the latest tag I researched (`0.2.5`) pins **nu-plugin ~0.103**, which I treat as pre-support for the current official-registry lane (focused on **0.114** / nearby minors).

**Ask:** if/when you bump to a modern `nu-plugin` / `nu-protocol` (0.114.x preferred), please cut a tagged release. Uploaded target archives are a bonus; tag + Cargo pins are enough for [numan-plugins](https://github.com/tonythethompson/numan-plugins) to CI-build and hand assets to the registry.

No rush and no implication the 0.103 line is wrong. I just can't list it honestly for users on current Nu. A comment here when a bump lands is plenty; I'll pick up intake from there.
