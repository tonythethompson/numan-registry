# Registry intake candidates

Running list of packages evaluated for the official Numan registry.
_Auto-synced 2026-07-22 from `docs/intake-state.json`, `registry/index.json`, and GitHub (via `gh`). Edit `intake-state.json` to add candidates; run `python scripts/sync-intake-candidates.py` to refresh._

**Intake rules:** artifact must be `.zip`, `.tar.gz`, `.tgz`, or `.tar` (not `.tar.xz`); prefer upstream uploaded release assets over GitHub auto-generated `/archive/` zipballs; never hand-type `sha256` (use `scripts/add-package.py`); mirror packages via `scripts/build-mirror-zip.py` + registry release upload. After intake, the package **must be staged or published** in the configured registry before running Stage 1 lifecycle-prove (`scripts/lifecycle-prove.py --package owner/name`), unless a registry-target override is added. Run lifecycle-prove on a clean root against a real Nu matching the package constraint ([lifecycle-prove.md](lifecycle-prove.md)). See [upstream-release-outreach.md](upstream-release-outreach.md) for contacting maintainers to ship upstream assets.

**Currently in registry:** `SuaveIV/nu_plugin_audio@0.2.8` (upstream), `SuaveIV/nu_script_wttr@0.1.0-main` (mirror), `Trivernis/nu-plugin-dialog@0.1.0` (upstream), `abusch/nu_plugin_semver@0.11.17` (upstream), `alex-kattathra-johnson/nu_plugin_ws@1.0.6` (upstream), `amtoine/nu-git-manager@0.8.0` (mirror), `amtoine/nu-git-manager-sugar@0.7.0` (mirror), `b4nst/nu_plugin_format_pcap@0.1.0` (upstream), `cptpiepmatz/nu_plugin_highlight@1.4.15` (upstream), `dead10ck/nu_plugin_dns@4.0.10` (upstream), `fdncred/nu_plugin_file@0.25.2` (upstream), `fdncred/nu_plugin_regex@0.22.0` (upstream), `nushell-prophet/dotnu@0.0.18` (mirror), `nushell-prophet/numd@0.4.0` (mirror), `nushell-works/nu_plugin_nw_ulid@0.2.0` (upstream), `nushell/custom-completions@0.1.0-f04cb44` (mirror), `nushell/git-completions@0.1.0-f04cb44` (mirror), `nushell/nu-hooks@0.1.0` (mirror), `tesujimath/bash-env-nushell@0.19.0` (upstream), `vyadh/nutest` (1.1.0, 1.2.0).

---

## Ready to add now

Upstream ships byte-stable release assets in Numan-supported formats.

