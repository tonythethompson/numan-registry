Not a bug — a packaging suggestion for package-manager consumers.

[Numan](https://github.com/tonythethompson/numan) is a Nushell package manager that verifies installs with sha256-pinned artifacts. We've added both **dotnu** (v0.0.18) and **numd** (v0.4.0) to the [official registry](https://github.com/tonythethompson/numan-registry) using **registry-hosted mirrors** of your tags, because the releases today have no uploaded zip assets.

GitHub's auto-generated `/archive/refs/tags/…` zipballs are not guaranteed byte-stable over time, which breaks hash-pinned installs if GitHub changes archive generation.

**Would you be open to attaching a zip per package as an uploaded release asset on future tags?** Suggested layouts:

**dotnu**

```text
dotnu-0.0.18.zip
└── dotnu-0.0.18/
    ├── nupm.nuon
    └── dotnu/
        └── mod.nu
        …
```

**numd**

```text
numd-0.4.0.zip
└── numd-0.4.0/
    ├── nupm.nuon
    └── numd/
        └── mod.nu
        …
```

Both packages already ship `nupm.nuon` — uploaded zips would align with nupm/Numan and any other hash-pinned consumer.

We're mirroring the exact bytes ourselves for now, so this isn't blocking. Happy to open PR(s) with a small tag-triggered release workflow (similar to [nutest v1.2.0](https://github.com/vyadh/nutest/releases/tag/v1.2.0)) if useful.

**Where to track:** fine to keep this issue on either repo; we'll watch both.
