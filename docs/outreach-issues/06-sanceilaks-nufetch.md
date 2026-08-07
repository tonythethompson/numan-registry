`nufetch` is a great first-use demo for Nushell (and for package managers that want something that "just looks alive" without a plugin ABI pin).

I'm adding packages to the [Numan registry](https://github.com/tonythethompson/numan-registry) focused on scripts and everyday modules. Plan is to list **`Sanceilaks/nufetch`** as an **install-only** script (hash-verified download; user runs it themselves; I'm not auto-wiring config yet).

Today that means I'd host a registry mirror of a pinned commit/tag. If you're open to it, an uploaded release zip would let me pin **your** artifact instead:

```text
nufetch-{version}.zip
└── nufetch-{version}/
    └── …entry .nu + README…
```

Requirements that matter for consumers like Numan:

- Uploaded GitHub Release asset (not `/archive/refs/tags/…`)
- Stable bytes per tag
- Any sensible top-level folder layout

Totally fine to decline. Mirrors work. If you want the lowest-maintenance path, I can PR a tiny tag→zip workflow (same idea as [nutest's release workflow](https://github.com/vyadh/nutest/blob/v1.2.0/.github/workflows/release.yaml) after [nutest#29](https://github.com/vyadh/nutest/issues/29)).
