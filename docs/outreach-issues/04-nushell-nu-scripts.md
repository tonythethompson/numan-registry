Not a bug — a packaging / policy question for package-manager consumers.

[Numan](https://github.com/tonythethompson/numan) is a Nushell package manager that verifies installs with sha256-pinned artifacts. We've added two entries sourced from this repo (pinned at commit `f04cb44`):

- `nushell/nu-hooks` v0.1.0 — registry mirror of the `nu-hooks/` tree
- `nushell/custom-completions` v0.1.0-f04cb44 — registry mirror of `custom-completions/`

Both use **registry-hosted mirrors** because there are no uploaded release zips for these paths today, and GitHub's auto-generated `/archive/refs/tags/…` / `/archive/{commit}.zip` endpoints are not guaranteed byte-stable for hash pinning.

**Question:** Is there appetite for uploaded release assets for individual nupm-style packages in this monorepo? For example:

```text
nu-hooks-0.1.0.zip
└── nu-hooks-0.1.0/
    └── nu-hooks/
        …
```

and/or periodic snapshot zips of `custom-completions/`?

We know this repo is structured differently from single-module repos — not asking for a workflow PR without maintainer buy-in. Mostly wondering whether subfolder release assets fit your release model, or if git pins (as nupm uses today) are the intended long-term path.

Our mirrors are not blocking anything on our end. If the answer is "git pins only," that's useful to know and we'll keep mirroring those paths.

Related precedent: [vyadh/nutest#29](https://github.com/vyadh/nutest/issues/29) (upstream added `nutest-X.Y.Z.zip` in v1.2.0 after a similar ask).
