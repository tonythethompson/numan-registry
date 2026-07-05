Not a bug — a packaging suggestion for package-manager consumers.

[Numan](https://github.com/tonythethompson/numan) is a Nushell package manager that verifies installs with sha256-pinned artifacts. We've added `amtoine/nu-git-manager` v0.8.0 to the [official registry](https://github.com/tonythethompson/numan-registry) using a **registry-hosted mirror** of tag `0.8.0`, because the release today has no uploaded zip asset.

GitHub's auto-generated `/archive/refs/tags/…` zipballs are not guaranteed byte-stable over time, which breaks hash-pinned installs if GitHub changes archive generation.

**Would you be open to attaching a zip as an uploaded release asset on future tags?** Suggested layout (matches how we mirror `pkgs/nu-git-manager/` today):

```text
nu-git-manager-0.8.0.zip
└── nu-git-manager-0.8.0/
    └── pkgs/
        └── nu-git-manager/
            ├── nupm.nuon
            └── nu-git-manager/
                └── mod.nu
            …
```

You're already in the [nupm registry](https://github.com/nushell/nupm) with git pins — an uploaded zip would help Numan and any other consumer that pins artifact hashes.

We're mirroring the exact bytes ourselves for now, so this isn't blocking anything on our end. Happy to open a PR adding a small GitHub Actions release workflow (similar to [nutest v1.2.0](https://github.com/vyadh/nutest/releases/tag/v1.2.0)) if that would be useful.
