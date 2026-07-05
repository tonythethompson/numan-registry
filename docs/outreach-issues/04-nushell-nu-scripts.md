`nu_scripts` is a different beast from the single-module repos we've been onboarding — wanted to ask how you think about **release artifacts** before we assume the wrong model.

Context: [Numan](https://github.com/tonythethompson/numan) (package manager, hash-verified installs) now lists two slices of this repo, both pinned at **`f04cb44`**:

| Registry name | What we packaged |
|---------------|------------------|
| `nushell/nu-hooks@0.1.0` | the `nu-hooks/` tree |
| `nushell/custom-completions@0.1.0-f04cb44` | `custom-completions/` |

nupm already consumes this repo via **git revision pins**, which fits a monorepo. Numan wants a downloadable artifact per entry, so we built mirrors on our side rather than using `/archive/{commit}.zip` (same byte-stability concerns as tag archives).

**What I'm trying to learn:**

1. **nu-hooks** — hooks are individual `.nu` files under subdirs, no top-level `mod.nu`. Is a subfolder zip on releases something you'd ever want, or should git pins remain the canonical distribution?

2. **custom-completions** — big, churny tree. Periodic snapshot releases? Split repo? Or "registry mirrors forever" is expected for this kind of content?

Not looking for a drive-by Actions PR — this repo's release story is yours. Mostly want to know if we're fighting the grain by mirroring, or if there's a lightweight convention you'd prefer (even if it's "please keep mirroring").

For reference, a single-module upstream recently added an uploaded zip after a similar conversation: [nutest#29](https://github.com/vyadh/nutest/issues/29) → [v1.2.0 asset](https://github.com/vyadh/nutest/releases/tag/v1.2.0).
