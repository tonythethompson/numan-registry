Quick packaging question from the [Numan](https://github.com/tonythethompson/numan) registry side.

`git-aliases.nu` is on the short list for a **module or script** entry (everyday Git UX without needing a plugin ABI match), which helps users whose Nu minor doesn't line up with many plugins yet.

I'll start with a registry-hosted mirror of a tagged (or commit-pinned) tree so installs are hash-verified. If you'd prefer upstream ownership of the artifact, a per-tag uploaded zip is ideal:

```text
git-aliases.nu-{version}.zip
└── git-aliases.nu-{version}/
    └── …alias module entry…
```

Flat is fine. Same constraints as other Nu modules: uploaded `.zip`/`.tar.gz`, byte-stable per tag, avoid relying on GitHub auto-archives for pinned digests.

No pressure. Mirror forever is an acceptable outcome. Happy to contribute a small release workflow PR if you want one.
