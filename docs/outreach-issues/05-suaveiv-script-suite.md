Hi. Small packaging heads-up / ask.

I've been building out the [Numan](https://github.com/tonythethompson/numan) official registry (hash-verified installs for Nu plugins, modules, scripts, and completions). Your **`nu_script_wttr`** is already listed as an install-only package via a registry-hosted mirror of `main`. Next catalog wave looks at more of the same shape from your repos:

| Planned registry id | Repo |
|---------------------|------|
| `SuaveIV/nu_script_wttr` (live) | this repo / related |
| `SuaveIV/nu_script_gh_status` | [nu_script_gh_status](https://github.com/SuaveIV/nu_script_gh_status) |
| `SuaveIV/nu_script_hnews` | [nu_script_hnews](https://github.com/SuaveIV/nu_script_hnews) |

Scripts stay **install-only** in Numan for now (no Nu config mutation until I design activation). The ask is only about **byte-stable release artifacts**.

**Optional (nice, not required):** on tags, upload something like:

```text
nu_script_gh_status-0.1.0.zip
└── nu_script_gh_status-0.1.0/
    └── …your .nu entry + README…
```

Same pattern for wttr / hnews when you cut versions. Flat layouts are fine. Uploaded Release assets (`.zip` / `.tar.gz`) beat GitHub auto-generated `/archive/` zipballs for sha256 pins.

If you'd rather stay git/`main`-only, say the word and I'll keep mirroring and won't nag. Happy to open a minimal tag→zip Actions PR on one repo if that helps.

(Opening here as the first script already in the registry; treat it as covering the SuaveIV script suite.)
