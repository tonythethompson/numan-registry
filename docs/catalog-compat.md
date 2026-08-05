# Official registry catalog compatibility

_Auto-generated from `registry/index.json`. Do not hand-edit._

Generated: `2026-08-05T07:36:40Z` · Index `updated_at`: `2026-08-05T07:36:40Z` · `registry_revision`: `seed-2026-07-02`

This is the **master list** of packages in the official Numan registry and the Nu constraint on each package's **latest** version. For demand-ranked *plugin candidates* not yet in the registry, see [`numan-plugins/docs/backlog.json`](https://github.com/tonythethompson/numan-plugins/blob/main/docs/backlog.json). For intake workflow status, see [`intake-candidates.md`](intake-candidates.md).

## Summary

- **36** packages total
- By type: `completion` 2, `module` 7, `plugin` 26, `script` 1
- Latest version Nu band: `0.114` 18, `0.113` 4, `0.112` 1, `other` 6, `*` 7

Nu band is a coarse label from the constraint **lower bound** (`>=0.114` → `0.114`, etc.; else `*` or `other`). Exact constraints are in the table and in the signed index.

## Catalog (latest version per package)

| Package | Type | Latest | Nu constraint | Band | Targets | Provenance | Versions |
|---------|------|--------|---------------|------|---------|------------|----------|
| `abusch/nu_plugin_semver` | plugin | 0.11.17 | `>=0.113.0 <0.114.0` | 0.113 | win | upstream | 1 |
| `alex-kattathra-johnson/nu_plugin_ws` | plugin | 1.0.6 | `>=0.107.0 <0.108.0` | other | mac,win,linux | upstream | 1 |
| `amtoine/nu-git-manager` | module | 0.8.0 | `>=0.92.0` | other | — | mirror | 1 |
| `amtoine/nu-git-manager-sugar` | module | 0.7.0 | `>=0.92.0` | other | — | mirror | 1 |
| `b4nst/nu_plugin_format_pcap` | plugin | 0.1.0 | `>=0.101.0 <0.102.0` | other | mac,linux,win | upstream | 1 |
| `cptpiepmatz/nu_plugin_highlight` | plugin | 1.4.16 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 2 |
| `dead10ck/nu_plugin_dns` | plugin | 4.0.10 | `>=0.113.0 <0.114.0` | 0.113 | mac,linux | ci-built | 1 |
| `drbrain/nu_plugin_prometheus` | plugin | 0.12.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,win,linux | ci-built | 1 |
| `fdncred/nu_plugin_emoji` | plugin | 0.23.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `fdncred/nu_plugin_file` | plugin | 0.26.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 2 |
| `fdncred/nu_plugin_json_path` | plugin | 0.24.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `fdncred/nu_plugin_jwalk` | plugin | 0.26.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `fdncred/nu_plugin_parquet` | plugin | 0.24.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `fdncred/nu_plugin_query_git` | plugin | 0.24.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `fdncred/nu_plugin_regex` | plugin | 0.23.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 2 |
| `fdncred/nu_plugin_strutils` | plugin | 0.22.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `FMotalleb/nu_plugin_desktop_notifications` | plugin | 0.114.1 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `FMotalleb/nu_plugin_image` | plugin | 0.112.2 | `>=0.112.0 <0.113.0` | 0.112 | mac,linux,win | ci-built | 1 |
| `FMotalleb/nu_plugin_port_extension` | plugin | 0.114.1 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 2 |
| `fnuttens/nu_plugin_hmac` | plugin | 0.27.0 | `>=0.113.0 <0.114.0` | 0.113 | mac,linux,win | ci-built | 1 |
| `idanarye/nu_plugin_skim` | plugin | 0.29.1 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `Kissaki/nu_plugin_bson` | plugin | 26.1140.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `lizclipse/nu_plugin_ulid` | plugin | 0.23.0 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `nushell-prophet/dotnu` | module | 0.0.18 | `*` | * | — | mirror | 1 |
| `nushell-prophet/numd` | module | 0.4.0 | `*` | * | — | mirror | 1 |
| `nushell-works/nu_plugin_nw_ulid` | plugin | 0.2.0 | `>=0.111.0 <0.112.0` | other | mac,linux,win | upstream | 1 |
| `nushell/custom-completions` | completion | 0.1.0-f04cb44 | `*` | * | — | mirror | 1 |
| `nushell/git-completions` | completion | 0.1.0-f04cb44 | `*` | * | — | mirror | 1 |
| `nushell/nu-hooks` | module | 0.1.0 | `*` | * | — | mirror | 1 |
| `rhino-linux/nu_plugin_nutext` | plugin | 0.6.2 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |
| `SuaveIV/nu_plugin_audio` | plugin | 0.2.8 | `>=0.113.1 <0.114.0` | 0.113 | linux,win | upstream | 1 |
| `SuaveIV/nu_script_wttr` | script | 0.1.0-main | `*` | * | — | mirror | 1 |
| `tesujimath/bash-env-nushell` | module | 0.19.0 | `*` | * | — | upstream | 1 |
| `Trivernis/nu-plugin-dialog` | plugin | 0.1.0 | `>=0.107.0 <0.108.0` | other | win | upstream | 1 |
| `vyadh/nutest` | module | 1.2.0 | `>=0.114.0` | 0.114 | — | upstream | 2 |
| `Yethal/nu_plugin_hcl` | plugin | 0.114.1 | `>=0.114.0 <0.115.0` | 0.114 | mac,linux,win | ci-built | 1 |

## How to refresh

```bash
python scripts/render_catalog_compat.py
python scripts/render_catalog_compat.py --check   # CI drift gate
```

Run after every index-changing PR (`add-package.py --write`, mirrors, Nu constraint edits). Commit the regenerated markdown with the index.

## Related lists

| List | Role |
|------|------|
| `registry/index.json` | Signed source of truth (all versions + hashes) |
| `docs/catalog-compat.md` | This file: human catalog × Nu overview |
| `docs/intake-state.json` / `intake-candidates.md` | Intake pipeline status |
| `numan-plugins/manifest.json` | CI-built plugins currently built |
| `numan-plugins/docs/backlog.json` | Demand-ranked plugin candidates |
