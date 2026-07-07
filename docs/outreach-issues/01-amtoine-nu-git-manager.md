Hi — I'm adding NGM to the [Numan](https://github.com/tonythethompson/numan) registry (same general idea as nupm: install from a curated index, verify artifacts by hash).

You're already listed in the [nupm registry](https://github.com/nushell/nupm) with git pins on `pkgs/nu-git-manager`. For Numan I need something with stable bytes per tag, so right now we're hosting a mirror of **0.8.0** ourselves (`pkgs/nu-git-manager/` zipped as `nu-git-manager-0.8.0.zip`).

The awkward part is GitHub's tag archive URLs — `/archive/refs/tags/0.8.0.zip` and friends — aren't something I'd trust to stay byte-identical forever. GitHub has changed how those archives are built before, and hash-pinned installs break silently when the bytes drift.

**Would you consider uploading a zip on release tags?** Something like:

```text
nu-git-manager-0.8.0.zip
└── nu-git-manager-0.8.0/
    └── pkgs/nu-git-manager/   # same tree nupm already points at
```

No rush on our side — the mirror works. If an uploaded asset is something you'd want, I can send a PR for a tiny release workflow (vyadh did this for [nutest](https://github.com/vyadh/nutest/releases/tag/v1.2.0) and it was straightforward).