| Package | Type | Version | Platforms | Status |
|---------|------|---------|-----------|--------|
| [`nushell-works/nu_plugin_nw_ulid`](https://github.com/nushell-works/nu_plugin_nw_ulid) | plugin | v0.2.0 | linux, macOS, Windows (full matrix, `.tar.gz` + `.zip`) | live (upstream asset) |
| [`SuaveIV/nu_plugin_audio`](https://github.com/SuaveIV/nu_plugin_audio) | plugin | v0.2.8 | Windows zip + Linux aarch64 tar.gz (mac/x64-linux are tar.xz) | live (upstream asset) — partial platforms |
| [`fdncred/nu_plugin_file`](https://github.com/fdncred/nu_plugin_file) | plugin | v0.25.2 | Windows x64 + arm64 zip only | live (upstream asset) — Windows-only |
| [`b4nst/nu_plugin_format_pcap`](https://github.com/b4nst/nu_plugin_format_pcap) | plugin | v0.1.0 | linux, macOS, Windows (full matrix, `.tar.gz`) | live (upstream asset) |
| [`alex-kattathra-johnson/nu_plugin_ws`](https://github.com/alex-kattathra-johnson/nu_plugin_ws) | plugin | v1.0.6 | linux, macOS, Windows (full matrix, `.tar.gz` + `.zip`) | live (upstream asset) |
| [`Trivernis/nu-plugin-dialog`](https://github.com/Trivernis/nu-plugin-dialog) | plugin | v0.1.0 | Windows x64 zip only | live (upstream asset) — Windows-only |
| [`tesujimath/bash-env-nushell`](https://github.com/tesujimath/bash-env-nushell) | module | v0.19.0 | all platforms (`.zip` archive — platform-agnostic Nu module) | live (upstream asset) |
| [`cptpiepmatz/nu_plugin_highlight`](https://github.com/cptpiepmatz/nu-plugin-highlight) | plugin | v1.4.15 | linux x64/arm64, macOS arm64, Windows x64 (no intel mac) | live (upstream asset) — ci-built via numan-plugins |
| [`fdncred/nu_plugin_regex`](https://github.com/fdncred/nu_plugin_regex) | plugin | v0.22.0 | linux x64/arm64, macOS arm64, Windows x64 (no intel mac) | live (upstream asset) — ci-built via numan-plugins |
| [`dead10ck/nu_plugin_dns`](https://github.com/dead10ck/nu_plugin_dns) | plugin | v4.0.10 | linux x64/arm64, macOS arm64 only | live (upstream asset) — ci-built via numan-plugins; no Windows (upstream build fails on Windows) |

---

## Worth adding via registry mirror

No compliant upstream release asset; pack a tag/commit snapshot as a registry-hosted zip (see `scripts/build-mirror-zip.py`).

| Package | Type | Source | Status |
|---------|------|--------|--------|
| [`amtoine/nu-git-manager`](https://github.com/amtoine/nu-git-manager) | module | tag 0.8.0 | live (registry mirror) — outreach: blocked (repo archived (read-only); cannot open issues or comments) |
| [`nushell-prophet/dotnu`](https://github.com/nushell-prophet/dotnu) | module | tag 0.0.18 | live (registry mirror) — outreach: issue open (nushell-prophet/numd#115) |
| [`nushell-prophet/numd`](https://github.com/nushell-prophet/numd) | module | tag 0.4.0 | live (registry mirror) — outreach: issue open (nushell-prophet/numd#115) |
| [`nushell/nu-hooks`](https://github.com/nushell/nu_scripts) | module | commit f04cb44 | live (registry mirror) — outreach: responded — see nushell/nu_scripts#1266 — install-only |
| [`nushell/custom-completions`](https://github.com/nushell/nu_scripts/tree/main/custom-completions) | completion | commit f04cb44 | live (registry mirror) — outreach: responded — see nushell/nu_scripts#1266 — install-only |
| [`SuaveIV/nu_script_wttr`](https://github.com/SuaveIV/nu_script_wttr) | script | branch main | live (registry mirror) — install-only |
| [`amtoine/nu-git-manager-sugar`](https://github.com/amtoine/nu-git-manager) | module | tag 0.7.0 | live (registry mirror) — outreach: blocked (repo archived (read-only); cannot open issues or comments) |
| [`nushell/git-completions`](https://github.com/nushell/nu_scripts/tree/main/custom-completions/git) | completion | commit f04cb44 | live (registry mirror) — outreach: responded — see nushell/nu_scripts#1266 — install-only |

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
| 2026-07-21 | Intake CI-built plugins from numan-plugins: cptpiepmatz/nu_plugin_highlight@1.4.15, fdncred/nu_plugin_regex@0.22.0, dead10ck/nu_plugin_dns@4.0.10 |
| 2026-07-10 | Switched tesujimath/bash-env-nushell@0.19.0 from registry mirror to upstream release asset (tesujimath/bash-env-nushell#50, #51; cutover in [#16](https://github.com/tonythethompson/numan-registry/pull/16)) |
| 2026-07-06 | Batch 3: plugins (format_pcap, ws, dialog), first script (nu_script_wttr), mirrors (git-manager-sugar, git-completions) |
| 2026-07-05 | Ready-now plugin batch in [#11](https://github.com/tonythethompson/numan-registry/pull/11) |
| 2026-07-05 | Initial list |
