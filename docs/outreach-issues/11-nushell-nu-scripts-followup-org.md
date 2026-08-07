Follow-up on the earlier packing discussion (no zip hosting; agreed).

You mentioned openness to **folder organization** that makes package managers' lives easier. That's the angle I'd actually use next.

## What I'm doing short-term

Keeping **registry-hosted mirrors** for:

- `nushell/nu-hooks`
- `nushell/custom-completions` (whole tree)
- `nushell/git-completions` (git slice; already split out for search)

Next wave likely adds more **per-tool completion packages** (cargo / npm / make / winget / …) as separate Numan entries, still mirrored from this repo at a pinned commit. No request that you store zip/tar artifacts here.

## Lightweight organization ask (optional)

If you ever reorganize, these conventions would reduce special-casing on my side (and probably help nupm/git consumers too):

1. Keep **one directory per completion tool** under `custom-completions/<tool>/` with a single obvious entry `*-completions.nu` (already mostly true).
2. Prefer **stable directory names** over renames when possible (registry ids and docs link paths).
3. For anything meant as a standalone module (weather, extractors, etc.), a clear `mod.nu` (or documented entry) at the slice root helps activation tools.

No CI, no release assets, no size growth. If you'd rather leave structure alone, mirrors stay fine. This is not a blocker, just a standing preference if reorganization energy appears.

Happy to draft a small README section under `custom-completions/` describing "how package managers should pin slices" if that would help contributors.
