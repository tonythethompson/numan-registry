# Registry intake candidates

Running list of packages evaluated for the official Numan registry.
_Auto-synced 2026-07-05 23:02 UTC from `docs/intake-state.json`, `registry/index.json`, and GitHub (via `gh`). Edit `intake-state.json` to add candidates; run `python scripts/sync-intake-candidates.py` to refresh._

**Intake rules:** artifact must be `.zip`, `.tar.gz`, `.tgz`, or `.tar` (not `.tar.xz`); prefer upstream uploaded release assets over GitHub auto-generated `/archive/` zipballs; never hand-type `sha256` (use `scripts/add-package.py`); mirror packages via `scripts/build-mirror-zip.py` + registry release upload. See [upstream-release-outreach.md](upstream-release-outreach.md) for contacting maintainers to ship upstream assets.

**Currently in registry:** `SuaveIV/nu_plugin_audio@0.2.8` (upstream), `abusch/nu_plugin_semver@0.11.17` (upstream), `amtoine/nu-git-manager@0.8.0` (mirror), `fdncred/nu_plugin_file@0.25.2` (upstream), `nushell-prophet/dotnu@0.0.18` (mirror), `nushell-prophet/numd@0.4.0` (mirror), `nushell-works/nu_plugin_nw_ulid@0.2.0` (upstream), `nushell/custom-completions@0.1.0-f04cb44` (mirror), `nushell/nu-hooks@0.1.0` (mirror), `tesujimath/bash-env-nushell@0.19.0` (mirror), `vyadh/nutest` (1.1.0, 1.2.0).

---

## Ready to add now

Upstream ships byte-stable release assets in Numan-supported formats.

| Package | Type | Version | Platforms | Status |
|---------|------|---------|-----------|--------|
| [`nushell-works/nu_plugin_nw_ulid`](https://github.com/nushell-works/nu_plugin_nw_ulid) | plugin | v0.2.0 | linux, macOS, Windows (full matrix, `.tar.gz` + `.zip`) | live (upstream asset) |
| [`SuaveIV/nu_plugin_audio`](https://github.com/SuaveIV/nu_plugin_audio) | plugin | v0.2.8 | Windows zip + Linux aarch64 tar.gz (mac/x64-linux are tar.xz) | live (upstream asset) — partial platforms |
| [`fdncred/nu_plugin_file`](https://github.com/fdncred/nu_plugin_file) | plugin | v0.25.2 | Windows x64 + arm64 zip only | live (upstream asset) — Windows-only |

---

## Worth adding via registry mirror

No compliant upstream release asset; pack a tag/commit snapshot as a registry-hosted zip (see `scripts/build-mirror-zip.py`).

| Package | Type | Source | Status |
|---------|------|--------|--------|
| [`amtoine/nu-git-manager`](https://github.com/amtoine/nu-git-manager) | module | tag 0.8.0 | live (registry mirror) — outreach: outreach pending |
| [`tesujimath/bash-env-nushell`](https://github.com/tesujimath/bash-env-nushell) | module | tag 0.19.0 | live (registry mirror) — outreach: outreach pending |
| [`nushell-prophet/dotnu`](https://github.com/nushell-prophet/dotnu) | module | tag 0.0.18 | live (registry mirror) — outreach: outreach pending |
| [`nushell-prophet/numd`](https://github.com/nushell-prophet/numd) | module | tag 0.4.0 | live (registry mirror) — outreach: outreach pending |
| [`nushell/nu-hooks`](https://github.com/nushell/nu_scripts) | module | commit f04cb44 | live (registry mirror) — outreach: outreach pending — install-only |
| [`nushell/custom-completions`](https://github.com/nushell/nu_scripts/tree/main/custom-completions) | completion | commit f04cb44 | live (registry mirror) — outreach: outreach pending — install-only |

---

## Blocked for now

| Package | Blocker |
|---------|---------|
| [`idanarye/nu_plugin_skim`](https://github.com/idanarye/nu_plugin_skim) | v0.29.0 tag exists; release assets empty (dist CI not uploading) |
| [`FMotalleb/nu_plugin_clipboard`](https://github.com/FMotalleb/nu_plugin_clipboard) | nupm git-only; no release binaries (and other FMotalleb plugins) |
| [`abusch/nu_plugin_semver`](https://github.com/abusch/nu_plugin_semver) | mac/linux tar.xz only (in registry as Windows-only) |
| [`fennewald/nu_plugin_net`](https://github.com/fennewald/nu_plugin_net) | tar.xz only; no Windows zip |
| [`fnuttens/nu_plugin_hmac`](https://github.com/fnuttens/nu_plugin_hmac) | Bare binary upload, not zip/tar archive |
| fdncred/abusch cargo-dist plugins | Unix targets ship `.tar.xz`; Windows ships `.zip` |
| MCP / AI agent tooling | Not a Numan package type; would need module/script packaging |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-05 | Mirror module/completion batch (6 packages) in [#12](https://github.com/tonythethompson/numan-registry/pull/12) |
| 2026-07-05 | Ready-now plugin batch in [#11](https://github.com/tonythethompson/numan-registry/pull/11) |
| 2026-07-05 | Initial list |
