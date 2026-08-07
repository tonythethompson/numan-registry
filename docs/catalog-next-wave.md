# Catalog next wave: non-plugin gaps

_Research date: 2026-08-06. Sources: live `docs/catalog-compat.md` (generated 2026-08-05), `numan-plugins/docs/backlog.json` (69 plugins), [awesome-nu](https://github.com/nushell/awesome-nu) README, `nushell/nu_scripts`, `docs/intake-candidates.md`, client install-only rules in `numan/docs/plans/consolidated-multi-repo-roadmap.md`._

## Verdict

The official catalog is **plugin-heavy and script-thin**. Further plugin waves yield diminishing returns: almost every backlog entry that can be CI-built on a supported Nu minor is already `PROMOTED`. The critical adoption gaps for a less experienced user are **scripts, per-tool completions, and a few everyday modules**, delivered as **install-only mirrors** until activation contracts exist.

Do not treat "next wave" as another `numan-plugins` CI batch by default. Prefer registry mirror packages from `nu_scripts` slices and standalone Nu module/script repos.

## Current catalog shape

From `docs/catalog-compat.md` (36 packages):

| Type | Count | Share |
|------|------:|------:|
| plugin | 26 | 72% |
| module | 7 | 19% |
| completion | 2 | 6% |
| script | 1 | 3% |

Notes on non-plugins already present:

- **Modules:** `bash-env-nushell`, `nutest`, `dotnu`, `numd`, `nu-hooks`, `nu-git-manager` (+ sugar; archived upstream).
- **Completions:** `nushell/custom-completions` (whole tree snapshot) and `nushell/git-completions` (git slice). Both install-only mirrors at commit `f04cb44`.
- **Scripts:** only `SuaveIV/nu_script_wttr`.

`numan try` starters are still almost all plugins/modules (`skim`, Windows `semver`, `nutest`). There is no script-shaped first win.

## Plugin backlog is not the bottleneck

`numan-plugins/docs/backlog.json` status mix (69 entries):

| Status | Count | Implication |
|--------|------:|-------------|
| PROMOTED | 19 | Already in registry via CI-built or related path |
| NO_RELEASE | 38 | Needs upstream tags or commit-snapshot policy |
| PRE_0_112 | 10 | Deferred until upstream Nu bump |
| CREDENTIALS | 1 | `galuszkak/nu_plugin_bigquery` (needs cred lifecycle plan) |
| ELIGIBLE | 1 | `SuaveIV/nu_plugin_audio` already live in registry |

Highest-demand **deferred** plugins (outreach / wait, not next registry PR):

1. `FMotalleb/nu_plugin_clipboard` (85★, pinned ~0.110)
2. `Euphrasiologist/nu_plugin_plot` (71★, no tags)
3. `yybit/nu_plugin_compress` (42★, pinned ~0.103)
4. `devyn/nu_plugin_dbus` (34★, pinned ~0.101, not Windows)

Secondary registry polish (not gap-filling): multi-OS `abusch/nu_plugin_semver` intake; `fennewald/nu_plugin_net` when Windows assets exist.

## Gap analysis vs awesome-nu / nu_scripts

### Scripts (largest gap)

awesome-nu lists ~50 Script entries. Catalog has **1**. High-value install-only candidates that fit the existing `build-mirror-zip.py` path:

| Priority | Candidate | Why | Packaging notes |
|----------|-----------|-----|-----------------|
| P0 | `SuaveIV/nu_script_gh_status` | Same author/pattern as live `nu_script_wttr`; tiny, network demo | Mirror whole repo |
| P0 | `SuaveIV/nu_script_hnews` | Browser-less HN demo; strong `try` companion | Mirror whole repo |
| P0 | `Sanceilaks/nufetch` | Instant "it works" neofetch-like demo | Mirror; confirm license + layout |
| P1 | `KamilKleina/git-aliases.nu` | Everyday shell usability without plugin ABI | Mirror; type `module` or `script` after inspect |
| P1 | `nushell/nu_scripts` weather + extract slices | Already known upstream; complements wttr | Mirror paths like git-completions (`modules/weather`, `modules/data_extraction`) |
| P1 | `fj0r/docker.nu`, `fj0r/git.nu` | Popular structured CLI wrappers | Mirror; smoke with Docker/git present |
| P2 | `yh17549/nu-dir-bookmark` | Jump/bookmark UX | Mirror |
| P2 | `SuaveIV/nu_script_time_sync` (+ world-time) | Small companion suite | Mirror |
| P2 | `nushell-prophet/nu-history-tools`, `nu-cmd-stack` | Same provenance family as `numd`/`dotnu` | Mirror; heavier UX surface |
| Defer | `fj0r/ai.nu`, Salesforce/QuickBooks, telegram bots | Credentials / niche; poorer first-use | Outreach later |
| Defer | Prompt themes (`powerline.nu`, catppuccin) | Config mutation risk; needs activation story | After script activation design |

### Completions (second gap)

awesome-nu highlights cargo / git / make / npm / winget. Catalog ships the mega `custom-completions` tree **plus** a git slice only. Users searching `cargo` or `winget` do not see discrete packages.

Recommended wave: **split top-N completion packages** as install-only mirrors (same commit pin as existing `f04cb44` or refresh together):

1. `nushell/cargo-completions`
2. `nushell/npm-completions`
3. `nushell/make-completions`
4. `nushell/winget-completions` (Windows-first demo)
5. `nushell/aws-completions` (if present under `custom-completions/aws`)
6. Later: docker / kubectl / gh / bat once the packaging pattern is boring

Keep the mega `nushell/custom-completions` package; do not remove it. Splits improve discoverability in `search`.

### Modules (smaller gap, better activation story)

Modules can already activate. Prefer packages with clear exports and low host coupling:

| Priority | Candidate | Why |
|----------|-----------|-----|
| P1 | Refresh / add `nu_scripts` docker, kubernetes helpers if they load as modules | Real day-job demos without ABI |
| P1 | Confirm whether `git-aliases.nu` activates cleanly as a module | Better than install-only for UX |
| P2 | `amasialabs/nushell-modules` (snip) | Snippet manager |
| Defer | Archived `nu-git-manager` replacements | Already have archived mirrors; avoid more archive debt |

## Recommended Wave 3 (registry-first)

Goal: make `search` / first-use demos feel like a shell ecosystem, not only a plugin ABI zoo. Target **8–12 install-only packages**, no `numan-plugins` build unless a deferred plugin suddenly gains a 0.114 tag.

### Wave 3A: Scripts (prove diversity)

- [ ] `SuaveIV/nu_script_gh_status`
- [ ] `SuaveIV/nu_script_hnews`
- [ ] `Sanceilaks/nufetch`
- [ ] Optional 4th: `KamilKleina/git-aliases.nu` (module if activation works)

Intake steps per package: `scripts/discover.py` → `build-mirror-zip.py` → registry release asset → `add-package.py --write` → sync intake docs → staging → lifecycle evidence consistent with install-only type → production.

### Wave 3B: Completions (discoverability)

- [ ] Individual mirrors: cargo, npm, make, winget (+ aws if easy)
- [ ] Refresh pin with existing nu_scripts mirrors in the same PR if convenient (single commit SHA across nu_scripts-derived packages)

### Wave 3C: Client honesty (same timeframe, separate PRs)

- [ ] Document in README / search UX that scripts & completions are install-only (path printed; no silent activate)
- [ ] Consider adding one **install-only** starter path to `numan try` docs (or a follow-up `try` fallback) once Wave 3A is live: e.g. wttr or nufetch on any Nu
- [ ] Do **not** invent script/completion activation in the catalog wave (roadmap: still deferred)

### Explicit non-goals for Wave 3

- No commit-snapshot CI for `nu_plugin_plot` / other NO_RELEASE plugins
- No PRE_0_112 rebuilds
- No credentialed BigQuery promotion
- No mixing source-build work into registry intake PRs

## Wave 4 (parallel track, plugins)

Only if upstream moves, or maintainer time remains after Wave 3:

1. Outreach: clipboard, compress, plot (tag + nu-plugin 0.114)
2. Multi-OS `semver` registry completion
3. Research tag policy for high-star NO_RELEASE only after Wave 3 ships

## Outreach (what to file vs mirror)

Full tracker + weekly schedule: [`upstream-release-outreach.md`](upstream-release-outreach.md). Ready bodies: [`outreach-issues/`](outreach-issues/README.md).

| Do now (low risk) | Do with Wave 3 mirrors | Parallel plugin track | Do not |
|-------------------|------------------------|------------------------|--------|
| Follow-up comment on [nu_scripts#1266](https://github.com/nushell/nu_scripts/issues/1266): folder org only, not zips ([draft 11](outreach-issues/11-nushell-nu-scripts-followup-org.md)) | Courtesy optional-zip issues for SuaveIV suite, nufetch, git-aliases ([05](outreach-issues/05-suaveiv-script-suite.md)–[07](outreach-issues/07-kamilkleina-git-aliases.md)) | Clipboard / plot / compress Nu-tag asks ([08](outreach-issues/08-fmotalleb-clipboard-nu114.md)–[10](outreach-issues/10-yybit-compress-nu-bump.md)) | Re-ask nu_scripts for release zips (already declined) |
| Optional nudge [numd#115](https://github.com/nushell-prophet/numd/issues/115) ([draft 12](outreach-issues/12-nushell-prophet-numd-nudge.md)) | Mirror first; upstream assets optional | One upstream per week | Spam amtoine (archived) |

## Tracking debt to open

1. **`numan-registry/docs/non-plugin-backlog.json`** (or extend intake-state): plugin backlog does not cover scripts/modules/completions.
2. **`numan try` starter diversity**: add at least one Nu-agnostic script after Wave 3A.
3. **Activation contracts** for scripts/completions remain on the consolidated roadmap; catalog growth must stay install-only until those land.

## Success criteria

Wave 3 is done when:

- Catalog type mix moves toward roughly **≥6 scripts or completion packages** (today: 3 combined).
- `numan search weather` / `git` / `cargo` / `fetch` return obvious non-plugin hits with honest install-only behavior.
- Lifecycle-prove (or type-appropriate install smoke) passes on at least Linux and Windows for the new packages.
- Plugin backlog status counts are unchanged except for genuine upstream Nu bumps.

## Related docs

- [`catalog-compat.md`](catalog-compat.md): live package list
- [`intake-candidates.md`](intake-candidates.md): intake status
- [`numan-plugins/docs/backlog.json`](https://github.com/tonythethompson/numan-plugins/blob/main/docs/backlog.json): plugin candidates only
- [`numan/docs/plans/consolidated-multi-repo-roadmap.md`](https://github.com/tonythethompson/numan/blob/master/docs/plans/consolidated-multi-repo-roadmap.md): install-only package types
