`nu_plugin_plot` shows up often in awesome-nu / demand lists (~70★), but as far as I can tell there are **no git tags / GitHub Releases** to pin.

For the [Numan](https://github.com/numan-cli/numan) official registry and [numan-plugins](https://github.com/numan-cli/numan-plugins) CI builds I need an immutable **tag + commit**. Without that I either stay off-catalog or invent a commit-snapshot policy (something I'd rather not do without maintainer buy-in).

**Ask:** would you be willing to cut a versioned tag (even `v0.1.0`) on a known-good commit, ideally with `nu-plugin` / `nu-protocol` on a current minor (0.114.x if practical)?

Release binaries are optional. A tag alone is enough for me to CI-build multi-OS archives and propose a registry intake. If you prefer git-main-only permanently, that's a clear "defer" on my side too.

Open compatible-with-old-Nu issues (#32 etc.) suggest the project still has users. A tag would help every package manager, not just Numan.
