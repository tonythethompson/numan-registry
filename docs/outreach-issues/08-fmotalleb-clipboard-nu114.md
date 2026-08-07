Hi. Demand-side note from the [Numan](https://github.com/tonythethompson/numan) / [numan-plugins](https://github.com/tonythethompson/numan-plugins) catalog work.

`nu_plugin_clipboard` is one of the highest-starred community plugins I still cannot promote into the official registry: latest release I see pins **nu-plugin ~0.110**, while the catalog's current CI-built / demo lane is centered on **Nu 0.114** (plugin ABI is minor-scoped).

Two asks, either of which unblocks listing:

1. **Nu bump**: a tagged release that builds against `nu-plugin` / `nu-protocol` **0.114.x** (or whatever minor you intend to support next).
2. **Release shape**: uploaded per-target archives (`.zip` / `.tar.gz` / `.tar.xz`) on that tag help hash-pinned clients. If upstream builds are inconvenient, I can CI-build from your tag via numan-plugins the same way I did for desktop notifications / port_extension. I still need a **compatible tag + commit**.

Not filing this as "broken"; older minors are fine for their users. I just can't honestly ship an install path that fails ABI on the Nu versions first-use demos target.

If a 0.114 bump is already in progress, a pointer to a branch/PR is enough and I can align intake. Happy to test a release candidate on Windows + Linux once tagged.
