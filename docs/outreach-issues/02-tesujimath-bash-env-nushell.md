Not a bug — a packaging suggestion for package-manager consumers.

[Numan](https://github.com/tonythethompson/numan) is a Nushell package manager that verifies installs with sha256-pinned artifacts. We've added `tesujimath/bash-env-nushell` v0.19.0 to the [official registry](https://github.com/tonythethompson/numan-registry) using a **registry-hosted mirror** of tag `0.19.0`, because there is no uploaded release zip today.

GitHub's auto-generated `/archive/refs/tags/…` zipballs are not guaranteed byte-stable over time, which breaks hash-pinned installs if GitHub changes archive generation.

**Would you be open to attaching a zip as an uploaded release asset on future tags?** Suggested layout:

```text
bash-env-nushell-0.19.0.zip
└── bash-env-nushell-0.19.0/
    ├── bash-env.nu
    ├── README.md
    ├── LICENSE
    …
```

(Entry file is `bash-env.nu`, not `mod.nu` — that's fine for our activation path.)

We're mirroring the exact bytes ourselves for now, so this isn't blocking. Happy to open a PR with a small tag-triggered release workflow if you'd like one.

Note: we document that `bash-env-json` must be on PATH separately — not part of this ask.
