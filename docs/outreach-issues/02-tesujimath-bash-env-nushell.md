`bash-env-nushell` has effectively replaced the old `nu_plugin_bash_env` path for a lot of people. I'm pointing new installs at the module instead of the plugin.

I'm listing **0.19.0** in the [Numan registry](https://github.com/tonythethompson/numan-registry). Because there's no release asset on the tag yet, I packaged the repo root myself and host that zip on the registry releases. It works, but I'd rather pin against something you own.

The specific thing that makes me nervous about *not* having an uploaded asset: consumers that record `sha256(url)` will pick GitHub's auto-generated tag archive if I don't have anything else, and those archives aren't promised to stay byte-stable. One infrastructure change on GitHub's side and every pinned install looks corrupt.

If you're open to it, an uploaded **`bash-env-nushell-{version}.zip`** on future tags would be ideal. Flat layout is fine:

```text
bash-env-nushell-0.19.0/
├── bash-env.nu      # entry point (not mod.nu; intentional)
├── README.md
└── …
```

Totally fine if you'd rather not maintain release artifacts; I'll keep mirroring. Separate note: I already tell users they need `bash-env-json` on PATH; not asking you to bundle that.

Happy to contribute a tag → zip GitHub Action if that lowers the maintenance cost.
