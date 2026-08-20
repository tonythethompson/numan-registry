Both **dotnu** and **numd** ship with `nupm.nuon` and proper tags. That made them easy candidates for the [Numan registry](https://github.com/numan-cli/numan-registry). I've got them listed now at **0.0.18** and **0.4.0** respectively.

One gap: the GitHub releases have tags but no attached zips. For hash-verified installs I need a byte-stable artifact, so I'm currently mirroring each tag myself on [numan-registry releases](https://github.com/numan-cli/numan-registry/releases) rather than pointing at upstream.

I'd love to flip that to **your** release assets if you're willing. Per-tag zips, roughly:

| Package | Suggested asset | Entry Numan activates |
|---------|-----------------|-----------------------|
| dotnu | `dotnu-0.0.18.zip` → `dotnu-0.0.18/{nupm.nuon, dotnu/mod.nu, …}` | `dotnu/mod.nu` |
| numd | `numd-0.4.0.zip` → `numd-0.4.0/{nupm.nuon, numd/mod.nu, …}` | `numd/mod.nu` |

Not asking for a monorepo-wide packaging overhaul; just whether uploaded assets on your existing tags/releases are in scope. If yes, I can open a PR with a minimal workflow on one repo and you can copy to the other.

If git-only distribution is the long-term plan, say the word and I'll stay on mirrors. Either answer helps.

(I opened this on **numd** but it covers both; close/duplicate on dotnu if that's cleaner for your triage.)
