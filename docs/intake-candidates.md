# Registry intake candidates

Running list of packages evaluated for the official Numan registry. Updated as packages are researched, added, or re-triaged.

**Intake rules:** artifact must be `.zip`, `.tar.gz`, `.tgz`, or `.tar` (not `.tar.xz`); prefer upstream uploaded release assets over GitHub auto-generated `/archive/` zipballs; never hand-type `sha256` (use `scripts/add-package.py`); mirror packages via `scripts/build-mirror-zip.py` + registry release upload. See [upstream-release-outreach.md](upstream-release-outreach.md) for contacting maintainers to ship upstream assets.

**Currently in registry:** `abusch/nu_plugin_semver`, `vyadh/nutest` (1.1.0 mirror + 1.2.0 upstream), plugin batch from [#11](https://github.com/tonythethompson/numan-registry/pull/11), mirror batch from [#12](https://github.com/tonythethompson/numan-registry/pull/12).

---

## Ready to add now

Upstream ships byte-stable release assets in Numan-supported formats.

| Package | Type | Version | Platforms | Status |
|---------|------|---------|-----------|--------|
| [`nushell-works/nu_plugin_nw_ulid`](https://github.com/nushell-works/nu_plugin_nw_ulid) | plugin | v0.2.0 | linux, macOS, Windows (full matrix, `.tar.gz` + `.zip`) | added in [#11](https://github.com/tonythethompson/numan-registry/pull/11) |
| [`SuaveIV/nu_plugin_audio`](https://github.com/SuaveIV/nu_plugin_audio) | plugin | v0.2.8 | Windows zip + Linux aarch64 tar.gz (mac/x64-linux are tar.xz) | added in [#11](https://github.com/tonythethompson/numan-registry/pull/11) — partial platforms |
| [`fdncred/nu_plugin_file`](https://github.com/fdncred/nu_plugin_file) | plugin | v0.25.2 | Windows x64 + arm64 zip only | added in [#11](https://github.com/tonythethompson/numan-registry/pull/11) — Windows-only |

---

## Worth adding via registry mirror

No compliant upstream release asset; pack a tag/commit snapshot as a registry-hosted zip (see `scripts/build-mirror-zip.py`).

| Package | Type | Source | Status |
|---------|------|--------|--------|
| [`amtoine/nu-git-manager`](https://github.com/amtoine/nu-git-manager) | module | tag 0.8.0 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| [`tesujimath/bash-env-nushell`](https://github.com/tesujimath/bash-env-nushell) | module | tag 0.19.0 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| [`nushell-prophet/dotnu`](https://github.com/nushell-prophet/dotnu) | module | tag 0.0.18 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| [`nushell-prophet/numd`](https://github.com/nushell-prophet/numd) | module | tag 0.4.0 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| [`nushell/nu_scripts` → `nu-hooks`](https://github.com/nushell/nu_scripts) | module | commit f04cb44 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) (install-only) |
| [`nushell/nu_scripts` → custom completions](https://github.com/nushell/nu_scripts/tree/main/custom-completions) | completion | commit f04cb44 | added in [#12](https://github.com/tonythethompson/numan-registry/pull/12) (install-only) |

---

## Blocked for now

| Package | Blocker |
|---------|---------|
| [`idanarye/nu_plugin_skim`](https://github.com/idanarye/nu_plugin_skim) | v0.29.0 tag exists; release assets empty (dist CI not uploading) |
| [`FMotalleb/nu_plugin_clipboard`](https://github.com/FMotalleb/nu_plugin_clipboard) and other FMotalleb plugins | nupm git-only; no release binaries |
| [`abusch/nu_plugin_semver`](https://github.com/abusch/nu_plugin_semver) mac/linux | tar.xz only (in registry as Windows-only) |
| [`fennewald/nu_plugin_net`](https://github.com/fennewald/nu_plugin_net) | tar.xz only; no Windows zip |
| [`fnuttens/nu_plugin_hmac`](https://github.com/fnuttens/nu_plugin_hmac) | Bare binary upload, not zip/tar archive |
| Most fdncred/abusch cargo-dist plugins | Unix targets ship `.tar.xz`; Windows ships `.zip` |
| MCP servers / AI agent tooling | Not a Numan package type; would need module/script packaging |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-05 | Mirror module/completion batch (6 packages) in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| 2026-07-05 | Ready-now plugin batch in [#11](https://github.com/tonythethompson/numan-registry/pull/11) |
| 2026-07-05 | Initial list |
